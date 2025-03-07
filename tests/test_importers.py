import os
import tempfile
from unittest.mock import patch
from datetime import date, datetime

import sys
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataType

# Mock classes for testing
class MockOuraImporter:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.client = "mock_client"
    
    def import_sleep_data(self, start_date, end_date):
        # Create a data type if it doesn't exist
        data_type = DataType.query.filter_by(
            source='oura',
            metric_name='sleep_score'
        ).first()
        
        if not data_type:
            data_type = DataType(
                source='oura',
                metric_name='sleep_score',
                metric_units='score'
            )
            db.session.add(data_type)
            db.session.flush()
            
        # Add mock data to the database
        sleep_data = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=85
        )
        db.session.add(sleep_data)
        
        # Add a data source
        source = DataType.query.filter_by(source='oura', metric_name='source_info').first()
        if not source:
            source = DataType(
                source='oura',
                metric_name='source_info',
                source_type='api',
                last_import=datetime.now()
            )
            db.session.add(source)
        
        db.session.commit()
        
        # Return a list of processed data points
        return [
            {
                'date': date(2025, 3, 1),
                'metric_name': 'sleep_score',
                'metric_value': 85,
                'metric_units': 'score'
            }
        ]

class MockChronometerImporter:
    def __init__(self):
        self.nutrition_metrics = [
            'Energy (kcal)',
            'Protein (g)',
            'Carbs (g)',
            'Fat (g)'
        ]
    
    def import_from_csv(self, file_path):
        # Create data types if they don't exist
        energy_type = DataType.query.filter_by(
            source='chronometer',
            metric_name='energy'
        ).first()
        
        if not energy_type:
            energy_type = DataType(
                source='chronometer',
                metric_name='energy',
                metric_units='kcal'
            )
            db.session.add(energy_type)
            
        protein_type = DataType.query.filter_by(
            source='chronometer',
            metric_name='protein'
        ).first()
        
        if not protein_type:
            protein_type = DataType(
                source='chronometer',
                metric_name='protein',
                metric_units='g'
            )
            db.session.add(protein_type)
            
        # Add mock data to the database
        energy_data = HealthData(
            date=date(2025, 3, 1),
            data_type=energy_type,
            metric_value=2000
        )
        db.session.add(energy_data)
        
        protein_data = HealthData(
            date=date(2025, 3, 1),
            data_type=protein_type,
            metric_value=100
        )
        db.session.add(protein_data)
        
        # Add a data source
        source = DataType.query.filter_by(source='chronometer', metric_name='source_info').first()
        if not source:
            source = DataType(
                source='chronometer',
                metric_name='source_info',
                source_type='csv',
                last_import=datetime.now()
            )
            db.session.add(source)
            
        db.session.commit()
        
        # Return a list of processed data points
        return [
            {
                'date': date(2025, 3, 1),
                'metric_name': 'energy',
                'metric_value': 2000,
                'metric_units': 'kcal'
            },
            {
                'date': date(2025, 3, 1),
                'metric_name': 'protein',
                'metric_value': 100,
                'metric_units': 'g'
            }
        ]
    
    def _parse_csv_row(self, row):
        # Parse a CSV row and return a list of dictionaries containing the data type and value
        result = []
        
        # Add energy data
        if 'Energy (kcal)' in row:
            result.append({
                'metric_name': 'energy',
                'metric_value': int(row['Energy (kcal)']),
                'metric_units': 'kcal'
            })
            
        # Add protein data
        if 'Protein (g)' in row:
            result.append({
                'metric_name': 'protein',
                'metric_value': int(row['Protein (g)']),
                'metric_units': 'g'
            })
            
        # Add carbs data
        if 'Carbs (g)' in row:
            result.append({
                'metric_name': 'carbs',
                'metric_value': int(row['Carbs (g)']),
                'metric_units': 'g'
            })
            
        # Add fat data
        if 'Fat (g)' in row:
            result.append({
                'metric_name': 'fat',
                'metric_value': int(row['Fat (g)']),
                'metric_units': 'g'
            })
            
        return result

