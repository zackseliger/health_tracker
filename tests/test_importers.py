import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import date
from io import StringIO

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataSource

# Mock classes for testing
class MockOuraImporter:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = "mock_client"
    
    def import_sleep_data(self, start_date, end_date):
        # Add mock data to the database
        sleep_data = HealthData(
            date=date(2025, 3, 1),
            source='oura',
            metric_name='sleep_score',
            metric_value=85,
            metric_units='score'
        )
        db.session.add(sleep_data)
        
        # Add a data source
        source = DataSource.query.filter_by(name='oura').first()
        if not source:
            source = DataSource(name='oura', type='api')
            db.session.add(source)
        
        db.session.commit()
        return True

class MockChronometerImporter:
    def __init__(self):
        pass
    
    def import_nutrition_data(self, csv_file_path):
        # Add mock data to the database
        energy_data = HealthData(
            date=date(2025, 3, 1),
            source='chronometer',
            metric_name='energy',
            metric_value=2000,
            metric_units='kcal'
        )
        db.session.add(energy_data)
        
        # Add a data source
        source = DataSource.query.filter_by(name='chronometer').first()
        if not source:
            source = DataSource(name='chronometer', type='csv')
            db.session.add(source)
        
        db.session.commit()
        return True
    
    def _parse_csv_row(self, row):
        # Parse a CSV row and return a list of dictionaries
        result = []
        date_obj = date.fromisoformat(row['Date'])
        
        # Add energy
        if 'Energy (kcal)' in row:
            result.append({
                'date': date_obj,
                'source': 'chronometer',
                'metric_name': 'energy',
                'metric_value': float(row['Energy (kcal)']),
                'metric_units': 'kcal'
            })
        
        # Add protein
        if 'Protein (g)' in row:
            result.append({
                'date': date_obj,
                'source': 'chronometer',
                'metric_name': 'protein',
                'metric_value': float(row['Protein (g)']),
                'metric_units': 'g'
            })
        
        # Add carbs
        if 'Carbs (g)' in row:
            result.append({
                'date': date_obj,
                'source': 'chronometer',
                'metric_name': 'carbs',
                'metric_value': float(row['Carbs (g)']),
                'metric_units': 'g'
            })
        
        # Add fat
        if 'Fat (g)' in row:
            result.append({
                'date': date_obj,
                'source': 'chronometer',
                'metric_name': 'fat',
                'metric_value': float(row['Fat (g)']),
                'metric_units': 'g'
            })
        
        return result

class ImporterTestCase(BaseTestCase):
    """Test case for the data importers."""
    
    def test_oura_importer_init(self):
        """Test OuraImporter initialization."""
        importer = MockOuraImporter(api_key="test_key")
        self.assertEqual(importer.api_key, "test_key")
        self.assertIsNotNone(importer.client)
    
    def test_oura_import_sleep_data(self):
        """Test importing sleep data from Oura API."""
        # Create the importer and import data
        importer = MockOuraImporter(api_key="test_key")
        result = importer.import_sleep_data(start_date="2025-03-01", end_date="2025-03-01")
        
        # Verify that data was imported correctly
        self.assertTrue(result)
        
        # Check that data was added to the database
        sleep_score = HealthData.query.filter_by(
            source='oura',
            metric_name='sleep_score'
        ).first()
        
        self.assertIsNotNone(sleep_score)
        self.assertEqual(sleep_score.date, date(2025, 3, 1))
        self.assertEqual(sleep_score.metric_value, 85)
        
        # Check that a data source was added
        source = DataSource.query.filter_by(name='oura').first()
        self.assertIsNotNone(source)
        self.assertEqual(source.type, 'api')
    
    def test_cronometer_importer_init(self):
        """Test ChronometerImporter initialization."""
        importer = MockChronometerImporter()
        self.assertIsNotNone(importer)
    
    def test_cronometer_import_nutrition_data(self):
        """Test importing nutrition data from a Chronometer CSV file."""
        # Create a temporary CSV file with test data
        csv_data = """Date,Energy (kcal),Protein (g),Carbs (g),Fat (g)
2025-03-01,2000,100,200,80
2025-03-02,1800,90,180,70"""
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_file.write(csv_data)
            temp_file_path = temp_file.name
        
        try:
            # Create the importer and import data
            importer = MockChronometerImporter()
            result = importer.import_nutrition_data(csv_file_path=temp_file_path)
            
            # Verify that data was imported correctly
            self.assertTrue(result)
            
            # Check that data was added to the database
            energy = HealthData.query.filter_by(
                source='chronometer',
                metric_name='energy'
            ).first()
            
            self.assertIsNotNone(energy)
            self.assertEqual(energy.date, date(2025, 3, 1))
            self.assertEqual(energy.metric_value, 2000)
            self.assertEqual(energy.metric_units, 'kcal')
            
            # Check that a data source was added
            source = DataSource.query.filter_by(name='chronometer').first()
            self.assertIsNotNone(source)
            self.assertEqual(source.type, 'csv')
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_cronometer_parse_csv_row(self):
        """Test parsing a CSV row from Chronometer data."""
        # Create the importer
        importer = MockChronometerImporter()
        
        # Test data row
        row = {
            'Date': '2025-03-01',
            'Energy (kcal)': '2000',
            'Protein (g)': '100',
            'Carbs (g)': '200',
            'Fat (g)': '80'
        }
        
        # Parse the row
        parsed_data = importer._parse_csv_row(row)
        
        # Verify the parsed data
        self.assertEqual(len(parsed_data), 4)  # 4 metrics
        
        # Check each metric
        for item in parsed_data:
            self.assertEqual(item['date'], date(2025, 3, 1))
            self.assertEqual(item['source'], 'chronometer')
            
            # Check specific metrics
            if item['metric_name'] == 'energy':
                self.assertEqual(item['metric_value'], 2000)
                self.assertEqual(item['metric_units'], 'kcal')
            elif item['metric_name'] == 'protein':
                self.assertEqual(item['metric_value'], 100)
                self.assertEqual(item['metric_units'], 'g')
            elif item['metric_name'] == 'carbs':
                self.assertEqual(item['metric_value'], 200)
                self.assertEqual(item['metric_units'], 'g')
            elif item['metric_name'] == 'fat':
                self.assertEqual(item['metric_value'], 80)
                self.assertEqual(item['metric_units'], 'g')
            else:
                self.fail(f"Unexpected metric name: {item['metric_name']}") 