import os
import unittest
import json
from unittest.mock import patch
from datetime import date, datetime

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app.models.base import HealthData, DataSource, ImportRecord
from app.utils.oura_importer import OuraImporter
from app.utils.analyzer import HealthAnalyzer
from app import db  # Add the db import

class MockOuraResponse:
    """Mock response object for testing"""
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.json_data = json_data or {}
        self.text = json.dumps(json_data)
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP Error: {self.status_code}")

class SleepStagesTestCase(BaseTestCase):
    """Test case for sleep stages metrics."""
    
    def setUp(self):
        super().setUp()
        
        # Create test data
        self.personal_token = "test_personal_token"
        self.start_date = "2023-01-01"
        self.end_date = "2023-01-07"
        
        # Mock API responses with complex sleep data over multiple days
        self.mock_daily_sleep_data = {
            "data": [
                {
                    "day": "2023-01-01",
                    "score": 85,
                    "rem_sleep_duration": 5400,  # 90 minutes in seconds
                    "deep_sleep_duration": 7200,  # 120 minutes in seconds
                    "light_sleep_duration": 14400,  # 240 minutes in seconds
                    "awake_duration": 1800  # 30 minutes in seconds
                },
                {
                    "day": "2023-01-02",
                    "score": 78,
                    "rem_sleep_duration": 4800,  # 80 minutes in seconds
                    "deep_sleep_duration": 6600,  # 110 minutes in seconds
                    "light_sleep_duration": 12000,  # 200 minutes in seconds
                    "awake_duration": 1800  # 30 minutes in seconds
                },
                {
                    "day": "2023-01-03",
                    "score": 92,
                    "rem_sleep_duration": 6000,  # 100 minutes in seconds
                    "deep_sleep_duration": 7800,  # 130 minutes in seconds
                    "light_sleep_duration": 15000,  # 250 minutes in seconds
                    "awake_duration": 1200  # 20 minutes in seconds
                }
            ]
        }
        
        # First day has a single sleep session
        # Second day has a main sleep session and a nap
        # Third day has a main sleep session with unusual values
        self.mock_sleep_data = {
            "data": [
                {
                    "day": "2023-01-01",
                    "score": 85,
                    "average_hrv": 45,
                    "average_heart_rate": 58,
                    "average_breath": 15.5,
                    "time_in_bed": 28800,  # 8 hours in seconds
                    "rem_sleep_duration": 5400,  # 90 minutes in seconds
                    "deep_sleep_duration": 7200,  # 120 minutes in seconds
                    "light_sleep_duration": 14400,  # 240 minutes in seconds
                    "awake_duration": 1800,  # 30 minutes in seconds
                    "type": "long_sleep"
                },
                {
                    "day": "2023-01-02",
                    "score": 78,
                    "average_hrv": 42,
                    "average_heart_rate": 60,
                    "average_breath": 16.0,
                    "time_in_bed": 25200,  # 7 hours in seconds
                    "rem_sleep_duration": 4500,  # 75 minutes in seconds
                    "deep_sleep_duration": 6300,  # 105 minutes in seconds
                    "light_sleep_duration": 11400,  # 190 minutes in seconds
                    "awake_duration": 1800,  # 30 minutes in seconds
                    "type": "long_sleep"
                },
                {
                    "day": "2023-01-02",
                    "score": 78,
                    "average_hrv": 45,
                    "average_heart_rate": 55,
                    "average_breath": 14.5,
                    "time_in_bed": 3600,  # 1 hour nap in seconds
                    "rem_sleep_duration": 300,  # 5 minutes in seconds
                    "deep_sleep_duration": 300,  # 5 minutes in seconds
                    "light_sleep_duration": 600,  # 10 minutes in seconds
                    "awake_duration": 0,  # 0 minutes in seconds
                    "type": "short_sleep"
                },
                {
                    "day": "2023-01-03",
                    "score": 92,
                    "average_hrv": 50,
                    "average_heart_rate": 55,
                    "average_breath": 14.0,
                    "time_in_bed": 30600,  # 8.5 hours in seconds
                    "rem_sleep_duration": 6000,  # 100 minutes in seconds
                    "deep_sleep_duration": 7800,  # 130 minutes in seconds
                    "light_sleep_duration": 15000,  # 250 minutes in seconds
                    "awake_duration": 1200,  # 20 minutes in seconds
                    "type": "long_sleep"
                }
            ]
        }
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_sleep_stages(self, mock_get):
        """Test importing sleep stages data from Oura API."""
        # Configure the mock responses
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Create the importer and import data
        importer = OuraImporter(personal_token=self.personal_token)
        processed_data = importer.import_sleep_data(self.start_date, self.end_date)
        
        # Check that sleep stage metrics were processed correctly
        # Find the REM sleep entries for all days
        rem_entries = [item for item in processed_data if item['metric_name'] == 'rem_sleep']
        self.assertEqual(len(rem_entries), 3)  # One for each day
        
        # Check day 1 values
        day1_rem = next(item for item in rem_entries if item['date'] == datetime.strptime("2023-01-01", "%Y-%m-%d").date())
        self.assertEqual(day1_rem['metric_value'], 90)  # 5400 seconds = 90 minutes
        
        # Check day 2 values (combined from main sleep + nap)
        day2_rem = next(item for item in rem_entries if item['date'] == datetime.strptime("2023-01-02", "%Y-%m-%d").date())
        # The value should come from the daily sleep data, which is 80 minutes
        self.assertEqual(day2_rem['metric_value'], 80)  # 4800 seconds = 80 minutes
        
        # Check day 3 values
        day3_rem = next(item for item in rem_entries if item['date'] == datetime.strptime("2023-01-03", "%Y-%m-%d").date())
        self.assertEqual(day3_rem['metric_value'], 100)  # 6000 seconds = 100 minutes
        
        # Check that data was added to the database
        db_rem_sleep = HealthData.query.filter_by(
            source='oura',
            metric_name='rem_sleep'
        ).all()
        
        self.assertEqual(len(db_rem_sleep), 3)
        
        # Sort by date to ensure consistent order
        db_rem_sleep.sort(key=lambda x: x.date)
        
        self.assertEqual(db_rem_sleep[0].date, date(2023, 1, 1))
        self.assertEqual(db_rem_sleep[0].metric_value, 90)
        self.assertEqual(db_rem_sleep[0].metric_units, 'minutes')
        
        self.assertEqual(db_rem_sleep[1].date, date(2023, 1, 2))
        self.assertEqual(db_rem_sleep[1].metric_value, 80)
        self.assertEqual(db_rem_sleep[1].metric_units, 'minutes')
        
        self.assertEqual(db_rem_sleep[2].date, date(2023, 1, 3))
        self.assertEqual(db_rem_sleep[2].metric_value, 100)
        self.assertEqual(db_rem_sleep[2].metric_units, 'minutes')
    
    @patch('app.utils.oura_importer.requests.get')
    def test_sleep_stages_consistency(self, mock_get):
        """Test the consistency of sleep stage metrics."""
        # Configure the mock responses
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Create the importer and import data
        importer = OuraImporter(personal_token=self.personal_token)
        processed_data = importer.import_sleep_data(self.start_date, self.end_date)
        
        # For each day, verify that the sum of sleep stages is close to the total time in bed
        # (allowing for rounding errors and small discrepancies)
        
        # Group data by date
        data_by_date = {}
        for item in processed_data:
            date_str = item['date'].strftime("%Y-%m-%d")
            if date_str not in data_by_date:
                data_by_date[date_str] = {}
            data_by_date[date_str][item['metric_name']] = item['metric_value']
        
        for date_str, metrics in data_by_date.items():
            if all(key in metrics for key in ['rem_sleep', 'deep_sleep', 'light_sleep', 'awake_time']):
                total_sleep_time = metrics['rem_sleep'] + metrics['deep_sleep'] + metrics['light_sleep'] + metrics['awake_time']
                
                # Find the corresponding time_in_bed from the mock data
                day_data = next((d for d in self.mock_sleep_data['data'] 
                                 if d['day'] == date_str and d['type'] == 'long_sleep'), None)
                
                if day_data:
                    time_in_bed_minutes = day_data['time_in_bed'] / 60
                    # Allow for larger discrepancies (e.g., < 20 minutes or < 5%)
                    # Some discrepancy is expected due to rounding and data processing
                    self.assertLess(abs(total_sleep_time - time_in_bed_minutes), 
                                     max(20, time_in_bed_minutes * 0.05))
    
    @patch('app.utils.oura_importer.requests.get')
    def test_analyzer_with_sleep_stages(self, mock_get):
        """Test the analyzer with sleep stage metrics."""
        # Configure the mock responses
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Create the importer and import data
        importer = OuraImporter(personal_token=self.personal_token)
        importer.import_sleep_data(self.start_date, self.end_date)
        
        # Create an analyzer and get sleep stage metrics
        analyzer = HealthAnalyzer()
        
        # Check if the metrics are available
        metrics = analyzer.get_available_metrics()
        metric_names = [m['metric_name'] for m in metrics if m['source'] == 'oura']
        
        self.assertIn('rem_sleep', metric_names)
        self.assertIn('deep_sleep', metric_names)
        self.assertIn('light_sleep', metric_names)
        self.assertIn('awake_time', metric_names)
        
        # Get REM sleep data
        rem_data = analyzer.get_metric_data('rem_sleep', 'oura')
        self.assertEqual(len(rem_data), 3)  # 3 days of data
        
        # Get deep sleep data
        deep_data = analyzer.get_metric_data('deep_sleep', 'oura')
        self.assertEqual(len(deep_data), 3)  # 3 days of data
        
        # Get light sleep data
        light_data = analyzer.get_metric_data('light_sleep', 'oura')
        self.assertEqual(len(light_data), 3)  # 3 days of data
        
        # Get awake time data
        awake_data = analyzer.get_metric_data('awake_time', 'oura')
        self.assertEqual(len(awake_data), 3)  # 3 days of data
        
        # Calculate the correlation between REM sleep and deep sleep
        # We need to set min_pairs lower since we only have 3 days of data
        correlation = analyzer.calculate_correlation(
            'rem_sleep', 'oura',
            'deep_sleep', 'oura',
            min_pairs=3  # Set minimum pairs to 3 since we only have 3 days of data
        )
        
        # Check that correlation calculation worked
        self.assertIn('correlation', correlation)
        self.assertIn('coefficient', correlation['correlation'])
    
    def test_sleep_stage_metrics_in_database(self):
        """Test that sleep stage metrics are correctly stored and retrievable from the database."""
        # Create some test data directly in the database
        test_data = [
            HealthData(
                date=date(2023, 1, 1),
                source='oura',
                metric_name='rem_sleep',
                metric_value=90,
                metric_units='minutes'
            ),
            HealthData(
                date=date(2023, 1, 1),
                source='oura',
                metric_name='deep_sleep',
                metric_value=120,
                metric_units='minutes'
            ),
            HealthData(
                date=date(2023, 1, 1),
                source='oura',
                metric_name='light_sleep',
                metric_value=240,
                metric_units='minutes'
            ),
            HealthData(
                date=date(2023, 1, 1),
                source='oura',
                metric_name='awake_time',
                metric_value=30,
                metric_units='minutes'
            )
        ]
        
        # Add the data to the database
        db.session.add_all(test_data)
        db.session.commit()
        
        # Create an analyzer and check if it can retrieve the data
        analyzer = HealthAnalyzer()
        
        # Get all metrics for the test date
        metrics_df = analyzer.get_metric_dataframe(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 1)
        )
        
        # Check if the sleep stage metrics are in the dataframe
        self.assertIn('oura:rem_sleep', metrics_df.columns)
        self.assertIn('oura:deep_sleep', metrics_df.columns)
        self.assertIn('oura:light_sleep', metrics_df.columns)
        self.assertIn('oura:awake_time', metrics_df.columns)
        
        # Check the values
        self.assertEqual(metrics_df['oura:rem_sleep'].iloc[0], 90)
        self.assertEqual(metrics_df['oura:deep_sleep'].iloc[0], 120)
        self.assertEqual(metrics_df['oura:light_sleep'].iloc[0], 240)
        self.assertEqual(metrics_df['oura:awake_time'].iloc[0], 30)


if __name__ == '__main__':
    unittest.main() 