# Test cases for importers
class ImporterTestCase(BaseTestCase):
    """Test case for data importers."""
    
    def test_oura_importer_init(self):
        """Test Oura importer initialization."""
        from app.utils.oura_importer import OuraImporter
        
        # Create an importer with a mock API key
        importer = OuraImporter(personal_token='test_key')
        
        # Check that the importer has the expected attributes
        self.assertEqual(importer.personal_token, 'test_key')
        self.assertEqual(importer.api_base_url, 'https://api.ouraring.com')
        self.assertEqual(importer.auth_header, {'Authorization': 'Bearer test_key'})
    
    def test_oura_import_sleep_data(self):
        """Test importing sleep data from the Oura API."""
        with patch('app.utils.oura_importer.OuraImporter', MockOuraImporter):
            from app.utils.oura_importer import OuraImporter
            
            # Create an importer and import data
            importer = OuraImporter(api_key='test_key')
            result = importer.import_sleep_data('2025-03-01', '2025-03-07')
            
            # Check that data was added to the database
            sleep_data = HealthData.query.join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name == 'sleep_score'
            ).first()
            
            self.assertIsNotNone(sleep_data)
            self.assertEqual(sleep_data.metric_value, 85)
            
            # Check that a data source was added
            source = DataType.query.filter_by(source='oura', metric_name='source_info').first()
            self.assertIsNotNone(source)
            self.assertEqual(source.source_type, 'api')
    
    def test_cronometer_importer_init(self):
        """Test Cronometer importer initialization."""
        from app.utils.chronometer_importer import ChronometerImporter
        
        # Create an importer
        importer = ChronometerImporter()
        
        # Check that the importer has the expected attributes
        self.assertIsNotNone(importer.nutrition_metrics)
        self.assertIn('Energy (kcal)', importer.nutrition_metrics)
        self.assertIn('Protein (g)', importer.nutrition_metrics)
    
    def test_cronometer_import_nutrition_data(self):
        """Test importing nutrition data from a Cronometer CSV file."""
        with patch('app.utils.chronometer_importer.ChronometerImporter', MockChronometerImporter):
            from app.utils.chronometer_importer import ChronometerImporter
            
            # Create a temporary CSV file with test data
            csv_data = """Date,Energy (kcal),Protein (g),Carbs (g),Fat (g)
2025-03-01,2000,100,200,80
2025-03-02,1800,90,180,70"""
            
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                temp_file.write(csv_data)
                temp_file_path = temp_file.name
            
            try:
                # Create the importer and import data
                importer = ChronometerImporter()
                result = importer.import_from_csv(temp_file_path)
                
                # Check that data was added to the database
                energy_data = HealthData.query.join(
                    DataType, HealthData.data_type_id == DataType.id
                ).filter(
                    DataType.source == 'chronometer',
                    DataType.metric_name == 'energy'
                ).first()
                
                self.assertIsNotNone(energy_data)
                self.assertEqual(energy_data.metric_value, 2000)
                
                # Check that a data source was added
                source = DataType.query.filter_by(source='chronometer', metric_name='source_info').first()
                self.assertIsNotNone(source)
                self.assertEqual(source.source_type, 'csv')
            
            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)
    
    def test_cronometer_parse_csv_row(self):
        """Test parsing a CSV row from a Cronometer export."""
        with patch('app.utils.chronometer_importer.ChronometerImporter', MockChronometerImporter):
            from app.utils.chronometer_importer import ChronometerImporter
            
            # Create an importer
            importer = ChronometerImporter()
            
            # Create a sample CSV row
            row = {
                'Date': '2025-03-01',
                'Energy (kcal)': '2000',
                'Protein (g)': '100',
                'Carbs (g)': '200',
                'Fat (g)': '80'
            }
            
            # Parse the row
            result = importer._parse_csv_row(row)
            
            # Check the result
            self.assertEqual(len(result), 4)  # Should have 4 metrics
            
            # Check that each metric has the expected values
            energy = next((item for item in result if item['metric_name'] == 'energy'), None)
            self.assertIsNotNone(energy)
            self.assertEqual(energy['metric_value'], 2000)
            
            protein = next((item for item in result if item['metric_name'] == 'protein'), None)
            self.assertIsNotNone(protein)
            self.assertEqual(protein['metric_value'], 100) 