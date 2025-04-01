from datetime import date, timedelta, datetime

import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataType

class RouteTestCase(BaseTestCase):
    """Test case for the application routes."""
    
    def setUp(self):
        """Set up test client and create test data."""
        super().setUp()
    
    def _clear_test_data(self):
        """Clear all health data for clean testing."""
        try:
            HealthData.query.delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing test data: {e}")
    
    def test_index_route(self):
        """Test that the index route returns a 200 status code."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Health Data Tracker', response.data)
    
    def test_about_route(self):
        """Test that the about route returns a 200 status code."""
        response = self.client.get('/about')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'About', response.data)
    
    def test_correlation_route(self):
        """Test that the correlation route returns a 200 status code."""
        response = self.client.get('/analysis/correlation')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Correlation Analysis', response.data)
    
    def test_data_route(self):
        """Test the data overview route (mock test)."""
        # Create a test data source
        source = DataType(
            source='test_source',
            metric_name='source_info',
            source_type='api'
        )
        db.session.add(source)
        db.session.commit()
        
        response = self.client.get('/data/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Data Overview', response.data)
        
        # Clean up
        db.session.delete(source)
        db.session.commit()
    
    def test_data_import_route(self):
        """Test that the data import route returns a 200 status code."""
        response = self.client.get('/data/import')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Import Data', response.data)
    
    def test_analysis_dashboard_route(self):
        """Test the analysis dashboard route with sample data."""
        self._clear_test_data()  # Ensure clean state
        
        # Create data types for sleep and steps
        sleep_type = DataType(
            source='test',
            metric_name='sleep',
            metric_units='hours'
        )
        db.session.add(sleep_type)
        
        steps_type = DataType(
            source='test',
            metric_name='steps',
            metric_units='count'
        )
        db.session.add(steps_type)
        db.session.flush()
        
        # Add some test data
        today = date.today()
        for i in range(7):
            test_date = today - timedelta(days=i)
            sleep_data = HealthData(
                date=test_date,
                data_type=sleep_type,
                metric_value=7.5 - (i * 0.1)  # Slightly decreasing sleep
            )
            steps_data = HealthData(
                date=test_date,
                data_type=steps_type,
                metric_value=8000 + (i * 500)  # Increasing steps
            )
            db.session.add(sleep_data)
            db.session.add(steps_data)
        
        db.session.commit()
        
        response = self.client.get('/analysis/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
    
    def test_data_browse_route(self):
        """Test the data browse route with filtering."""
        self._clear_test_data()  # Ensure clean state
        
        # Create data types
        sleep_type = DataType(
            source='oura',
            metric_name='sleep_score',
            metric_units='score'
        )
        db.session.add(sleep_type)
        
        steps_type = DataType(
            source='garmin',
            metric_name='steps',
            metric_units='count'
        )
        db.session.add(steps_type)
        
        calories_type = DataType(
            source='chronometer',
            metric_name='calories',
            metric_units='kcal'
        )
        db.session.add(calories_type)
        db.session.flush()
        
        # Add some test data
        today = date.today()
        for i in range(5):
            test_date = today - timedelta(days=i)
            
            sleep_data = HealthData(
                date=test_date,
                data_type=sleep_type,
                metric_value=85 - i
            )
            db.session.add(sleep_data)
            
            steps_data = HealthData(
                date=test_date,
                data_type=steps_type,
                metric_value=10000 - (i * 500)
            )
            db.session.add(steps_data)
            
            calories_data = HealthData(
                date=test_date,
                data_type=calories_type,
                metric_value=2000 + (i * 100)
            )
            db.session.add(calories_data)
        
        db.session.commit()
        
        # Test default browse route
        response = self.client.get('/data/browse')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Browse Data', response.data)
        
        # Test filtering by source
        response = self.client.get('/data/browse?source=oura')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'oura', response.data)
        self.assertIn(b'sleep_score', response.data)
        
        # Test filtering by metric
        response = self.client.get('/data/browse?metric=steps')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'garmin', response.data)
        self.assertIn(b'steps', response.data)
        
        # Test filtering by date range
        start_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        response = self.client.get(f'/data/browse?start_date={start_date}&end_date={end_date}')
        self.assertEqual(response.status_code, 200)
        # Should show 3 days of data (today, yesterday, day before)
    
    def test_analysis_data_api(self):
        """Test the analysis data API endpoint."""
        self._clear_test_data()  # Ensure clean state
        
        # Create data type for sleep score
        sleep_type = DataType(
            source='oura',
            metric_name='sleep_score',
            metric_units='score'
        )
        db.session.add(sleep_type)
        db.session.flush()
        
        # Add some test data
        today = date.today()
        for i in range(7):
            test_date = today - timedelta(days=i)
            sleep_data = HealthData(
                date=test_date,
                data_type=sleep_type,
                metric_value=85 - i
            )
            db.session.add(sleep_data)
        
        db.session.commit()
        
        # Test the API endpoint
        response = self.client.get('/analysis/data?metric=sleep_score&source=oura')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'success', response.data)
    
    def test_chronometer_import(self):
        """Test the Chronometer import functionality with a sample file."""
        import tempfile
        from io import BytesIO
        
        # Create a sample CSV file
        csv_data = """Day,Energy (kcal),Protein (g),Carbs (g),Fat (g)
