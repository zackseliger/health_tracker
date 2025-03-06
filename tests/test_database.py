from datetime import datetime, date, timedelta
import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataSource, UserDefinedMetric, ImportRecord
from sqlalchemy.exc import IntegrityError

class DatabaseTestCase(BaseTestCase):
    """Comprehensive test case for the database models."""
    
    def test_health_data_model_crud(self):
        """Test CRUD operations for HealthData model."""
        # CREATE
        health_data = HealthData(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=42.0,
            metric_units='test_units',
            notes='Test notes'
        )
        
        db.session.add(health_data)
        db.session.commit()
        
        # READ
        retrieved_data = HealthData.query.filter_by(metric_name='test_metric').first()
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data.source, 'test_source')
        self.assertEqual(retrieved_data.metric_value, 42.0)
        self.assertEqual(retrieved_data.notes, 'Test notes')
        
        # UPDATE
        retrieved_data.metric_value = 50.0
        retrieved_data.notes = 'Updated notes'
        db.session.commit()
        
        updated_data = HealthData.query.get(retrieved_data.id)
        self.assertEqual(updated_data.metric_value, 50.0)
        self.assertEqual(updated_data.notes, 'Updated notes')
        
        # DELETE
        db.session.delete(updated_data)
        db.session.commit()
        
        deleted_data = HealthData.query.get(retrieved_data.id)
        self.assertIsNone(deleted_data)
    
    def test_data_source_model_crud(self):
        """Test CRUD operations for DataSource model."""
        # CREATE
        now = datetime.utcnow()
        data_source = DataSource(
            name='test_source',
            type='api',
            last_import=now
        )
        
        db.session.add(data_source)
        db.session.commit()
        
        # READ
        retrieved_source = DataSource.query.filter_by(name='test_source').first()
        self.assertIsNotNone(retrieved_source)
        self.assertEqual(retrieved_source.type, 'api')
        self.assertEqual(retrieved_source.last_import, now)
        
        # UPDATE
        new_time = datetime.utcnow()
        retrieved_source.type = 'csv'
        retrieved_source.last_import = new_time
        db.session.commit()
        
        updated_source = DataSource.query.get(retrieved_source.id)
        self.assertEqual(updated_source.type, 'csv')
        self.assertEqual(updated_source.last_import, new_time)
        
        # DELETE
        db.session.delete(updated_source)
        db.session.commit()
        
        deleted_source = DataSource.query.get(retrieved_source.id)
        self.assertIsNone(deleted_source)
    
    def test_user_defined_metric_model_crud(self):
        """Test CRUD operations for UserDefinedMetric model."""
        # CREATE
        metric = UserDefinedMetric(
            name='test_metric',
            units='kg',
            description='Weight measurement',
            frequency='daily'
        )
        
        db.session.add(metric)
        db.session.commit()
        
        # READ
        retrieved_metric = UserDefinedMetric.query.filter_by(name='test_metric').first()
        self.assertIsNotNone(retrieved_metric)
        self.assertEqual(retrieved_metric.units, 'kg')
        self.assertEqual(retrieved_metric.description, 'Weight measurement')
        self.assertEqual(retrieved_metric.frequency, 'daily')
        
        # UPDATE
        retrieved_metric.units = 'lbs'
        retrieved_metric.frequency = 'weekly'
        db.session.commit()
        
        updated_metric = UserDefinedMetric.query.get(retrieved_metric.id)
        self.assertEqual(updated_metric.units, 'lbs')
        self.assertEqual(updated_metric.frequency, 'weekly')
        
        # DELETE
        db.session.delete(updated_metric)
        db.session.commit()
        
        deleted_metric = UserDefinedMetric.query.get(retrieved_metric.id)
        self.assertIsNone(deleted_metric)
    
    def test_import_record_model_crud(self):
        """Test CRUD operations for ImportRecord model."""
        # CREATE
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        import_record = ImportRecord(
            source='oura_sleep',
            date_imported=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
            record_count=42,
            status='success'
        )
        
        db.session.add(import_record)
        db.session.commit()
        
        # READ
        retrieved_record = ImportRecord.query.filter_by(source='oura_sleep').first()
        self.assertIsNotNone(retrieved_record)
        self.assertEqual(retrieved_record.record_count, 42)
        self.assertEqual(retrieved_record.status, 'success')
        self.assertEqual(retrieved_record.date_range_start, start_date)
        self.assertEqual(retrieved_record.date_range_end, end_date)
        
        # UPDATE
        retrieved_record.record_count = 50
        retrieved_record.status = 'partial'
        retrieved_record.error_message = 'Some data could not be imported'
        db.session.commit()
        
        updated_record = ImportRecord.query.get(retrieved_record.id)
        self.assertEqual(updated_record.record_count, 50)
        self.assertEqual(updated_record.status, 'partial')
        self.assertEqual(updated_record.error_message, 'Some data could not be imported')
        
        # DELETE
        db.session.delete(updated_record)
        db.session.commit()
        
        deleted_record = ImportRecord.query.get(retrieved_record.id)
        self.assertIsNone(deleted_record)
    
    def test_health_data_unique_constraint(self):
        """Test that the unique constraint on HealthData works."""
        # Create a health data record
        health_data1 = HealthData(
            date=date(2025, 3, 1),
            source='test_source',
            metric_name='test_metric',
            metric_value=42.0
        )
        
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
        with self.assertRaises(IntegrityError):
            db.session.add(health_data2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_data_source_unique_name_constraint(self):
        """Test that the unique constraint on DataSource name works."""
        # Create a data source
        source1 = DataSource(
            name='unique_source',
            type='api'
        )
        
        db.session.add(source1)
        db.session.commit()
        
        # Create another data source with the same name
        source2 = DataSource(
            name='unique_source',
            type='csv'
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(IntegrityError):
            db.session.add(source2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_user_defined_metric_unique_name_constraint(self):
        """Test that the unique constraint on UserDefinedMetric name works."""
        # Create a user-defined metric
        metric1 = UserDefinedMetric(
            name='unique_metric',
            units='kg'
        )
        
        db.session.add(metric1)
        db.session.commit()
        
        # Create another user-defined metric with the same name
        metric2 = UserDefinedMetric(
            name='unique_metric',
            units='lbs'
        )
        
        # This should raise an IntegrityError due to the unique constraint
        with self.assertRaises(IntegrityError):
            db.session.add(metric2)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_model_relationships(self):
        """Test querying across models."""
        # Create a data source
        source = DataSource(
            name='relationship_test',
            type='api'
        )
        
        db.session.add(source)
        db.session.commit()
        
        # Create multiple health data entries with the same source
        for i in range(3):
            health_data = HealthData(
                date=date(2025, 3, i+1),
                source='relationship_test',
                metric_name=f'metric_{i}',
                metric_value=i * 10
            )
            db.session.add(health_data)
        db.session.commit()
        
        # Query health data by source
        health_entries = HealthData.query.filter_by(source='relationship_test').all()
        self.assertEqual(len(health_entries), 3)
        
        # Check that values are correct
        values = sorted([entry.metric_value for entry in health_entries])
        self.assertEqual(values, [0.0, 10.0, 20.0]) 