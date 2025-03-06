from datetime import datetime, date
import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataSource, UserDefinedMetric

class ModelTestCase(BaseTestCase):
    """Test case for the database models."""
    
    def test_health_data_model(self):
        """Test HealthData model creation and querying."""
        # Create a test health data record
        health_data = HealthData(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=42.0,
            metric_units='test_units'
        )
        
        # Add and commit to the database
        db.session.add(health_data)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_data = HealthData.query.filter_by(metric_name='test_metric').first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_data)
        self.assertEqual(saved_data.source, 'test_source')
        self.assertEqual(saved_data.metric_value, 42.0)
        self.assertEqual(saved_data.metric_units, 'test_units')
        self.assertEqual(saved_data.date, date(2025, 3, 1))
    
    def test_data_source_model(self):
        """Test DataSource model creation and querying."""
        # Create a test data source
        data_source = DataSource(
            name='test_source',
            type='test',
            last_import=datetime.utcnow()
        )
        
        # Add and commit to the database
        db.session.add(data_source)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_source = DataSource.query.filter_by(name='test_source').first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_source)
        self.assertEqual(saved_source.name, 'test_source')
        self.assertEqual(saved_source.type, 'test')
        self.assertIsNotNone(saved_source.last_import)
    
    def test_user_defined_metric_model(self):
        """Test UserDefinedMetric model creation and querying."""
        # Create a test user-defined metric
        metric = UserDefinedMetric(
            name='test_metric',
            units='test_units',
            description='This is a test metric',
            frequency='daily'
        )
        
        # Add and commit to the database
        db.session.add(metric)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_metric = UserDefinedMetric.query.filter_by(name='test_metric').first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_metric)
        self.assertEqual(saved_metric.name, 'test_metric')
        self.assertEqual(saved_metric.units, 'test_units')
        self.assertEqual(saved_metric.description, 'This is a test metric')
        self.assertEqual(saved_metric.frequency, 'daily')
    
    def test_health_data_unique_constraint(self):
        """Test that the unique constraint on HealthData works."""
        # Create a health data record
        health_data1 = HealthData(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=42.0
        )
        
        # Add and commit to the database
        db.session.add(health_data1)
        db.session.commit()
        
        # Create another record with the same date, source, and metric_name
        health_data2 = HealthData(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=43.0
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(Exception):
            db.session.add(health_data2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback() 