2023-03-01,2000,100,200,80
2023-03-02,1800,90,180,70"""
        
        # Convert string to bytes for the file upload
        csv_file = BytesIO(csv_data.encode('utf-8'))
        
        # Create a mock file upload
        data = {
            'data_source': 'chronometer_csv',
            'chronometer_file': (csv_file, 'test_chronometer.csv')
        }
        
        # Test the import route
        response = self.client.post(
            '/data/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'successfully', response.data.lower())
        
        # Verify data was imported correctly
        # Check for energy data
        energy_type = DataType.query.filter_by(
            source='chronometer',
            metric_name='Energy (kcal)'
        ).first()
        self.assertIsNotNone(energy_type)
        
        energy_data = HealthData.query.filter(
            HealthData.data_type_id == energy_type.id,
            HealthData.date == date(2023, 3, 1)
        ).first()
        self.assertIsNotNone(energy_data)
        self.assertEqual(energy_data.metric_value, 2000)
        
        # Check for protein data
        protein_type = DataType.query.filter_by(
            source='chronometer',
            metric_name='Protein (g)'
        ).first()
        self.assertIsNotNone(protein_type)
        
        protein_data = HealthData.query.filter(
            HealthData.data_type_id == protein_type.id,
            HealthData.date == date(2023, 3, 1)
        ).first()
        self.assertIsNotNone(protein_data)
        self.assertEqual(protein_data.metric_value, 100)
    
    def test_data_date_view(self):
        """Test the date view route with sample data."""
        self._clear_test_data()  # Ensure clean state
        
        # Create test data for a specific date
        test_date = date(2023, 3, 15)
        formatted_date = test_date.strftime('%Y-%m-%d')
        
        # Create data types
        sleep_type = DataType(
            source='oura',
            metric_name='sleep_score',
            metric_units='score'
        )
        db.session.add(sleep_type)
        
        steps_type = DataType(
            source='garmin',
            metric_name='steps',
            metric_units='count'
        )
        db.session.add(steps_type)
        
        calories_type = DataType(
            source='chronometer',
            metric_name='calories',
            metric_units='kcal'
        )
        db.session.add(calories_type)
        db.session.flush()
        
        # Add health data for the test date
        sleep_data = HealthData(
            date=test_date,
            data_type=sleep_type,
            metric_value=85
        )
        db.session.add(sleep_data)
        
        steps_data = HealthData(
            date=test_date,
            data_type=steps_type,
            metric_value=12500
        )
        db.session.add(steps_data)
        
        calories_data = HealthData(
            date=test_date,
            data_type=calories_type,
            metric_value=2100
        )
        db.session.add(calories_data)
        
        db.session.commit()
        
        # Test the date view route
        response = self.client.get(f'/data/date/{formatted_date}')
        self.assertEqual(response.status_code, 200)
        
        # Verify the page contains our data
        self.assertIn(b'Daily Health Summary', response.data)
        self.assertIn(b'March 15, 2023', response.data)
        
        # Check each source of data
        self.assertIn(b'Oura', response.data)
        self.assertIn(b'85.0', response.data)  # Sleep score
        self.assertIn(b'Garmin', response.data)
        self.assertIn(b'12500.0', response.data)  # Steps
        self.assertIn(b'Chronometer', response.data)
        self.assertIn(b'2100.0', response.data)  # Calories
    
    def test_date_view_no_data(self):
        """Test the date view route with no data for the selected date."""
        self._clear_test_data()  # Ensure clean state
        
        # Use a date we know has no data
        test_date = date(2099, 12, 31)
        formatted_date = test_date.strftime('%Y-%m-%d')
        
        # Test the date view route
        response = self.client.get(f'/data/date/{formatted_date}')
        self.assertEqual(response.status_code, 200)
        
        # Verify the page contains a message about no data
        self.assertIn(b'No health data found for December 31, 2099', response.data)
    
    # Tests from test_browse_route.py
    def test_browse_with_calorie_filter(self):
        """Test that browse route correctly filters by calories."""
        # Create test data types
        dt_energy = DataType(
            source='chronometer',
            metric_name='Energy (kcal)',
            metric_units='kcal',
            source_type='csv'
        )
        
        dt_sleep = DataType(
            source='oura',
            metric_name='sleep_duration',
            metric_units='hours',
            source_type='api'
        )
        
        db.session.add_all([dt_energy, dt_sleep])
        db.session.commit()
        
        # Create test health data
        # Day 1 - high calories
        day1 = date.today() - timedelta(days=2)
        energy_day1 = HealthData(
            date=day1,
            data_type_id=dt_energy.id,
            metric_value=2500.0
        )
        
        sleep_day1 = HealthData(
            date=day1,
            data_type_id=dt_sleep.id,
            metric_value=7.5
        )
        
        # Day 2 - low calories
        day2 = date.today() - timedelta(days=1)
        energy_day2 = HealthData(
            date=day2,
            data_type_id=dt_energy.id,
            metric_value=1500.0
        )
        
        sleep_day2 = HealthData(
            date=day2,
            data_type_id=dt_sleep.id,
            metric_value=8.0
        )
        
        db.session.add_all([energy_day1, sleep_day1, energy_day2, sleep_day2])
        db.session.commit()
        
        # Test with max calories = 2000 (should only show day2 data)
        response = self.client.get('/data/browse?max_calories=2000')
        self.assertEqual(response.status_code, 200)
        
        # Day 2 data should be included
        self.assertIn(f'>{day2.strftime("%Y-%m-%d")}<', response.data.decode('utf-8'))
        self.assertIn('>1500.0<', response.data.decode('utf-8'))
        self.assertIn('>8.0<', response.data.decode('utf-8'))
        
        # Day 1 data should NOT be included
        self.assertNotIn(f'>{day1.strftime("%Y-%m-%d")}<', response.data.decode('utf-8'))
        self.assertNotIn('>2500.0<', response.data.decode('utf-8'))
        self.assertNotIn('>7.5<', response.data.decode('utf-8'))
        
        # Clean up
        self._clear_test_data()
        db.session.delete(dt_energy)
        db.session.delete(dt_sleep)
        db.session.commit()
        
    def test_browse_without_calorie_filter(self):
        """Test that browse route shows all data without calorie filter."""
        # Create test data types
        dt_energy = DataType(
            source='chronometer',
            metric_name='Energy (kcal)',
            metric_units='kcal',
            source_type='csv'
        )
        
        dt_sleep = DataType(
            source='oura',
            metric_name='sleep_duration',
            metric_units='hours',
            source_type='api'
        )
        
        db.session.add_all([dt_energy, dt_sleep])
        db.session.commit()
        
        # Create test health data
        # Day 1 - high calories
        day1 = date.today() - timedelta(days=2)
        energy_day1 = HealthData(
            date=day1,
            data_type_id=dt_energy.id,
            metric_value=2500.0
        )
        
        sleep_day1 = HealthData(
            date=day1,
            data_type_id=dt_sleep.id,
            metric_value=7.5
        )
        
        # Day 2 - low calories
        day2 = date.today() - timedelta(days=1)
        energy_day2 = HealthData(
            date=day2,
            data_type_id=dt_energy.id,
            metric_value=1500.0
        )
        
        sleep_day2 = HealthData(
            date=day2,
            data_type_id=dt_sleep.id,
            metric_value=8.0
        )
        
        db.session.add_all([energy_day1, sleep_day1, energy_day2, sleep_day2])
        db.session.commit()
        
        response = self.client.get('/data/browse')
        self.assertEqual(response.status_code, 200)
        
        # Both days' data should be included
        self.assertIn(f'>{day1.strftime("%Y-%m-%d")}<', response.data.decode('utf-8'))
        self.assertIn(f'>{day2.strftime("%Y-%m-%d")}<', response.data.decode('utf-8'))
        self.assertIn('>2500.0<', response.data.decode('utf-8'))
        self.assertIn('>1500.0<', response.data.decode('utf-8'))
        self.assertIn('>7.5<', response.data.decode('utf-8'))
        self.assertIn('>8.0<', response.data.decode('utf-8'))
        
        # Clean up
        self._clear_test_data()
        db.session.delete(dt_energy)
        db.session.delete(dt_sleep)
        db.session.commit()
    
    # Tests from test_data_types_routes.py
    def test_data_types_route(self):
        """Test that the data types route returns a 200 status code and shows all data types."""
        # Create some test data types
        dt1 = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units',
            source_type='api'
        )
        
        dt2 = DataType(
            source='test_source',
            metric_name='another_metric',
            metric_units='another_units',
            source_type='csv'
        )
        
        dt3 = DataType(
            source='test_source_with_data',
            metric_name='metric_with_data',
            metric_units='units',
            source_type='manual'
        )
        
        db.session.add_all([dt1, dt2, dt3])
        db.session.commit()
        
        response = self.client.get('/data/data-types')
        self.assertEqual(response.status_code, 200)
        
        # Check that all test data types are displayed
        self.assertIn(b'test_source', response.data)
        self.assertIn(b'test_metric', response.data)
        self.assertIn(b'another_metric', response.data)
        self.assertIn(b'test_source_with_data', response.data)
        
        # Clean up
        db.session.delete(dt1)
        db.session.delete(dt2)
        db.session.delete(dt3)
        db.session.commit()
    
    def test_edit_data_type_get(self):
        """Test that the edit data type route returns a 200 status code and the correct form."""
        # Create a test data type
        dt1 = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units',
            source_type='api'
        )
        
        db.session.add(dt1)
        db.session.commit()
        
        response = self.client.get(f'/data/data-types/edit/{dt1.id}')
        self.assertEqual(response.status_code, 200)
        
        # Check that the form contains the correct data
        self.assertIn(b'test_source', response.data)
        self.assertIn(b'test_metric', response.data)
        self.assertIn(b'test_units', response.data)
        self.assertIn(b'api', response.data)
        
        # Clean up
        db.session.delete(dt1)
        db.session.commit()
    
    def test_edit_data_type_post(self):
        """Test that the edit data type route correctly updates a data type."""
        # Create a test data type
        dt1 = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units',
            source_type='api'
        )
        
        db.session.add(dt1)
        db.session.commit()
        
        response = self.client.post(
            f'/data/data-types/edit/{dt1.id}',
            data={
                'source': 'updated_source',
                'metric_name': 'updated_metric',
                'metric_units': 'updated_units',
                'source_type': 'csv'
            },
            follow_redirects=True
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the data was updated in the database
        updated_dt = DataType.query.get(dt1.id)
        self.assertEqual(updated_dt.source, 'updated_source')
        self.assertEqual(updated_dt.metric_name, 'updated_metric')
        self.assertEqual(updated_dt.metric_units, 'updated_units')
        self.assertEqual(updated_dt.source_type, 'csv')
        
        # Check for success message
        self.assertIn(b'Successfully updated data type', response.data)
        
        # Clean up
        db.session.delete(updated_dt)
        db.session.commit()
    
    def test_delete_data_type(self):
        """Test that the delete data type route correctly deletes a data type without data."""
        # Create a test data type
        dt2 = DataType(
            source='test_source',
            metric_name='another_metric',
            metric_units='another_units',
            source_type='csv'
        )
        
        db.session.add(dt2)
        db.session.commit()
        
        response = self.client.post(
            f'/data/data-types/delete/{dt2.id}',
            follow_redirects=True
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the data type is gone from the database
        deleted_dt = DataType.query.get(dt2.id)
        self.assertIsNone(deleted_dt)
        
        # Check for success message
        self.assertIn(b'Successfully deleted data type', response.data)
    
    def test_delete_data_type_with_data(self):
        """Test that the delete data type route prevents deletion of data types with associated data."""
        # Create a test data type with associated health data
        dt3 = DataType(
            source='test_source_with_data',
            metric_name='metric_with_data',
            metric_units='units',
            source_type='manual'
        )
        
        db.session.add(dt3)
        db.session.commit()
        
        # Create some health data associated with dt3
        health_data = HealthData(
            date=date.today(),
            data_type_id=dt3.id,
            metric_value=10.5,
            notes="Test data"
        )
        
        db.session.add(health_data)
        db.session.commit()
        
        response = self.client.post(
            f'/data/data-types/delete/{dt3.id}',
            follow_redirects=True
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the data type still exists in the database
        not_deleted_dt = DataType.query.get(dt3.id)
        self.assertIsNotNone(not_deleted_dt)
        
        # Check for error message
        self.assertIn(b'Cannot delete data type that has', response.data)
        
        # Clean up
        db.session.delete(health_data)
        db.session.delete(dt3)
        db.session.commit()
    
    def test_data_type_not_found(self):
        """Test that the edit and delete routes return 404 for non-existent data types."""
        # Test edit route
        response = self.client.get('/data/data-types/edit/9999')
        self.assertEqual(response.status_code, 404)
        
        # Test delete route
        response = self.client.post('/data/data-types/delete/9999')
        self.assertEqual(response.status_code, 404) 