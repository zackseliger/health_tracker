import os
import json
from unittest.mock import patch
from datetime import date, datetime

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app.models.base import HealthData, DataSource, ImportRecord
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

class OuraTagsTestCase(BaseTestCase):
    """Test case for Oura tag data import functionality"""
    
    def setUp(self):
        super().setUp()
        
        # Create mock tag data
        self.mock_tags_data = {
            "data": [
                {
                    "id": "123456",
                    "start_time": "2023-01-01T08:30:00+00:00",
                    "tag_type_code": "mood_great",
                    "comment": "Feeling great",
                    "mood_label": "great"
                },
                {
                    "id": "123457",
                    "start_time": "2023-01-01T14:30:00+00:00",
                    "tag_type_code": "mood_great",
                    "comment": "Still feeling great",
                    "mood_label": "great"
                },
                {
                    "id": "123458",
                    "start_time": "2023-01-01T20:30:00+00:00",
                    "tag_type_code": "stress_high",
                    "comment": "Feeling stressed",
                    "stress_label": "high"
                },
                {
                    "id": "123459",
                    "start_time": "2023-01-02T08:30:00+00:00",
                    "tag_type_code": "mood_good",
                    "comment": "Feeling good",
                    "mood_label": "good"
                },
                {
                    "id": "123460",
                    "start_time": "2023-01-02T14:30:00+00:00",
                    "tag_type_code": "stress_high",
                    "comment": "Stress level high",
                    "stress_label": "high"
                }
            ]
        }
        
    @patch('app.utils.oura_importer.requests.get')
    def test_import_tags_data(self, mock_get):
        """Test importing tag data from Oura"""
        
        # Set up the mock response
        mock_response = MockOuraResponse(json_data=self.mock_tags_data)
        mock_get.return_value = mock_response
        
        # Create an instance of OuraImporter
        importer = OuraImporter("test_token")
        
        # Import the tag data
        start_date = "2023-01-01"
        end_date = "2023-01-02"
        processed_data = importer.import_tags_data(start_date, end_date)
        
        # Verify that the correct endpoint was called
        mock_get.assert_called_with(
            "https://api.ouraring.com/v2/usercollection/enhanced_tag",
            headers={"Authorization": "Bearer test_token"},
            params={"start_date": start_date, "end_date": end_date}
        )
        
        # Verify that the tag data was processed correctly
        self.assertEqual(len(processed_data), 6)
        
        # Check that we have 2 entries for "mood_great" on 2023-01-01
        mood_great_entry = next(item for item in processed_data if item['metric_name'] == 'tag_mood_great')
        self.assertEqual(mood_great_entry['date'], datetime.strptime("2023-01-01", "%Y-%m-%d").date())
        self.assertEqual(mood_great_entry['metric_value'], 2)
        self.assertEqual(mood_great_entry['metric_units'], 'count')
        
        # Check that we have 1 entry for "stress_high" on 2023-01-01
        stress_high_entry_day1 = next(item for item in processed_data 
                                 if item['metric_name'] == 'tag_stress_high' and 
                                 item['date'] == datetime.strptime("2023-01-01", "%Y-%m-%d").date())
        self.assertEqual(stress_high_entry_day1['metric_value'], 1)
        
        # Check that we have correct entries in the database
        with self.app.app_context():
            # Verify that tags were added to the database
            tags_in_db = HealthData.query.filter(
                HealthData.metric_name.like('tag_%')
            ).all()
            
            self.assertEqual(len(tags_in_db), 4)
            
            # Verify that a data source record was created
            data_source = DataSource.query.filter_by(name='oura_tags').first()
            self.assertIsNotNone(data_source)
    
    @patch('app.utils.oura_importer.requests.get')
    def test_empty_tags_data(self, mock_get):
        """Test importing empty tag data from Oura"""
        
        # Set up the mock response with empty data
        mock_response = MockOuraResponse(json_data={"data": []})
        mock_get.return_value = mock_response
        
        # Create an instance of OuraImporter
        importer = OuraImporter("test_token")
        
        # Import the tag data
        start_date = "2023-01-01"
        end_date = "2023-01-02"
        processed_data = importer.import_tags_data(start_date, end_date)
        
        # Verify that the processed data is empty
        self.assertEqual(len(processed_data), 0)
    
    @patch('app.utils.oura_importer.requests.get')
    def test_invalid_timestamp_format(self, mock_get):
        """Test handling of invalid timestamp format"""
        
        # Create mock data with invalid timestamp
        invalid_data = {
            "data": [
                {
                    "id": "123456",
                    "timestamp": "invalid-timestamp",
                    "tag_type_code": "mood_great",
                    "text": "Feeling great",
                    "mood_label": "great"
                }
            ]
        }
        
        # Set up the mock response
        mock_response = MockOuraResponse(json_data=invalid_data)
        mock_get.return_value = mock_response
        
        # Create an instance of OuraImporter
        importer = OuraImporter("test_token")
        
        # Import the tag data
        start_date = "2023-01-01"
        end_date = "2023-01-02"
        processed_data = importer.import_tags_data(start_date, end_date)
        
        # Verify that the invalid data was skipped
        self.assertEqual(len(processed_data), 0)
    
    @patch('app.utils.oura_importer.requests.get')
    def test_days_with_zero_tags(self, mock_get):
        """Test that days with no tags are represented with a value of 0"""
        
        # Create mock data with gaps (no tags on Jan 3)
        gap_data = {
            "data": [
                {
                    "id": "123456",
                    "start_time": "2023-01-01T08:30:00+00:00",
                    "tag_type_code": "mood_great",
                    "comment": "Feeling great"
                },
                {
                    "id": "123457",
                    "start_time": "2023-01-02T14:30:00+00:00",
                    "tag_type_code": "mood_great",
                    "comment": "Still feeling great"
                },
                {
                    "id": "123458",
                    "start_time": "2023-01-04T20:30:00+00:00",
                    "tag_type_code": "mood_great",
                    "comment": "Feeling great again"
                }
            ]
        }
        
        # Set up the mock response
        mock_response = MockOuraResponse(json_data=gap_data)
        mock_get.return_value = mock_response
        
        # Create an instance of OuraImporter
        importer = OuraImporter("test_token")
        
        # Import the tag data for a date range that spans Jan 1-4
        start_date = "2023-01-01"
        end_date = "2023-01-04"
        processed_data = importer.import_tags_data(start_date, end_date)
        
        # There should be data for all 4 days (Jan 1-4) for the mood_great tag
        # Verify that the processed data contains entries for all days
        self.assertEqual(len(processed_data), 4)  # One entry per day
        
        # Create a dictionary to check each day's tag count
        day_counts = {}
        for item in processed_data:
            if item['metric_name'] == 'tag_mood_great':
                day_counts[item['date']] = item['metric_value']
        
        # Verify counts for each day
        jan1 = datetime.strptime("2023-01-01", "%Y-%m-%d").date()
        jan2 = datetime.strptime("2023-01-02", "%Y-%m-%d").date()
        jan3 = datetime.strptime("2023-01-03", "%Y-%m-%d").date()
        jan4 = datetime.strptime("2023-01-04", "%Y-%m-%d").date()
        
        self.assertEqual(day_counts[jan1], 1)  # One tag on Jan 1
        self.assertEqual(day_counts[jan2], 1)  # One tag on Jan 2
        self.assertEqual(day_counts[jan3], 0)  # Zero tags on Jan 3
        self.assertEqual(day_counts[jan4], 1)  # One tag on Jan 4 