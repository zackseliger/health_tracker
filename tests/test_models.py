from datetime import datetime, date
import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.exc import IntegrityError
from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataType

class ModelTestCase(BaseTestCase):
    """Test case for the database models."""
    
    def test_health_data_model(self):
        """Test HealthData model creation and querying."""
        # Create a test data type
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        db.session.add(data_type)
        db.session.commit()
        
        # Create a test health data record
        health_data = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=42.0
        )
        
        # Add and commit to the database
        db.session.add(health_data)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_data = HealthData.query.first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_data)
        self.assertEqual(saved_data.data_type.source, 'test_source')
        self.assertEqual(saved_data.data_type.metric_name, 'test_metric')
        self.assertEqual(saved_data.data_type.metric_units, 'test_units')
        self.assertEqual(saved_data.metric_value, 42.0)
        self.assertEqual(saved_data.date, date(2025, 3, 1))
    
    def test_data_type_model(self):
        """Test DataType model creation and querying."""
        # Create a test data type
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        
        # Add and commit to the database
        db.session.add(data_type)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_type = DataType.query.filter_by(source='test_source', metric_name='test_metric').first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_type)
        self.assertEqual(saved_type.source, 'test_source')
        self.assertEqual(saved_type.metric_name, 'test_metric')
        self.assertEqual(saved_type.metric_units, 'test_units')
    
    def test_health_data_factory_method(self):
        """Test the HealthData.create factory method."""
        # Use the factory method to create a health data record
        health_data = HealthData.create(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=42.0,
            metric_units='test_units'
        )
        
        # Add and commit to the database
        db.session.add(health_data)
        db.session.commit()
        
        # Query the database to verify both records were saved
        data_type = DataType.query.filter_by(source='test_source', metric_name='test_metric').first()
        saved_data = HealthData.query.first()
        
        # Assert that both records exist and have the correct attributes
        self.assertIsNotNone(data_type)
        self.assertEqual(data_type.source, 'test_source')
        self.assertEqual(data_type.metric_name, 'test_metric')
        self.assertEqual(data_type.metric_units, 'test_units')
        
        self.assertIsNotNone(saved_data)
        self.assertEqual(saved_data.data_type.source, 'test_source')
        self.assertEqual(saved_data.metric_value, 42.0)
        self.assertEqual(saved_data.date, date(2025, 3, 1))
    
    def test_data_source_model(self):
        """Test that we can create and query DataType records."""
        # Create a source info data type
        data_type = DataType(
            source='test_source',
            metric_name='source_info',
            metric_units=None,
            source_type='api',
            last_import=datetime(2025, 3, 1, 12, 0, 0)
        )
        
        # Add and commit to the database
        db.session.add(data_type)
        db.session.commit()
        
        # Get the source using the class method
        source = DataType.get_data_source('test_source')
        
        # Assert the source was found
        self.assertIsNotNone(source)
        self.assertEqual(source.source, 'test_source')
        self.assertEqual(source.metric_name, 'source_info')
        self.assertEqual(source.source_type, 'api')
        
        # Test the update method
        DataType.update_last_import('test_source')
        
        # Verify the update
        updated_source = DataType.query.filter_by(source='test_source', metric_name='source_info').first()
        self.assertIsNotNone(updated_source)
        self.assertGreater(updated_source.last_import, datetime(2025, 3, 1, 12, 0, 0))
    
    def test_custom_metric_in_data_type(self):
        """Test creating and querying custom metrics using DataType."""
        # Create a test custom metric
        metric = DataType(
            source='custom',
            metric_name='test_metric',
            metric_units='test_units',
            description='This is a test metric'
        )
        
        # Add and commit to the database
        db.session.add(metric)
        db.session.commit()
        
        # Query the database to verify the record was saved
        saved_metric = DataType.query.filter_by(source='custom', metric_name='test_metric').first()
        
        # Assert that the record exists and has the correct attributes
        self.assertIsNotNone(saved_metric)
        self.assertEqual(saved_metric.metric_name, 'test_metric')
        self.assertEqual(saved_metric.metric_units, 'test_units')
        self.assertEqual(saved_metric.description, 'This is a test metric')
    
    def test_health_data_unique_constraint(self):
        """Test that the unique constraint on HealthData works."""
        # Create a data type
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        db.session.add(data_type)
        db.session.commit()
        
        # Create a health data record
        health_data1 = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=42.0
        )
        
        # Add and commit to the database
        db.session.add(health_data1)
        db.session.commit()
        
        # Create another record with the same date and data_type
        health_data2 = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=43.0
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(Exception):
            db.session.add(health_data2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback() 