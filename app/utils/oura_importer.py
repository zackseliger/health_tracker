import os
import json
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from flask import current_app
from .. import db
from ..models.base import HealthData, DataSource, ImportRecord

class OuraImporter:
    """Utility class for importing Oura Ring data through API"""
    
    def __init__(self, personal_token=None):
        self.personal_token = personal_token
        self.api_base_url = "https://api.ouraring.com"
        self.auth_header = {'Authorization': f'Bearer {self.personal_token}'}
    
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
        self._update_data_source('oura_sleep')
        
        return processed_data
    
    def _process_sleep_data(self, sleep_data, daily_sleep_data):
        """Process raw Oura sleep data into a format for our database"""
        processed_data = []
        
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
                    'metric_name': 'total_sleep',
                    'metric_value': day['contributors']['total_sleep'],
                    'metric_units': 'score'
                })

            if 'contributors' in day and 'latency' in day['contributors']:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'sleep_latency',
                    'metric_value': day['contributors']['latency'],
                    'metric_units': 'score'
                })
        
        # Process detailed sleep sessions
        prev_day = None
        day_hr_data = []
        day_hrv_data = []
        day_hr_data2 = []
        day_hrv_data2 = []
        day_avg_resp = []
        day_time_asleep = []
        # Track sleep stage totals for each day
        day_rem_sleep = 0
        day_deep_sleep = 0
        day_light_sleep = 0
        day_awake_time = 0
        long_hrv = 0
        long_hr = 0
        long_resp = 0
        long_efficiency = 0
        long_readiness = 0
        
        for sleep in sleep_data.get('data', []):
            day = sleep.get('day')
            if not day:
                continue
                
            # When we move to a new day, process the previous day's data
            if day != prev_day and prev_day is not None:
                avg_hr2 = 0
                avg_hrv2 = 0
                avg_resp = 0
                
                if day_time_asleep:  # Make sure we have data
                    total_time_asleep = sum(day_time_asleep)
                    for i in range(len(day_hr_data2)):
                        avg_hr2 += day_hr_data2[i] * (day_time_asleep[i] / total_time_asleep)
                        avg_hrv2 += day_hrv_data2[i] * (day_time_asleep[i] / total_time_asleep)
                        avg_resp += day_avg_resp[i] * (day_time_asleep[i] / total_time_asleep)
                
                    # Convert previous day string to datetime
                    try:
                        prev_day_obj = datetime.strptime(prev_day, "%Y-%m-%d").date()
                    except ValueError:
                        current_app.logger.error(f"Invalid date format: {prev_day}")
                        prev_day = day
                        continue
                
                    # Store metrics for the previous day
                    if day_hr_data:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'avg_hr_alt',
                            'metric_value': sum(day_hr_data) / len(day_hr_data),
                            'metric_units': 'bpm'
                        })
                    
                    if day_hrv_data:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'avg_hrv_alt',
                            'metric_value': sum(day_hrv_data) / len(day_hrv_data),
                            'metric_units': 'ms'
                        })
                    
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'avg_hr',
                        'metric_value': avg_hr2,
                        'metric_units': 'bpm'
                    })
                    
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'avg_hrv',
                        'metric_value': avg_hrv2,
                        'metric_units': 'ms'
                    })
                    
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'avg_resp',
                        'metric_value': avg_resp,
                        'metric_units': 'breaths_per_min'
                    })
                    
                    # Store sleep stage metrics from session data if they weren't in daily summary
                    # We check if we already have data for this metric to avoid duplicates
                    if day_rem_sleep > 0:
                        exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'rem_sleep' for item in processed_data)
                        if not exists:
                            processed_data.append({
                                'date': prev_day_obj,
                                'metric_name': 'rem_sleep',
                                'metric_value': day_rem_sleep / 60,  # Convert seconds to minutes
                                'metric_units': 'minutes'
                            })
                    
                    if day_deep_sleep > 0:
                        exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'deep_sleep' for item in processed_data)
                        if not exists:
                            processed_data.append({
                                'date': prev_day_obj,
                                'metric_name': 'deep_sleep',
                                'metric_value': day_deep_sleep / 60,  # Convert seconds to minutes
                                'metric_units': 'minutes'
                            })
                    
                    if day_light_sleep > 0:
                        exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'light_sleep' for item in processed_data)
                        if not exists:
                            processed_data.append({
                                'date': prev_day_obj,
                                'metric_name': 'light_sleep',
                                'metric_value': day_light_sleep / 60,  # Convert seconds to minutes
                                'metric_units': 'minutes'
                            })
                    
                    if day_awake_time > 0:
                        exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'awake_time' for item in processed_data)
                        if not exists:
                            processed_data.append({
                                'date': prev_day_obj,
                                'metric_name': 'awake_time',
                                'metric_value': day_awake_time / 60,  # Convert seconds to minutes
                                'metric_units': 'minutes'
                            })
                    
                    if long_hr > 0:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'long_hr',
                            'metric_value': long_hr,
                            'metric_units': 'bpm'
                        })
                    
                    if long_hrv > 0:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'long_hrv',
                            'metric_value': long_hrv,
                            'metric_units': 'ms'
                        })
                    
                    if long_resp > 0:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'long_resp',
                            'metric_value': long_resp,
                            'metric_units': 'breaths_per_min'
                        })
                    
                    if long_efficiency > 0:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'long_efficiency',
                            'metric_value': long_efficiency,
                            'metric_units': 'score'
                        })
                    
                    if long_readiness > 0:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'long_readiness',
                            'metric_value': long_readiness,
                            'metric_units': 'score'
                        })
                
                # Reset for new day
                day_hr_data = []
                day_hrv_data = []
                day_hr_data2 = []
                day_hrv_data2 = []
                day_avg_resp = []
                day_time_asleep = []
                day_rem_sleep = 0
                day_deep_sleep = 0
                day_light_sleep = 0
                day_awake_time = 0
                long_hr = 0
                long_hrv = 0
                long_resp = 0
                long_efficiency = 0
                long_readiness = 0
            
            # Process heart rate data
            if sleep.get('heart_rate') is not None:
                hr_data = sleep['heart_rate'].get('items', [])
                day_hr_data.extend([x for x in hr_data if x is not None])
            
            # Process HRV data
            if sleep.get('hrv') is not None:
                hrv_data = sleep['hrv'].get('items', [])
                day_hrv_data.extend([x for x in hrv_data if x is not None])
            
            # Store weighted averages
            if (sleep.get('average_heart_rate') is not None and 
                sleep.get('average_hrv') is not None and 
                sleep.get('average_breath') is not None):
                
                day_hr_data2.append(sleep['average_heart_rate'])
                day_hrv_data2.append(sleep['average_hrv'])
                day_avg_resp.append(sleep['average_breath'])
                day_time_asleep.append(sleep.get('time_in_bed', 0))
            
            # Extract sleep stages from the individual sleep session
            if sleep.get('rem_sleep_duration') is not None:
                day_rem_sleep += sleep['rem_sleep_duration']
            
            if sleep.get('deep_sleep_duration') is not None:
                day_deep_sleep += sleep['deep_sleep_duration']
            
            if sleep.get('light_sleep_duration') is not None:
                day_light_sleep += sleep['light_sleep_duration']
            
            if sleep.get('awake_duration') is not None:
                day_awake_time += sleep['awake_duration']
            
            # Store info from the longest sleep session
            if sleep.get('type') == 'long_sleep':
                if sleep.get('average_hrv') is not None:
                    long_hrv = sleep['average_hrv']
                if sleep.get('average_heart_rate') is not None:
                    long_hr = sleep['average_heart_rate']
                if sleep.get('average_breath') is not None:
                    long_resp = sleep['average_breath']
                if sleep.get('efficiency') is not None:
                    long_efficiency = sleep['efficiency']
                if sleep.get('readiness', {}).get('score') is not None:
                    long_readiness = sleep['readiness']['score']
            
            prev_day = day
        
        # Process the last day's data
        if prev_day is not None:
            # Similar processing to within the loop
            avg_hr2 = 0
            avg_hrv2 = 0
            avg_resp = 0
            
            if day_time_asleep:  # Make sure we have data
                total_time_asleep = sum(day_time_asleep)
                for i in range(len(day_hr_data2)):
                    avg_hr2 += day_hr_data2[i] * (day_time_asleep[i] / total_time_asleep)
                    avg_hrv2 += day_hrv_data2[i] * (day_time_asleep[i] / total_time_asleep)
                    avg_resp += day_avg_resp[i] * (day_time_asleep[i] / total_time_asleep)
            
                # Convert previous day string to datetime
                try:
                    prev_day_obj = datetime.strptime(prev_day, "%Y-%m-%d").date()
                except ValueError:
                    current_app.logger.error(f"Invalid date format: {prev_day}")
                    return processed_data
            
                # Store metrics for the previous day
                if day_hr_data:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'avg_hr_alt',
                        'metric_value': sum(day_hr_data) / len(day_hr_data),
                        'metric_units': 'bpm'
                    })
                
                if day_hrv_data:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'avg_hrv_alt',
                        'metric_value': sum(day_hrv_data) / len(day_hrv_data),
                        'metric_units': 'ms'
                    })
                
                processed_data.append({
                    'date': prev_day_obj,
                    'metric_name': 'avg_hr',
                    'metric_value': avg_hr2,
                    'metric_units': 'bpm'
                })
                
                processed_data.append({
                    'date': prev_day_obj,
                    'metric_name': 'avg_hrv',
                    'metric_value': avg_hrv2,
                    'metric_units': 'ms'
                })
                
                processed_data.append({
                    'date': prev_day_obj,
                    'metric_name': 'avg_resp',
                    'metric_value': avg_resp,
                    'metric_units': 'breaths_per_min'
                })
                
                # Store sleep stage metrics from session data if they weren't in daily summary
                # We check if we already have data for this metric to avoid duplicates
                if day_rem_sleep > 0:
                    exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'rem_sleep' for item in processed_data)
                    if not exists:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'rem_sleep',
                            'metric_value': day_rem_sleep / 60,  # Convert seconds to minutes
                            'metric_units': 'minutes'
                        })
                
                if day_deep_sleep > 0:
                    exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'deep_sleep' for item in processed_data)
                    if not exists:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'deep_sleep',
                            'metric_value': day_deep_sleep / 60,  # Convert seconds to minutes
                            'metric_units': 'minutes'
                        })
                
                if day_light_sleep > 0:
                    exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'light_sleep' for item in processed_data)
                    if not exists:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'light_sleep',
                            'metric_value': day_light_sleep / 60,  # Convert seconds to minutes
                            'metric_units': 'minutes'
                        })
                
                if day_awake_time > 0:
                    exists = any(item.get('date') == prev_day_obj and item.get('metric_name') == 'awake_time' for item in processed_data)
                    if not exists:
                        processed_data.append({
                            'date': prev_day_obj,
                            'metric_name': 'awake_time',
                            'metric_value': day_awake_time / 60,  # Convert seconds to minutes
                            'metric_units': 'minutes'
                        })
                
                if long_hr > 0:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'long_hr',
                        'metric_value': long_hr,
                        'metric_units': 'bpm'
                    })
                
                if long_hrv > 0:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'long_hrv',
                        'metric_value': long_hrv,
                        'metric_units': 'ms'
                    })
                
                if long_resp > 0:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'long_resp',
                        'metric_value': long_resp,
                        'metric_units': 'breaths_per_min'
                    })
                
                if long_efficiency > 0:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'long_efficiency',
                        'metric_value': long_efficiency,
                        'metric_units': 'score'
                    })
                
                if long_readiness > 0:
                    processed_data.append({
                        'date': prev_day_obj,
                        'metric_name': 'long_readiness',
                        'metric_value': long_readiness,
                        'metric_units': 'score'
                    })
        
        return processed_data
    
    def _store_data(self, processed_data, source):
        """Store processed data in the database"""
        for item in processed_data:
            # Check if record already exists
            existing = HealthData.query.filter_by(
                date=item['date'],
                source=source,
                metric_name=item['metric_name']
            ).first()
            
            if existing:
                # Update existing record
                existing.metric_value = item['metric_value']
                existing.metric_units = item.get('metric_units')
            else:
                # Create new record
                new_data = HealthData(
                    date=item['date'],
                    source=source,
                    metric_name=item['metric_name'],
                    metric_value=item['metric_value'],
                    metric_units=item.get('metric_units')
                )
                db.session.add(new_data)
        
        db.session.commit()
    
    def _update_data_source(self, source_name):
        """Update or create a data source record"""
        source = DataSource.query.filter_by(name=source_name).first()
        
        if not source:
            source = DataSource(
                name=source_name,
                type='api',
                last_import=datetime.now()
            )
            db.session.add(source)
        else:
            source.last_import = datetime.now()
        
        db.session.commit()
    
    def import_activity_data(self, start_date, end_date):
        """Import activity data from Oura API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Get daily activity data
        daily_activity_data = self._get_data("/v2/usercollection/daily_activity", params)
        
        # Process and store the data
        processed_data = self._process_activity_data(daily_activity_data)
        self._store_data(processed_data, 'oura')
        
        # Update data source record
        self._update_data_source('oura_activity')
        
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
            
            # Store daily movement
            if 'daily_movement' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'daily_movement',
                    'metric_value': day['daily_movement'],
                    'metric_units': 'meters'
                })
            
            # Store inactive time
            if 'inactive_time' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'inactive_time',
                    'metric_value': day['inactive_time'],
                    'metric_units': 'seconds'
                })
            
            # Store rest time
            if 'rest_time' in day:
                processed_data.append({
                    'date': date_obj,
                    'metric_name': 'rest_time',
                    'metric_value': day['rest_time'],
                    'metric_units': 'seconds'
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
        
        return processed_data
    
    def _infer_units(self, metric_name):
        """Infer units for a metric based on its name."""
        if 'calories' in metric_name:
            return 'kcal'
        elif 'steps' in metric_name:
            return 'count'
        elif 'distance' in metric_name:
            return 'meters'
        elif 'duration' in metric_name or 'time' in metric_name:
            return 'seconds'
        elif 'score' in metric_name:
            return 'score'
        elif 'hr' in metric_name and 'hrv' not in metric_name:
            return 'bpm'
        elif 'hrv' in metric_name:
            return 'ms'
        elif 'breath' in metric_name or 'resp' in metric_name:
            return 'breaths_per_min'
        elif 'tag' in metric_name:
            return 'count'
        else:
            return None

    def import_tags_data(self, start_date, end_date):
        """Import tags data from Oura API
        
        Args:
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            
        Returns:
            List of processed tag data
        """
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
            self._store_data(processed_data, 'oura')
            
            # Update data source record
            self._update_data_source('oura_tags')
        
        return processed_data
    
    def _process_tags_data(self, tags_data, start_date=None, end_date=None):
        """Process raw Oura tag data into a format for our database
        
        Args:
            tags_data: Raw tag data from Oura API
            start_date: Start date for the data range (optional)
            end_date: End date for the data range (optional)
            
        Returns:
            List of processed tag data
        """
        processed_data = []
        
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
                    HealthData.metric_name
                ).filter(
                    HealthData.metric_name.like('tag_%'),
                    HealthData.source == 'oura'
                ).distinct().all()
                
                # Extract tag names from metric_names
                for tag_record in existing_tags:
                    if tag_record.metric_name.startswith('tag_'):
                        tag_name = tag_record.metric_name[4:]  # Remove 'tag_' prefix
                        unique_tags.add(tag_name)
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