import os
import unittest
import json
from unittest.mock import patch
from datetime import date

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app.models.base import HealthData, DataSource, ImportRecord
from app.utils.oura_importer import OuraImporter

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

class OuraAPITestCase(BaseTestCase):
    """Test case for the Oura API integration using personal token."""
    
    def setUp(self):
        super().setUp()
        # Create test data
        self.personal_token = "test_personal_token"
        self.start_date = "2023-01-01"
        self.end_date = "2023-01-07"
        
        # Mock API responses
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
                    "rem_sleep_duration": 4800,  # 80 minutes in seconds
                    "deep_sleep_duration": 6600,  # 110 minutes in seconds
                    "light_sleep_duration": 12000,  # 200 minutes in seconds
                    "awake_duration": 1800,  # 30 minutes in seconds
                    "type": "long_sleep"
                }
            ]
        }
        
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
                }
            ]
        }
        
        self.mock_activity_data = {
            "data": [
                {
                    "day": "2023-01-01",
                    "score": 90,
                    "active_calories": 350,
                    "total_calories": 2100,
                    "steps": 8500,
                    "equivalent_walking_distance": 6500,
                    "daily_movement": 7200,
                    "inactive_time": 28800,  # 8 hours in seconds
                    "rest_time": 28800,  # 8 hours in seconds
                    "met": {
                        "average": 1.4,
                        "min": 0.9,
                        "max": 4.2
                    }
                },
                {
                    "day": "2023-01-02",
                    "score": 85,
                    "active_calories": 320,
                    "total_calories": 2050,
                    "steps": 7800,
                    "equivalent_walking_distance": 6000,
                    "daily_movement": 6800,
                    "inactive_time": 32400,  # 9 hours in seconds
                    "rest_time": 25200,  # 7 hours in seconds
                    "met": {
                        "average": 1.3,
                        "min": 0.9,
                        "max": 3.8
                    }
                }
            ]
        }
    
    @patch('app.utils.oura_importer.requests.get')
    def test_oura_importer_init(self, mock_get):
        """Test OuraImporter initialization with personal token."""
        importer = OuraImporter(personal_token=self.personal_token)
        self.assertEqual(importer.personal_token, self.personal_token)
        self.assertEqual(importer.api_base_url, "https://api.ouraring.com")
        self.assertEqual(importer.auth_header, {'Authorization': f'Bearer {self.personal_token}'})
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_sleep_data(self, mock_get):
        """Test importing sleep data from Oura API with personal token."""
        # Configure the mock responses
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Create the importer and import data
        importer = OuraImporter(personal_token=self.personal_token)
        processed_data = importer.import_sleep_data(self.start_date, self.end_date)
        
        # Check that the correct API endpoints were called
        mock_get.assert_any_call(
            f"{importer.api_base_url}/v2/usercollection/daily_sleep",
            headers=importer.auth_header,
            params={"start_date": self.start_date, "end_date": self.end_date}
        )
        
        mock_get.assert_any_call(
            f"{importer.api_base_url}/v2/usercollection/sleep",
            headers=importer.auth_header,
            params={"start_date": self.start_date, "end_date": self.end_date}
        )
        
        # Verify that data was processed correctly
        self.assertGreater(len(processed_data), 0)
        
        # Check that data was added to the database
        sleep_scores = HealthData.query.filter_by(
            source='oura',
            metric_name='sleep_score'
        ).all()
        
        self.assertEqual(len(sleep_scores), 2)
        self.assertEqual(sleep_scores[0].date, date(2023, 1, 1))
        self.assertEqual(sleep_scores[0].metric_value, 85)
        
        # Check that the new sleep metrics were added
        rem_sleep = HealthData.query.filter_by(
            source='oura',
            metric_name='rem_sleep'
        ).all()
        
        self.assertEqual(len(rem_sleep), 2)
        self.assertEqual(rem_sleep[0].date, date(2023, 1, 1))
        self.assertEqual(rem_sleep[0].metric_value, 90)  # 5400 seconds = 90 minutes
        self.assertEqual(rem_sleep[0].metric_units, 'minutes')
        
        deep_sleep = HealthData.query.filter_by(
            source='oura',
            metric_name='deep_sleep'
        ).all()
        
        self.assertEqual(len(deep_sleep), 2)
        self.assertEqual(deep_sleep[0].date, date(2023, 1, 1))
        self.assertEqual(deep_sleep[0].metric_value, 120)  # 7200 seconds = 120 minutes
        self.assertEqual(deep_sleep[0].metric_units, 'minutes')
        
        light_sleep = HealthData.query.filter_by(
            source='oura',
            metric_name='light_sleep'
        ).all()
        
        self.assertEqual(len(light_sleep), 2)
        self.assertEqual(light_sleep[0].date, date(2023, 1, 1))
        self.assertEqual(light_sleep[0].metric_value, 240)  # 14400 seconds = 240 minutes
        self.assertEqual(light_sleep[0].metric_units, 'minutes')
        
        awake_time = HealthData.query.filter_by(
            source='oura',
            metric_name='awake_time'
        ).all()
        
        self.assertEqual(len(awake_time), 2)
        self.assertEqual(awake_time[0].date, date(2023, 1, 1))
        self.assertEqual(awake_time[0].metric_value, 30)  # 1800 seconds = 30 minutes
        self.assertEqual(awake_time[0].metric_units, 'minutes')
        
        # Check that a data source was added
        source = DataSource.query.filter_by(name='oura_sleep').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.type, 'api')
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_activity_data(self, mock_get):
        """Test importing activity data from Oura API with personal token."""
        # Configure the mock response
        mock_get.return_value = MockOuraResponse(json_data=self.mock_activity_data)
        
        # Create the importer and import data
        importer = OuraImporter(personal_token=self.personal_token)
        processed_data = importer.import_activity_data(self.start_date, self.end_date)
        
        # Check that the correct API endpoint was called
        mock_get.assert_called_with(
            f"{importer.api_base_url}/v2/usercollection/daily_activity",
            headers=importer.auth_header,
            params={"start_date": self.start_date, "end_date": self.end_date}
        )
        
        # Verify that data was processed correctly
        self.assertGreater(len(processed_data), 0)
        
        # Check that data was added to the database
        activity_scores = HealthData.query.filter_by(
            source='oura',
            metric_name='activity_score'
        ).all()
        
        self.assertEqual(len(activity_scores), 2)
        self.assertEqual(activity_scores[0].date, date(2023, 1, 1))
        self.assertEqual(activity_scores[0].metric_value, 90)
        
        steps = HealthData.query.filter_by(
            source='oura',
            metric_name='steps'
        ).all()
        
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].date, date(2023, 1, 1))
        self.assertEqual(steps[0].metric_value, 8500)
        
        # Check MET values
        avg_met = HealthData.query.filter_by(
            source='oura',
            metric_name='average_met'
        ).all()
        
        self.assertEqual(len(avg_met), 2)
        self.assertEqual(avg_met[0].date, date(2023, 1, 1))
        self.assertEqual(avg_met[0].metric_value, 1.4)
        
        # Check that a data source was added
        source = DataSource.query.filter_by(name='oura_activity').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.type, 'api')

    def test_connect_oura_form(self):
        """Test the form for entering an Oura personal token."""
        response = self.client.get('/data/connect/oura')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Personal Access Token', response.data)
    
    def test_submit_oura_token(self):
        """Test submitting an Oura personal token."""
        response = self.client.post('/data/connect/oura', data={
            'personal_token': self.personal_token
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that session variables were set correctly
        with self.client.session_transaction() as session:
            self.assertEqual(session.get('oura_personal_token'), self.personal_token)
            self.assertTrue(session.get('oura_connected'))
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_oura_route(self, mock_get):
        """Test the import Oura data route with personal token."""
        # Configure mock responses
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Mock session data
        with self.client.session_transaction() as session:
            session['oura_connected'] = True
            session['oura_personal_token'] = self.personal_token
        
        # Test the import route with valid data
        response = self.client.post('/data/import/oura', data={
            'start_date': self.start_date,
            'end_date': self.end_date,
            'data_type': 'sleep'
        }, follow_redirects=True)
        
        # Check that the import was successful
        self.assertEqual(response.status_code, 200)
        
        # Verify import record was created
        import_record = ImportRecord.query.filter_by(source='oura_sleep').first()
        self.assertIsNotNone(import_record)
        self.assertEqual(import_record.status, 'success')
        self.assertEqual(import_record.date_range_start, date(2023, 1, 1))
        self.assertEqual(import_record.date_range_end, date(2023, 1, 7))
        
if __name__ == '__main__':
    unittest.main() 