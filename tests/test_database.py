from datetime import datetime, date, timedelta
import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataType, ImportRecord
from sqlalchemy.exc import IntegrityError

class DatabaseTestCase(BaseTestCase):
    """Comprehensive test case for the database models."""
    
    def test_health_data_model_crud(self):
        """Test CRUD operations for HealthData model."""
        # Create DataType first
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        db.session.add(data_type)
        db.session.flush()
        
        # CREATE
        health_data = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=42.0,
            notes='Test notes'
        )
        
        db.session.add(health_data)
        db.session.commit()
        
        # READ
        saved_data = HealthData.query.filter_by(id=health_data.id).first()
        
        # Assert all fields match
        self.assertIsNotNone(saved_data)
        self.assertEqual(saved_data.date, date(2025, 3, 1))
        self.assertEqual(saved_data.data_type.source, 'test_source')
        self.assertEqual(saved_data.data_type.metric_name, 'test_metric')
        self.assertEqual(saved_data.data_type.metric_units, 'test_units')
        self.assertEqual(saved_data.metric_value, 42.0)
        self.assertEqual(saved_data.notes, 'Test notes')
        
        # UPDATE
        saved_data.metric_value = 43.0
        db.session.commit()
        
        # Verify the update
        updated_data = HealthData.query.filter_by(id=health_data.id).first()
        self.assertEqual(updated_data.metric_value, 43.0)
        
        # DELETE
        db.session.delete(saved_data)
        db.session.commit()
        
        # Verify deletion
        deleted_data = HealthData.query.filter_by(id=health_data.id).first()
        self.assertIsNone(deleted_data)
    
    def test_data_type_source_methods(self):
        """Test the DataType methods for handling data sources."""
        # Create a test data type
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units',
            source_type='test_type',
            last_import=datetime(2025, 3, 1, 12, 0, 0)
        )
        
        db.session.add(data_type)
        db.session.commit()
        
        # Test get_data_source method - this should now create a source_info record
        DataType.update_last_import('test_source')
        
        # Now test get_data_source
        source = DataType.get_data_source('test_source')
        self.assertIsNotNone(source)
        self.assertEqual(source.source, 'test_source')
        self.assertEqual(source.metric_name, 'source_info')
        
        # Test update_last_import method again
        DataType.update_last_import('test_source')
        
        # Verify the update
        updated_source = DataType.query.filter_by(source='test_source', metric_name='source_info').first()
        self.assertIsNotNone(updated_source.last_import)
        self.assertGreater(updated_source.last_import, datetime(2025, 3, 1, 12, 0, 0))
        
        # Test update_last_import with a new source
        DataType.update_last_import('new_source')
        
        # Verify a placeholder was created
        new_source = DataType.query.filter_by(source='new_source').first()
        self.assertIsNotNone(new_source)
        self.assertEqual(new_source.metric_name, 'source_info')
        self.assertEqual(new_source.source_type, 'unknown')
    
    def test_import_record_model_crud(self):
        """Test CRUD operations for ImportRecord model."""
        # CREATE
        import_record = ImportRecord(
            source='test_source',
            date_imported=datetime(2025, 3, 1, 12, 0, 0),
            date_range_start=date(2025, 2, 1),
            date_range_end=date(2025, 2, 28),
            record_count=100,
            status='success'
        )
        
        db.session.add(import_record)
        db.session.commit()
        
        # READ
        saved_record = ImportRecord.query.filter_by(source='test_source').first()
        
        # Assert all fields match
        self.assertIsNotNone(saved_record)
        self.assertEqual(saved_record.source, 'test_source')
        self.assertEqual(saved_record.date_imported, datetime(2025, 3, 1, 12, 0, 0))
        self.assertEqual(saved_record.date_range_start, date(2025, 2, 1))
        self.assertEqual(saved_record.date_range_end, date(2025, 2, 28))
        self.assertEqual(saved_record.record_count, 100)
        self.assertEqual(saved_record.status, 'success')
        
        # UPDATE
        saved_record.record_count = 200
        db.session.commit()
        
        # Verify the update
        updated_record = ImportRecord.query.filter_by(source='test_source').first()
        self.assertEqual(updated_record.record_count, 200)
        
        # DELETE
        db.session.delete(saved_record)
        db.session.commit()
        
        # Verify deletion
        deleted_record = ImportRecord.query.filter_by(source='test_source').first()
        self.assertIsNone(deleted_record)
    
    def test_health_data_unique_constraint(self):
        """Test that the unique constraint on HealthData works."""
        # Create DataType first
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        db.session.add(data_type)
        db.session.flush()
        
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
        with self.assertRaises(IntegrityError):
            db.session.add(health_data2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_data_type_unique_constraint(self):
        """Test that the unique constraint on DataType source and metric_name works."""
        # Create a data type
        data_type1 = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        
        # Add and commit to the database
        db.session.add(data_type1)
        db.session.commit()
        
        # Create another data type with the same source and metric_name
        data_type2 = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='different_units'
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(IntegrityError):
            db.session.add(data_type2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_custom_metric_crud(self):
        """Test CRUD operations for custom metrics in DataType model."""
        # CREATE
        metric = DataType(
            source='custom',
            metric_name='test_metric',
            metric_units='test_units',
            description='Test description'
        )
        
        db.session.add(metric)
        db.session.commit()
        
        # READ
        saved_metric = DataType.query.filter_by(source='custom', metric_name='test_metric').first()
        
        # Assert all fields match
        self.assertIsNotNone(saved_metric)
        self.assertEqual(saved_metric.metric_name, 'test_metric')
        self.assertEqual(saved_metric.metric_units, 'test_units')
        self.assertEqual(saved_metric.description, 'Test description')

        # UPDATE
        saved_metric.metric_units = 'updated_units'
        saved_metric.description = 'Updated description'
        db.session.commit()
        
        # Read again to verify update
        updated_metric = DataType.query.get(saved_metric.id)
        self.assertEqual(updated_metric.metric_units, 'updated_units')
        self.assertEqual(updated_metric.description, 'Updated description')
        
        # DELETE
        db.session.delete(updated_metric)
        db.session.commit()
        
        # Verify deletion
        deleted_metric = DataType.query.get(updated_metric.id)
        self.assertIsNone(deleted_metric)
    
    def test_custom_metric_unique_constraint(self):
        """Test that the unique constraint on custom metrics works."""
        # Create a custom metric
        metric1 = DataType(
            source='custom',
            metric_name='test_metric',
            metric_units='test_units'
        )
        
        # Add and commit to the database
        db.session.add(metric1)
        db.session.commit()
        
        # Create another metric with the same source and metric_name
        metric2 = DataType(
            source='custom',
            metric_name='test_metric',
            metric_units='different_units'
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(IntegrityError):
            db.session.add(metric2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_model_relationships(self):
        """Test querying across models."""
        # Create DataType
        data_type = DataType(
            source='test_source',
            metric_name='test_metric',
            metric_units='test_units'
        )
        db.session.add(data_type)
        db.session.flush()
        
        # Create a health data record
        health_data = HealthData(
            date=date(2025, 3, 1),
            data_type=data_type,
            metric_value=42.0
        )
        
        # Add and commit to the database
        db.session.add(health_data)
        db.session.commit()
        
        # Query HealthData and join with DataType
        result = db.session.query(HealthData, DataType).join(
            DataType, HealthData.data_type_id == DataType.id
        ).filter(
            HealthData.date == date(2025, 3, 1),
            DataType.source == 'test_source',
            DataType.metric_name == 'test_metric'
        ).first()
        
        # Verify the query worked
        self.assertIsNotNone(result)
        self.assertEqual(result[0].metric_value, 42.0)
        self.assertEqual(result[1].source, 'test_source')
        self.assertEqual(result[1].metric_name, 'test_metric') 