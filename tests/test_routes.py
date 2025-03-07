from datetime import date, timedelta, datetime

import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import UserDefinedMetric, HealthData, DataType

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
        """Test the data management route (mock test)."""
        # Create a test data source
        source = DataType(
            source='test_source',
            metric_name='source_info',
            source_type='test',
            last_import=datetime.now()
        )
        db.session.add(source)
        db.session.commit()
        
        response = self.client.get('/data')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Data Management', response.data)
    
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
    
    def test_custom_metrics_functionality(self):
        """Test the custom metrics page and functionality."""
        # Create a test custom metric
        custom_metric = UserDefinedMetric(
            name='BMI',
            unit='kg/m²',
            description='Body Mass Index',
            data_type='numeric',
            is_cumulative=False
        )
        db.session.add(custom_metric)
        db.session.commit()
        
        # Create a DataType for this custom metric
        data_type = DataType(
            source='custom',
            metric_name='BMI',
            metric_units='kg/m²'
        )
        db.session.add(data_type)
        db.session.commit()
        
        # Test the metrics page
        response = self.client.get('/data/custom-metrics')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Custom Health Metrics', response.data)
        self.assertIn(b'BMI', response.data)
        
        # Test viewing a specific metric
        response = self.client.get(f'/data/custom-metrics/view/{custom_metric.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'BMI', response.data)
        self.assertIn(b'Body Mass Index', response.data)
    
    def test_custom_metrics_add(self):
        """Test adding a new custom metric."""
        # Test the add metric form
        response = self.client.get('/data/custom-metrics/add')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Add Custom Metric', response.data)
        
        # Test submitting the form
        response = self.client.post('/data/custom-metrics/add', data={
            'name': 'Calorie Ratio',
            'unit': 'ratio',
            'description': 'Ratio of calories consumed to calories burned',
            'data_type': 'numeric',
            'is_cumulative': 'false'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Calorie Ratio', response.data)
        
        # Verify the metric was added to the database
        metric = UserDefinedMetric.query.filter_by(name='Calorie Ratio').first()
        self.assertIsNotNone(metric)
        self.assertEqual(metric.unit, 'ratio')
        self.assertEqual(metric.description, 'Ratio of calories consumed to calories burned')
        self.assertEqual(metric.data_type, 'numeric')
        
        # Verify the DataType was created
        data_type = DataType.query.filter_by(source='custom', metric_name='Calorie Ratio').first()
        self.assertIsNotNone(data_type)
        self.assertEqual(data_type.metric_units, 'ratio')
    
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