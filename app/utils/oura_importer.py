import requests
from datetime import datetime, timedelta
from flask import current_app
from .. import db
from ..models.base import HealthData, DataType
import json

class OuraImporter:
    """Utility class for importing Oura Ring data through API"""
    
    def __init__(self, personal_token=None, access_token=None):
        self.personal_token = personal_token if personal_token else access_token
        self.api_base_url = "https://api.ouraring.com"
        self.auth_header = {'Authorization': f'Bearer {self.personal_token}'}
        self.debug = current_app.config.get('DEBUG', False)
    
    def _get_data(self, endpoint, params=None):
        """Helper method to fetch data from Oura API"""
        url = f"{self.api_base_url}{endpoint}"
        response = requests.get(url, headers=self.auth_header, params=params)
        
        if response.status_code != 200:
            current_app.logger.error(f"Error fetching data from Oura API: {response.text}")
            response.raise_for_status()
            
        return response.json()
    
    def import_sleep_data(self, start_date, end_date):
        """Import sleep data from Oura API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Get daily sleep data
        daily_sleep_data = self._get_data("/v2/usercollection/daily_sleep", params)
        
        # Get detailed sleep data
        sleep_data = self._get_data("/v2/usercollection/sleep", params)
        
        # Process and store the data
        processed_data = self._process_sleep_data(sleep_data, daily_sleep_data)
        self._store_data(processed_data, 'oura')
        
        # Update data source record
        self._update_data_source('oura')
        
        return processed_data
    
    def _process_sleep_data(self, sleep_data, daily_sleep_data):
        """Process raw Oura sleep data into a format for our database"""
        processed_data = []
        
        # Create a mapping of dates to REM sleep data to ensure we have metrics for all days
        day_to_rem_sleep = {}
        day_to_deep_sleep = {}
        day_to_light_sleep = {}
        day_to_awake_time = {}
        
        # Process daily summary metrics
        for day in daily_sleep_data.get('data', []):
            date = day.get('day')
            if not date:
                continue
                
            # Convert string date to datetime
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                current_app.logger.error(f"Invalid date format: {date}")
                continue
            
            # Store daily sleep score
            if 'score' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_score',
                    'metric_value': day['score'],
                    'metric_units': 'score'
                })
                
            # Process sleep metrics from daily summary if available
            if 'contributors' in day and 'rem_sleep' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'rem_sleep_score',
                    'metric_value': day['contributors']['rem_sleep'],
                    'metric_units': 'score'
                })
                
            if 'contributors' in day and 'deep_sleep' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'deep_sleep_score',
                    'metric_value': day['contributors']['deep_sleep'],
                    'metric_units': 'score'
                })
                
            if 'contributors' in day and 'total_sleep' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'total_sleep_score',
                    'metric_value': day['contributors']['total_sleep'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'latency' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_latency_score',
                    'metric_value': day['contributors']['latency'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'efficiency' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_efficiency_score',
                    'metric_value': day['contributors']['efficiency'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'restfulness' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_restfulness_score',
                    'metric_value': day['contributors']['restfulness'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'timing' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_timing_score',
                    'metric_value': day['contributors']['timing'],
                    'metric_units': 'score'
                })
                
            # Initialize tracking for this day
            day_to_rem_sleep[date] = 0
            day_to_deep_sleep[date] = 0
            day_to_light_sleep[date] = 0
            day_to_awake_time[date] = 0
        
        # Process detailed sleep sessions
        day_hr_data = {}
        day_hrv_data = {}
        day_hr_data2 = {}
        day_hrv_data2 = {}
        day_avg_resp = {}
        day_time_asleep = {}
        
        # Initialize these dictionaries for each date
        for day in day_to_rem_sleep.keys():
            day_hr_data[day] = []
            day_hrv_data[day] = []
            day_hr_data2[day] = []
            day_hrv_data2[day] = []
            day_avg_resp[day] = []
            day_time_asleep[day] = []
        
        # Track sleep stage totals for each day
        long_hr = {}
        lowest_hr = {}
        long_hrv = {}
        long_resp = {}
        long_efficiency = {}
        long_readiness = {}
        activity_balance_score = {}
        body_temperature_score = {}
        hrv_balance_score = {}
        previous_day_activity_score = {}
        previous_night_score = {}
        recovery_index_score = {}
        resting_heart_rate_score = {}
        sleep_balance_score = {}
        
        for sleep in sleep_data.get('data', []):
            day = sleep.get('day')
            if not day or day not in day_to_rem_sleep:
                continue
            
            if (sleep.get('average_heart_rate') is not None and 
                sleep.get('average_hrv') is not None and 
                sleep.get('average_breath') is not None):
                
                day_hr_data2[day].append(sleep['average_heart_rate'])
                day_hrv_data2[day].append(sleep['average_hrv'])
                day_avg_resp[day].append(sleep['average_breath'])
                day_time_asleep[day].append(sleep.get('time_in_bed', 0))
            
            # Extract sleep stages from the individual sleep session
            if sleep.get('rem_sleep_duration') is not None:
                day_to_rem_sleep[day] += sleep['rem_sleep_duration']
            
            if sleep.get('deep_sleep_duration') is not None:
                day_to_deep_sleep[day] += sleep['deep_sleep_duration']
            
            if sleep.get('light_sleep_duration') is not None:
                day_to_light_sleep[day] += sleep['light_sleep_duration']
            
            if sleep.get('awake_duration') is not None:
                day_to_awake_time[day] += sleep['awake_duration']
            
            # Store info from the longest sleep session
            if sleep.get('type') == 'long_sleep':
                if sleep.get('average_hrv') is not None:
                    long_hrv[day] = sleep['average_hrv']
                if sleep.get('average_heart_rate') is not None:
                    long_hr[day] = sleep['average_heart_rate']
                if sleep.get('lowest_heart_rate') is not None:
                    lowest_hr[day] = sleep['lowest_heart_rate']
                if sleep.get('average_breath') is not None:
                    long_resp[day] = sleep['average_breath']
                if sleep.get('efficiency') is not None:
                    long_efficiency[day] = sleep['efficiency']
                if sleep.get('readiness', {}).get('score') is not None:
                    long_readiness[day] = sleep['readiness']['score']
                if sleep.get('readiness', {}).get('contributors', {}) is not None:
                    activity_balance_score[day] = sleep['readiness']['contributors']['activity_balance']
                    body_temperature_score[day] = sleep['readiness']['contributors']['body_temperature']
                    hrv_balance_score[day] = sleep['readiness']['contributors']['hrv_balance']
                    previous_day_activity_score[day] = sleep['readiness']['contributors']['previous_day_activity']
                    previous_night_score[day] = sleep['readiness']['contributors']['previous_night']
                    recovery_index_score[day] = sleep['readiness']['contributors']['recovery_index']
                    resting_heart_rate_score[day] = sleep['readiness']['contributors']['resting_heart_rate']
                    sleep_balance_score[day] = sleep['readiness']['contributors']['sleep_balance']
        
        # Process metrics for each day
        for day, rem_sleep_duration in day_to_rem_sleep.items():
            # Convert day string to datetime
            try:
                day_obj = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                current_app.logger.error(f"Invalid date format: {day}")
                continue
            
            avg_hr2 = 0
            avg_hrv2 = 0
            avg_resp = 0
            
            # Process heart rate and HRV data
            if day_time_asleep[day]:  # Make sure we have data
                total_time_asleep = sum(day_time_asleep[day])
                for i in range(len(day_hr_data2[day])):
                    avg_hr2 += day_hr_data2[day][i] * (day_time_asleep[day][i] / total_time_asleep)
                    avg_hrv2 += day_hrv_data2[day][i] * (day_time_asleep[day][i] / total_time_asleep)
                    avg_resp += day_avg_resp[day][i] * (day_time_asleep[day][i] / total_time_asleep)
                
                # Store heart rate metrics
                if day_hr_data[day]:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'avg_hr_alt',
                        'metric_value': sum(day_hr_data[day]) / len(day_hr_data[day]) if day_hr_data[day] else 0,
                        'metric_units': 'bpm'
                    })
                
                if day_hrv_data[day]:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'avg_hrv_alt',
                        'metric_value': sum(day_hrv_data[day]) / len(day_hrv_data[day]) if day_hrv_data[day] else 0,
                        'metric_units': 'ms'
                    })
                
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'avg_hr',
                    'metric_value': avg_hr2,
                    'metric_units': 'bpm'
                })
                
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'avg_hrv',
                    'metric_value': avg_hrv2,
                    'metric_units': 'ms'
                })
                
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'avg_resp',
                    'metric_value': avg_resp,
                    'metric_units': 'breaths_per_min'
                })
            
            # Store sleep stage metrics from session data if they weren't in daily summary
            if rem_sleep_duration > 0:
                exists = any(item.get('date') == day_obj and item.get('metric_name') == 'rem_sleep' for item in processed_data)
                if not exists:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'rem_sleep',
                        'metric_value': rem_sleep_duration / 60,  # Convert seconds to minutes
                        'metric_units': 'minutes'
                    })
            
            if day_to_deep_sleep[day] > 0:
                exists = any(item.get('date') == day_obj and item.get('metric_name') == 'deep_sleep' for item in processed_data)
                if not exists:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'deep_sleep',
                        'metric_value': day_to_deep_sleep[day] / 60,  # Convert seconds to minutes
                        'metric_units': 'minutes'
                    })
            
            if day_to_light_sleep[day] > 0:
                exists = any(item.get('date') == day_obj and item.get('metric_name') == 'light_sleep' for item in processed_data)
                if not exists:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'light_sleep',
                        'metric_value': day_to_light_sleep[day] / 60,  # Convert seconds to minutes
                        'metric_units': 'minutes'
                    })
            
            if day_to_awake_time[day] > 0:
                exists = any(item.get('date') == day_obj and item.get('metric_name') == 'awake_time' for item in processed_data)
                if not exists:
                    processed_data.append({
                        'date': day_obj,
                        'metric_name': 'awake_time',
                        'metric_value': day_to_awake_time[day] / 60,  # Convert seconds to minutes
                        'metric_units': 'minutes'
                    })
            
            # Add long session data if available
            if day in long_hr:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'long_hr',
                    'metric_value': long_hr[day],
                    'metric_units': 'bpm'
                })
            
            if day in lowest_hr:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'lowest_hr',
                    'metric_value': lowest_hr[day],
                    'metric_units': 'bpm'
                })
            
            if day in long_hrv:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'long_hrv',
                    'metric_value': long_hrv[day],
                    'metric_units': 'ms'
                })
            
            if day in long_resp:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'long_resp',
                    'metric_value': long_resp[day],
                    'metric_units': 'breaths_per_min'
                })
            
            if day in long_efficiency:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'long_efficiency',
                    'metric_value': long_efficiency[day],
                    'metric_units': 'score'
                })
            
            if day in long_readiness:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'readiness_score',
                    'metric_value': long_readiness[day],
                    'metric_units': 'score'
                })

            if day in activity_balance_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'activity_balance_score',
                    'metric_value': activity_balance_score[day],
                    'metric_units': 'score'
                })

            if day in body_temperature_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'body_temperature_score',
                    'metric_value': body_temperature_score[day],
                    'metric_units': 'score'
                })

            if day in hrv_balance_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'hrv_balance_score',
                    'metric_value': hrv_balance_score[day],
                    'metric_units': 'score'
                })

            if day in previous_day_activity_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'previous_day_activity_score',
                    'metric_value': previous_day_activity_score[day],
                    'metric_units': 'score'
                })

            if day in previous_night_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'previous_night_score',
                    'metric_value': previous_night_score[day],
                    'metric_units': 'score'
                })

            if day in recovery_index_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'recovery_index_score',
                    'metric_value': recovery_index_score[day],
                    'metric_units': 'score'
                })

            if day in resting_heart_rate_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'resting_heart_rate_score',
                    'metric_value': resting_heart_rate_score[day],
                    'metric_units': 'score'
                })

            if day in sleep_balance_score:
                processed_data.append({
                    'date': day_obj,
                    'metric_name': 'sleep_balance_score',
                    'metric_value': sleep_balance_score[day],
                    'metric_units': 'score'
                })
        
        return processed_data
    
    def _store_data(self, processed_data, source):
        """Store processed data in the database"""
        records_added = 0
        records_updated = 0
        records_skipped = 0
        metrics_by_type = {}
        dates_range = set()
        
        for item in processed_data:
            # Skip items with null metric_value
            if item.get('metric_value') is None:
                current_app.logger.warning(f"Skipping record with null metric_value: {item}")
                records_skipped += 1
                continue
                
            # Track metrics for reporting
            metric_name = item.get('metric_name', 'unknown')
            if metric_name not in metrics_by_type:
                metrics_by_type[metric_name] = 0
            metrics_by_type[metric_name] += 1
            
            # Track date range
            if 'date' in item:
                dates_range.add(item['date'])
            
            # Get or create the DataType
            data_type = DataType.query.filter_by(
                source=source,
                metric_name=item['metric_name']
            ).first()
            
            if not data_type:
                data_type = DataType(
                    source=source,
                    metric_name=item['metric_name'],
                    metric_units=item.get('metric_units'),
                    source_type='api' if 'oura' in source else 'unknown'
                )
                db.session.add(data_type)
                db.session.flush()  # Flush to get the ID
            
            # Check if record already exists using the data_type_id and date
            existing = HealthData.query.filter_by(
                date=item['date'],
                data_type_id=data_type.id
            ).first()
            
            if existing:
                # Update existing record
                existing.metric_value = item['metric_value']
                records_updated += 1
            else:
                # Create new record
                new_data = HealthData(
                    date=item['date'],
                    data_type=data_type,
                    metric_value=item['metric_value']
                )
                db.session.add(new_data)
                records_added += 1
        
        # Commit changes to database
        db.session.commit()
        
        # Log detailed stats about the import
        date_range_str = ""
        if dates_range:
            min_date = min(dates_range)
            max_date = max(dates_range)
            date_range_str = f" (date range: {min_date} to {max_date})"
        
        current_app.logger.info(f"Imported {source} data: {records_added} new records, {records_updated} updated records, {records_skipped} skipped records{date_range_str}")
        
        # Log breakdown by metric type
        if metrics_by_type:
            metrics_breakdown = ", ".join([f"{metric}: {count}" for metric, count in metrics_by_type.items()])
            current_app.logger.info(f"Metrics breakdown: {metrics_breakdown}")
        
        # Update the data source last import date
        self._update_data_source(source)
        
        return processed_data
    
    def _update_data_source(self, source_name):
        """Update last import timestamp for data types from this source"""
        # Ensure we're using the base source name for Oura data
        if source_name.startswith('oura_'):
            # Strip the suffix and use just 'oura'
            source_name = 'oura'
            
        DataType.update_last_import(source_name)
    
    def import_activity_data(self, start_date, end_date):
        """Import activity data from Oura API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Get daily activity data
        activity_data = self._get_data("/v2/usercollection/daily_activity", params)
        
        # Process and store the data
        processed_data = self._process_activity_data(activity_data)
        self._store_data(processed_data, 'oura')
        
        # Update data source record
        self._update_data_source('oura')
        
        return processed_data
        
    def _process_activity_data(self, activity_data):
        """Process raw Oura activity data into a format for our database"""
        processed_data = []
        
        # Process daily activity metrics
        for day in activity_data.get('data', []):
            date = day.get('day')
            if not date:
                continue
                
            # Convert string date to datetime
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                current_app.logger.error(f"Invalid date format: {date}")
                continue
            
            # Store activity score
            if 'score' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'activity_score',
                    'metric_value': day['score'],
                    'metric_units': 'score'
                })
            
            # Store active calories
            if 'active_calories' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'active_calories',
                    'metric_value': day['active_calories'],
                    'metric_units': 'kcal'
                })
            
            # Store total calories
            if 'total_calories' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'total_calories',
                    'metric_value': day['total_calories'],
                    'metric_units': 'kcal'
                })
            
            # Store steps
            if 'steps' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'steps',
                    'metric_value': day['steps'],
                    'metric_units': 'count'
                })
            
            # Store equivalent walking distance
            if 'equivalent_walking_distance' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'walking_distance',
                    'metric_value': day['equivalent_walking_distance'],
                    'metric_units': 'meters'
                })
            
            # Store inactive time
            if 'sedentary_time' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sedentary_time',
                    'metric_value': day['sedentary_time'] / 3600, # seconds to hours
                    'metric_units': 'hours'
                })
            
            # Store met levels if available
            if 'met' in day:
                met_data = day['met']
                
                if 'average' in met_data:
                    processed_data.append({
                        'date': date_obj,
                        'metric_name': 'average_met',
                        'metric_value': met_data['average'],
                        'metric_units': 'met'
                    })
                
                if 'min' in met_data:
                    processed_data.append({
                        'date': date_obj,
                        'metric_name': 'min_met',
                        'metric_value': met_data['min'],
                        'metric_units': 'met'
                    })
                
                if 'max' in met_data:
                    processed_data.append({
                        'date': date_obj,
                        'metric_name': 'max_met',
                        'metric_value': met_data['max'],
                        'metric_units': 'met'
                    })

            if 'contributors' in day and 'meet_daily_targets' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'meet_daily_targets_score',
                    'metric_value': day['contributors']['meet_daily_targets'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'move_every_hour' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'move_every_hour_score',
                    'metric_value': day['contributors']['move_every_hour'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'recovery_time' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'recovery_time_score',
                    'metric_value': day['contributors']['recovery_time'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'stay_active' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'stay_active_score',
                    'metric_value': day['contributors']['stay_active'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'training_frequency' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'training_frequency_score',
                    'metric_value': day['contributors']['training_frequency'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'training_volume' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'training_volume_score',
                    'metric_value': day['contributors']['training_volume'],
                    'metric_units': 'score'
                })

        return processed_data

    def import_tags_data(self, start_date, end_date):
        """Import tags data from Oura API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Get enhanced tags data
        tags_data = self._get_data("/v2/usercollection/enhanced_tag", params)
        
        # Convert string dates to date objects
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            current_app.logger.error(f"Invalid date format: {start_date} or {end_date}")
            start_date_obj = None
            end_date_obj = None
        
        # Process and store the data
        processed_data = self._process_tags_data(tags_data, start_date_obj, end_date_obj)
        if processed_data:
            self._store_data(processed_data, 'oura')  # Always use 'oura' as the source
            
            # Update data source record
            self._update_data_source('oura')  # Use just 'oura', not 'oura_tags'
        
        return processed_data
    
    def _process_tags_data(self, tags_data, start_date=None, end_date=None):
        """Process raw Oura tags data into a format for our database"""
        processed_data = []
        
        # Check if we have valid data
        if not tags_data or 'data' not in tags_data or not tags_data['data']:
            return processed_data
        
        # Track unique tag types and their occurrence dates
        unique_tags = set()
        tag_dates = {}
        
        # Process tag metrics from the API response
        for tag in tags_data.get('data', []):
            tag_name = tag.get('tag_type_code')
            start_time = tag.get('start_time')
            
            if not tag_name or not start_time:
                continue
            
            # Extract the date part from the start_time
            try:
                # Format is typically ISO 8601, e.g., "2023-01-01T08:30:00+00:00"
                date_str = start_time.split('T')[0]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, IndexError):
                current_app.logger.error(f"Invalid start_time format: {start_time}")
                continue
            
            # Track this tag type
            unique_tags.add(tag_name)
            
            # Track dates for each tag type
            if tag_name not in tag_dates:
                tag_dates[tag_name] = {}
            
            if date_obj not in tag_dates[tag_name]:
                tag_dates[tag_name][date_obj] = 0
            
            # Increment the count for this tag on this date
            tag_dates[tag_name][date_obj] += 1
        
        # If no tags found in the current import, check for existing tag types from the database
        if not unique_tags and start_date and end_date:
            try:
                # Query existing tag types from the database
                existing_tags = db.session.query(
                    DataType.metric_name
                ).filter(
                    DataType.metric_name.like('tag_%'),
                    DataType.source == 'oura'
                ).distinct().all()
                
                # Add existing tag types to our set
                for tag in existing_tags:
                    unique_tags.add(tag.metric_name.replace('tag_', ''))
            except Exception as e:
                current_app.logger.error(f"Error querying existing tag types: {str(e)}")
        
        # Create a complete date range, using provided start_date and end_date if available
        if unique_tags:
            if start_date and end_date:
                # Use provided date range
                min_date = start_date
                max_date = end_date
            else:
                # Get date range from the data
                all_dates = set()
                for tag_date_dict in tag_dates.values():
                    all_dates.update(tag_date_dict.keys())
                
                if all_dates:
                    min_date = min(all_dates)
                    max_date = max(all_dates)
                else:
                    # No dates in current import, but we might have tag types
                    # If we have start_date and end_date, use those
                    if start_date and end_date:
                        min_date = start_date
                        max_date = end_date
                    else:
                        # No data, return empty
                        return processed_data
            
            # Create a complete date range
            complete_range = []
            current_date = min_date
            while current_date <= max_date:
                complete_range.append(current_date)
                current_date += timedelta(days=1)
            
            # Ensure every tag type has an entry for every date in the range
            for tag_name in unique_tags:
                for date_obj in complete_range:
                    # Get the count for this tag on this date (0 if not present)
                    count = tag_dates.get(tag_name, {}).get(date_obj, 0)
                    
                    processed_data.append({
                        'date': date_obj,
                        'metric_name': f"tag_{tag_name}",
                        'metric_value': count,
                        'metric_units': 'count'
                    })
        
        return processed_data
    
    def import_stress_data(self, start_date, end_date):
        """Import daily stress data from Oura API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Get daily stress data
        stress_data = self._get_data("/v2/usercollection/daily_stress", params)
        
        # Process and store the data
        processed_data = self._process_stress_data(stress_data)
        self._store_data(processed_data, 'oura')
        
        # Update data source record
        self._update_data_source('oura')
        
        return processed_data
    
    def _process_stress_data(self, stress_data):
        """Process raw Oura stress data into a format for our database"""
        processed_data = []
        
        # Process daily stress metrics
        for day in stress_data.get('data', []):
            date = day.get('day')
            if not date:
                continue
                
            # Convert string date to datetime
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                current_app.logger.error(f"Invalid date format: {date}")
                continue
            
            # Store stress_high metric
            if 'stress_high' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'stress_high',
                    'metric_value': day['stress_high'],
                    'metric_units': 'score'
                })
            
            # Store recovery_high metric
            if 'recovery_high' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'recovery_high',
                    'metric_value': day['recovery_high'],
                    'metric_units': 'score'
                })
            
            # Store day_summary if available
            # We skip this because it's a string value and our database needs numeric values
            # If needed in the future, we could convert it to a numeric code or create a separate table
        
        return processed_data
    
    def diagnostic_check(self, start_date, end_date):
        """Run diagnostic checks to identify potential issues with data import"""
        diagnostics = {
            "api_status": "unknown",
            "date_range": f"{start_date} to {end_date}",
            "endpoints_checked": {},
            "data_counts": {}
        }
        
        # Check API connectivity
        try:
            response = requests.get(f"{self.api_base_url}/v2/usercollection/personal_info", 
                                   headers=self.auth_header)
            diagnostics["api_status"] = f"HTTP {response.status_code}"
            if response.status_code == 200:
                user_info = response.json()
                diagnostics["user_info"] = {
                    "email": user_info.get('data', {}).get('email', 'unknown')
                }
        except Exception as e:
            diagnostics["api_status"] = f"Error: {str(e)}"
            
        # Check each endpoint
        endpoints = [
            "/v2/usercollection/daily_sleep",
            "/v2/usercollection/sleep",
            "/v2/usercollection/daily_activity",
            "/v2/usercollection/enhanced_tag",
            "/v2/usercollection/daily_stress"
        ]
        
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.api_base_url}{endpoint}", 
                                      headers=self.auth_header, 
                                      params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    data_count = len(data.get('data', []))
                    diagnostics["endpoints_checked"][endpoint] = {
                        "status": response.status_code,
                        "data_count": data_count
                    }
                    diagnostics["data_counts"][endpoint.split('/')[-1]] = data_count
                else:
                    diagnostics["endpoints_checked"][endpoint] = {
                        "status": response.status_code,
                        "message": response.text
                    }
            except Exception as e:
                diagnostics["endpoints_checked"][endpoint] = {
                    "status": "error",
                    "message": str(e)
                }
                
        # Check database counts
        try:
            sleep_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.in_(['sleep_score', 'rem_sleep', 'deep_sleep'])
            ).count()
            
            activity_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.in_(['activity_score', 'steps'])
            ).count()
            
            tag_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.like('tag_%')
            ).count()
            
            diagnostics["database_counts"] = {
                "sleep": sleep_count,
                "activity": activity_count,
                "tags": tag_count
            }
        except Exception as e:
            diagnostics["database_counts"] = {
                "error": str(e)
            }
            
        current_app.logger.info(f"Oura diagnostics: {json.dumps(diagnostics, indent=2, default=str)}")
        return diagnostics 