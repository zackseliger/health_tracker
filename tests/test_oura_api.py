import os
import unittest
import json
from unittest.mock import patch
from datetime import date

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app.models.base import HealthData, ImportRecord, DataType
from app.utils.oura_importer import OuraImporter
from app import db

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
                    "rem_sleep_duration": 5400,
                    "deep_sleep_duration": 7200,
                    "light_sleep_duration": 14400,
                    "awake_duration": 1800
                },
                {
                    "day": "2023-01-02",
                    "score": 78,
                    "rem_sleep_duration": 4800,
                    "deep_sleep_duration": 6600,
                    "light_sleep_duration": 12000,
                    "awake_duration": 1800
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
        
        # Mock stress data
        self.mock_stress_data = {
            "data": [
                {
                    "id": "abc123",
                    "day": "2023-01-01",
                    "stress_high": 65,
                    "recovery_high": 35,
                    "day_summary": "strained"
                },
                {
                    "id": "def456",
                    "day": "2023-01-02",
                    "stress_high": 45,
                    "recovery_high": 55,
                    "day_summary": "balanced"
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
        """Test importing sleep data from the Oura API."""
        # Create two different mock responses for the two API calls
        # First call is for daily sleep data, second is for detailed sleep data
        mock_get.side_effect = [
            MockOuraResponse(json_data=self.mock_daily_sleep_data),
            MockOuraResponse(json_data=self.mock_sleep_data)
        ]
        
        # Initialize the importer
        importer = OuraImporter(self.personal_token)
        
        # Import data
        result = importer.import_sleep_data(self.start_date, self.end_date)
        
        # Verify the result is a list of processed data points
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify data was imported correctly (test a sample of metrics)
        # First, get the DataType objects for the metrics we want to check
        sleep_score_type = DataType.query.filter_by(
            source='oura',
            metric_name='sleep_score'
        ).first()
        
        # Check for any sleep-related metric that should be created
        sleep_metrics = DataType.query.filter(
            DataType.source == 'oura',
            DataType.metric_name.like('sleep%')
        ).all()
        
        # Verify that we have at least one sleep-related metric
        self.assertGreater(len(sleep_metrics), 0)

        rem_sleep_metrics = DataType.query.filter(
            DataType.source == 'oura',
            DataType.metric_name == 'rem_sleep'
        ).all()
        
        # Verify we have a DataType for rem_sleep
        self.assertEqual(len(rem_sleep_metrics), 1)
        
        # Verify we have 2 data points for rem_sleep (one for each day)
        rem_sleep_data = HealthData.query.filter_by(
            data_type_id=rem_sleep_metrics[0].id
        ).all()
        self.assertEqual(len(rem_sleep_data), 2)
        
        # Verify the DataType objects exist
        self.assertIsNotNone(sleep_score_type)
        
        # Check that we have data for the sleep score
        sleep_score_data = HealthData.query.filter_by(
            data_type_id=sleep_score_type.id
        ).all()
        self.assertGreater(len(sleep_score_data), 0)
        
        # Check that a data source was added
        source = DataType.query.filter_by(source='oura', metric_name='source_info').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.source_type, 'api')
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_activity_data(self, mock_get):
        """Test importing activity data from the Oura API."""
        # Create a mock response with test data
        mock_get.return_value = MockOuraResponse(json_data=self.mock_activity_data)
        
        # Initialize the importer
        importer = OuraImporter(self.personal_token)
        
        # Import data
        result = importer.import_activity_data(self.start_date, self.end_date)
        
        # Verify the result is a list of processed data points
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify data was imported correctly (test a sample of metrics)
        # First, get the DataType objects for the metrics we want to check
        steps_type = DataType.query.filter_by(
            source='oura',
            metric_name='steps'
        ).first()
        
        # Check for any activity-related metric that should be created
        activity_metrics = DataType.query.filter(
            DataType.source == 'oura',
            DataType.metric_name.like('activity%')
        ).all()
        
        # Verify that we have at least one activity-related metric
        self.assertGreater(len(activity_metrics), 0)
        
        # Verify the DataType objects exist
        self.assertIsNotNone(steps_type)
        
        # Check that we have data for steps
        steps_data = HealthData.query.filter_by(
            data_type_id=steps_type.id
        ).all()
        self.assertGreater(len(steps_data), 0)
        
        # Check that a data source was added
        source = DataType.query.filter_by(source='oura', metric_name='source_info').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.source_type, 'api')
    
    @patch('app.utils.oura_importer.requests.get')
    def test_import_stress_data(self, mock_get):
        """Test importing stress data from the Oura API."""
        # Create a mock response with test data
        mock_get.return_value = MockOuraResponse(json_data=self.mock_stress_data)
        
        # Initialize the importer
        importer = OuraImporter(self.personal_token)
        
        # Import data
        result = importer.import_stress_data(self.start_date, self.end_date)
        
        # Verify the result is a list of processed data points
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify data was imported correctly (test a sample of metrics)
        # First, get the DataType objects for the metrics we want to check
        stress_high_type = DataType.query.filter_by(
            source='oura',
            metric_name='stress_high'
        ).first()
        
        recovery_high_type = DataType.query.filter_by(
            source='oura',
            metric_name='recovery_high'
        ).first()
        
        # Verify the DataType objects exist
        self.assertIsNotNone(stress_high_type)
        self.assertIsNotNone(recovery_high_type)
        
        # Check that we have data for stress_high and recovery_high
        stress_high_data = HealthData.query.filter_by(
            data_type_id=stress_high_type.id
        ).all()
        self.assertEqual(len(stress_high_data), 2)  # Should have 2 days of data
        
        recovery_high_data = HealthData.query.filter_by(
            data_type_id=recovery_high_type.id
        ).all()
        self.assertEqual(len(recovery_high_data), 2)  # Should have 2 days of data
        
        # Check the values
        self.assertEqual(stress_high_data[0].metric_value, 65)
        self.assertEqual(stress_high_data[1].metric_value, 45)
        self.assertEqual(recovery_high_data[0].metric_value, 35)
        self.assertEqual(recovery_high_data[1].metric_value, 55)
        
        # Check that a data source was added
        source = DataType.query.filter_by(source='oura', metric_name='source_info').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.source_type, 'api')
    
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
        # Configure mock responses for different data types
        mock_responses = {
            'sleep': [
                MockOuraResponse(json_data=self.mock_daily_sleep_data),
                MockOuraResponse(json_data=self.mock_sleep_data)
            ],
            'activity': [MockOuraResponse(json_data=self.mock_activity_data)],
            'stress': [MockOuraResponse(json_data=self.mock_stress_data)]
        }
        
        for data_type, responses in mock_responses.items():
            # Reset mock and set responses for this test
            mock_get.reset_mock()
            mock_get.side_effect = responses
        
            # Mock session data
            with self.client.session_transaction() as session:
                session['oura_connected'] = True
                session['oura_personal_token'] = self.personal_token
            
            # Test the import route with valid data
            response = self.client.post('/data/import/oura', data={
                'start_date': self.start_date,
                'end_date': self.end_date,
                'data_type': data_type
            }, follow_redirects=True)
            
            # Check that the import was successful
            self.assertEqual(response.status_code, 200)
            
            # Verify import record was created
            import_record = ImportRecord.query.filter_by(source='oura').first()
            self.assertIsNotNone(import_record)
            self.assertEqual(import_record.status, 'success')
            self.assertEqual(import_record.date_range_start, date(2023, 1, 1))
            self.assertEqual(import_record.date_range_end, date(2023, 1, 7))
            
            # Clear records for next test
            db.session.query(ImportRecord).delete()
            db.session.query(HealthData).delete()
            db.session.query(DataType).delete()
            db.session.commit()

if __name__ == '__main__':
    unittest.main() 