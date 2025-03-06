from datetime import date, timedelta

import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import DataSource, UserDefinedMetric, HealthData

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
        source = DataSource(name='test_source', type='test')
        db.session.add(source)
        db.session.commit()
        
        # Call the data index route
        response = self.client.get('/data/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Data Management', response.data)
    
    def test_data_import_route(self):
        """Test the data import route."""
        response = self.client.get('/data/import')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Import Health Data', response.data)
    
    def test_analysis_dashboard_route(self):
        """Test the analysis dashboard route."""
        # Create some test data for the dashboard
        for i in range(10):
            day = date.today() - timedelta(days=i)
            data_point = HealthData(
                date=day,
                source='test',
                metric_name='test_metric',
                metric_value=50 + i,
                metric_units='units'
            )
            db.session.add(data_point)
        db.session.commit()
        
        response = self.client.get('/analysis/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
    
    def test_data_browse_route(self):
        """Test the data/browse route with various filters."""
        # Create test data with different sources and metrics
        sources = ['oura', 'chronometer', 'custom']
        metrics = ['sleep_duration', 'energy', 'weight']
        
        for i in range(30):  # Create enough data for pagination
            source = sources[i % len(sources)]
            metric = metrics[i % len(metrics)]
            day = date.today() - timedelta(days=i)
            
            data_point = HealthData(
                date=day,
                source=source,
                metric_name=metric,
                metric_value=i * 10,
                metric_units='units'
            )
            db.session.add(data_point)
        db.session.commit()
        
        # Test base route without filters
        response = self.client.get('/data/browse')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Browse Health Data', response.data)
        
        # Test with source filter
        response = self.client.get('/data/browse?source=oura')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'oura', response.data.lower())
        
        # Test with metric filter
        response = self.client.get('/data/browse?metric=energy')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'energy', response.data.lower())
        
        # Test with both filters
        response = self.client.get('/data/browse?source=chronometer&metric=energy')
        self.assertEqual(response.status_code, 200)
        
        # Test pagination
        response = self.client.get('/data/browse?page=2&per_page=10')
        self.assertEqual(response.status_code, 200)
    
    def test_custom_metrics_functionality(self):
        """Test the custom metrics functionality (mock test)."""
        # Create a test custom metric to verify DB operations
        metric = UserDefinedMetric(
            name='test_metric',
            units='test_units',
            description='This is a test metric',
            frequency='daily'
        )
        db.session.add(metric)
        db.session.commit()
        
        # Verify the metric was created
        result = UserDefinedMetric.query.filter_by(name='test_metric').first()
        self.assertIsNotNone(result)
        self.assertEqual(result.units, 'test_units')
        self.assertEqual(result.description, 'This is a test metric')
        self.assertEqual(result.frequency, 'daily')
    
    def test_custom_metrics_add(self):
        """Test adding a new custom metric (mock test)."""
        # Create a new metric to verify DB operations
        metric = UserDefinedMetric(
            name='new_metric',
            units='new_units',
            description='This is a new metric',
            frequency='daily'
        )
        db.session.add(metric)
        db.session.commit()
        
        # Verify the metric was added
        result = UserDefinedMetric.query.filter_by(name='new_metric').first()
        self.assertIsNotNone(result)
        self.assertEqual(result.units, 'new_units')
        self.assertEqual(result.description, 'This is a new metric')
        self.assertEqual(result.frequency, 'daily')
    
    def test_analysis_data_api(self):
        """Test the analysis data API."""
        # Create some test data
        for i in range(5):
            day = date.today() - timedelta(days=i)
            data_point = HealthData(
                date=day,
                source='test',
                metric_name='test_api_metric',
                metric_value=100 + i,
                metric_units='units'
            )
            db.session.add(data_point)
        db.session.commit()
        
        response = self.client.get('/analysis/data')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'success', response.data)
        
    def test_chronometer_import(self):
        """Test importing Chronometer CSV data."""
        # Create a sample CSV data
        csv_data = """Day,Name,Quantity,Energy (kcal),Protein (g),Carbs (g),Fat (g),Fiber (g),Sugars (g),Sodium (mg),Potassium (mg),Vitamin C (mg),Calcium (mg),Iron (mg),Category
2023-01-01,Oatmeal,100,150,5,30,2.5,4,1,10,100,0,30,1.2,Breakfast
2023-01-01,Apple,1,72,0.3,19,0.2,3.3,15,1,107,8.4,8,0.1,Snacks
2023-01-02,Banana,1,105,1.3,27,0.4,3.1,14,1,422,10.3,6,0.3,Breakfast
"""
        # Create a file-like object for the post request
        from io import BytesIO
        file_data = BytesIO(csv_data.encode('utf-8'))
        
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
        
        # Verify we have energy data for Jan 1
        energy_data = HealthData.query.filter_by(
            source='chronometer',
            metric_name='Energy (kcal)',
            date=date(2023, 1, 1)
        ).first()
        
        self.assertIsNotNone(energy_data)
        # Jan 1: 150 (oatmeal) + 72 (apple) = 222 kcal
        self.assertEqual(energy_data.metric_value, 222)
        
        # Verify food categories were processed
        category_data = HealthData.query.filter(
            HealthData.metric_name.like('Food Category:%')
        ).all()
        self.assertGreater(len(category_data), 0)
    
    def test_data_date_view(self):
        """Test the data/date view route."""
        # Clear any existing data that might affect this test
        self._clear_test_data()
        
        # Create test data for multiple sources on the same date
        test_date = date.today()
        
        # Create Oura data for the test date
        oura_data = [
            HealthData(
                date=test_date,
                source='oura',
                metric_name='sleep_score',
                metric_value=85,
                metric_units='score'
            ),
            HealthData(
                date=test_date,
                source='oura',
                metric_name='avg_hrv',
                metric_value=42,
                metric_units='ms'
            )
        ]
        
        # Create chronometer data for the test date
        chrono_data = [
            HealthData(
                date=test_date,
                source='chronometer',
                metric_name='energy',
                metric_value=2100,
                metric_units='kcal'
            ),
            HealthData(
                date=test_date,
                source='chronometer',
                metric_name='protein',
                metric_value=120,
                metric_units='g'
            )
        ]
        
        # Create data for a different date (to test navigation)
        next_date = test_date + timedelta(days=1)
        next_day_data = HealthData(
            date=next_date,
            source='oura',
            metric_name='sleep_score',
            metric_value=90,
            metric_units='score'
        )
        
        prev_date = test_date - timedelta(days=1)
        prev_day_data = HealthData(
            date=prev_date,
            source='oura',
            metric_name='sleep_score',
            metric_value=80,
            metric_units='score'
        )
        
        # Add all data to the database
        db.session.add_all(oura_data + chrono_data + [next_day_data, prev_day_data])
        db.session.commit()
        
        # Test default route (today's data)
        response = self.client.get('/data/date')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Health Data for', response.data)
        
        # Expected strings should be in the response
        month_name = test_date.strftime('%B')
        self.assertIn(month_name.encode(), response.data)
        self.assertIn(b'Oura', response.data)
        self.assertIn(b'Chronometer', response.data)
        
        # Test specific date route
        formatted_date = test_date.strftime('%Y-%m-%d')
        response = self.client.get(f'/data/date/{formatted_date}')
        self.assertEqual(response.status_code, 200)
        
        # Verify date display - use partial string to avoid locale issues
        self.assertIn(month_name.encode(), response.data)
        day_str = str(test_date.day).encode()
        year_str = str(test_date.year).encode()
        self.assertIn(day_str, response.data)
        self.assertIn(year_str, response.data)
        
        # Test navigation - verify URLs are in the response
        prev_date_str = prev_date.strftime('%Y-%m-%d')
        next_date_str = next_date.strftime('%Y-%m-%d')
        self.assertIn(f'href="/data/date/{prev_date_str}"'.encode(), response.data)
        self.assertIn(f'href="/data/date/{next_date_str}"'.encode(), response.data)
        
        # Test form submission
        response = self.client.post('/data/date', data={'date': formatted_date}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(month_name.encode(), response.data)
        
        # Test with invalid date format
        response = self.client.get('/data/date/invalid-date', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid date format', response.data)
    
    def test_date_view_no_data(self):
        """Test the date view when no data exists for a date."""
        # Use a date far in the future to ensure no data exists
        future_date = date.today() + timedelta(days=1000)
        formatted_date = future_date.strftime('%Y-%m-%d')
        
        # Ensure there's no data for this date by deleting any existing data
        HealthData.query.filter_by(date=future_date).delete()
        db.session.commit()
        
        response = self.client.get(f'/data/date/{formatted_date}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No health data found', response.data) 