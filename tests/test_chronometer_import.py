import unittest
import os
import tempfile
from datetime import date
import pandas as pd
from io import StringIO

from .test_base import BaseTestCase
from app.models.base import HealthData, DataSource
from app.utils.chronometer_importer import ChronometerImporter

class ChronometerImportTestCase(BaseTestCase):
    
    def setUp(self):
        super().setUp()
        
        # Create a sample Chronometer CSV data
        self.csv_data = """Day,Name,Quantity,Energy (kcal),Protein (g),Carbs (g),Fat (g),Fiber (g),Sugars (g),Sodium (mg),Potassium (mg),Vitamin C (mg),Calcium (mg),Iron (mg),Category
2023-01-01,Oatmeal,100,150,5,30,2.5,4,1,10,100,0,30,1.2,Breakfast
2023-01-01,Apple,1,72,0.3,19,0.2,3.3,15,1,107,8.4,8,0.1,Snacks
2023-01-01,Chicken Breast,200,330,62,0,7,0,0,155,280,0,15,1.3,Dinner
2023-01-02,Banana,1,105,1.3,27,0.4,3.1,14,1,422,10.3,6,0.3,Breakfast
2023-01-02,Greek Yogurt,150,150,15,8,6,0,7,70,220,0,200,0,Snacks
2023-01-02,Salmon,200,412,40,0,25,0,0,113,628,0,12,0.9,Dinner
"""

        # Create a temporary file
        self.csv_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        self.csv_file.write(self.csv_data.encode('utf-8'))
        self.csv_file.close()
    
    def tearDown(self):
        # Remove the temporary file
        if os.path.exists(self.csv_file.name):
            os.unlink(self.csv_file.name)
        
        super().tearDown()
    
    def test_chronometer_importer_init(self):
        """Test that the ChronometerImporter initializes correctly"""
        importer = ChronometerImporter()
        
        # Check that the nutrition metrics are defined
        self.assertTrue(len(importer.nutrition_metrics) > 0)
        self.assertIn('Energy (kcal)', importer.nutrition_metrics)
        self.assertIn('Protein (g)', importer.nutrition_metrics)
    
    def test_process_csv_data(self):
        """Test processing raw CSV data"""
        importer = ChronometerImporter()
        
        # Load the CSV data
        df = pd.read_csv(StringIO(self.csv_data))
        
        # Process the data
        processed_data = importer._process_csv_data(df)
        
        # Check that we have data for each date and metric
        self.assertGreater(len(processed_data), 0)
        
        # Check that we have data for Jan 1 and Jan 2
        dates = set([item['date'] for item in processed_data])
        self.assertIn(date(2023, 1, 1), dates)
        self.assertIn(date(2023, 1, 2), dates)
        
        # Check that we have energy data
        energy_data = [item for item in processed_data if item['metric_name'] == 'Energy (kcal)']
        self.assertEqual(len(energy_data), 2)  # One for each date
        
        # Check the energy values
        jan1_energy = next(item for item in energy_data if item['date'] == date(2023, 1, 1))
        jan2_energy = next(item for item in energy_data if item['date'] == date(2023, 1, 2))
        
        # Jan 1: 150 (oatmeal) + 72 (apple) + 330 (chicken) = 552
        self.assertEqual(jan1_energy['metric_value'], 552)
        
        # Jan 2: 105 (banana) + 150 (yogurt) + 412 (salmon) = 667
        self.assertEqual(jan2_energy['metric_value'], 667)
    
    def test_import_from_csv(self):
        """Test importing from a CSV file"""
        importer = ChronometerImporter()
        
        # Import the data
        processed_data = importer.import_from_csv(self.csv_file.name)
        
        # Check that data was imported
        self.assertGreater(len(processed_data), 0)
        
        # Check that data was saved to the database
        db_data = HealthData.query.filter_by(source='chronometer').all()
        self.assertGreater(len(db_data), 0)
        
        # Check that a data source was created/updated
        data_source = DataSource.query.filter_by(name='chronometer_csv').first()
        self.assertIsNotNone(data_source)
        self.assertEqual(data_source.type, 'csv')
    
    def test_process_food_categories(self):
        """Test processing food categories"""
        importer = ChronometerImporter()
        
        # Load the CSV data
        df = pd.read_csv(StringIO(self.csv_data))
        
        # Process the food categories
        processed_data = importer.process_food_categories(df)
        
        # Check that we have data for each category
        self.assertGreater(len(processed_data), 0)
        
        # Check that we have data for the categories
        categories = set([item['metric_name'] for item in processed_data])
        self.assertIn('Food Category: Breakfast', categories)
        self.assertIn('Food Category: Snacks', categories)
        self.assertIn('Food Category: Dinner', categories)
        
        # Check the energy values for categories
        jan1_breakfast = next(item for item in processed_data 
                             if item['date'] == date(2023, 1, 1) and 
                             item['metric_name'] == 'Food Category: Breakfast')
        
        # Jan 1 Breakfast: 150 kcal (oatmeal)
        self.assertEqual(jan1_breakfast['metric_value'], 150)
        
    def test_import_with_http_client(self):
        """Test importing using the HTTP client (simulates form submission)"""
        # Create the test csv file content
        csv_content = self.csv_data
        
        # Create a file-like object for the post request
        from io import BytesIO
        file_data = BytesIO(csv_content.encode('utf-8'))
        
        # Simulate form submission with file upload
        response = self.client.post(
            '/data/import',
            data={
                'data_source': 'chronometer_csv',
                'process_categories': 'yes',
                'chronometer_file': (file_data, 'test_chronometer.csv')
            },
            content_type='multipart/form-data',
            follow_redirects=True
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        
        # Verify data was imported to the database
        db_data = HealthData.query.filter_by(source='chronometer').all()
        self.assertGreater(len(db_data), 0)
        
        # Verify food categories were processed
        category_data = HealthData.query.filter(
            HealthData.metric_name.like('Food Category:%')
        ).all()
        self.assertGreater(len(category_data), 0)

if __name__ == '__main__':
    unittest.main() 