from datetime import datetime, date
import sys
import os
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataSource, UserDefinedMetric, ImportRecord
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

class DatabaseTransactionTestCase(BaseTestCase):
    """Test case for database transactions and rollbacks."""
    
    def test_transaction_commit(self):
        """Test successful transaction commit."""
        # Start a transaction
        try:
            # Create multiple related records in one transaction
            data_source = DataSource(name='transaction_source', type='manual')
            db.session.add(data_source)
            
            # Create health data entries
            for i in range(3):
                health_data = HealthData(
                    date=date(2025, 3, i+1),
                    source='transaction_source',
                    metric_name=f'transaction_metric_{i}',
                    metric_value=i * 10.0,
                    metric_units='units'
                )
                db.session.add(health_data)
            
            # Create an import record
            import_record = ImportRecord(
                source='transaction_import',
                date_imported=datetime.utcnow(),
                date_range_start=date(2025, 3, 1),
                date_range_end=date(2025, 3, 3),
                record_count=3,
                status='success'
            )
            db.session.add(import_record)
            
            # Commit the transaction
            db.session.commit()
            
            # Verify all records were saved
            saved_source = DataSource.query.filter_by(name='transaction_source').first()
            self.assertIsNotNone(saved_source)
            
            health_entries = HealthData.query.filter_by(source='transaction_source').all()
            self.assertEqual(len(health_entries), 3)
            
            saved_import = ImportRecord.query.filter_by(source='transaction_import').first()
            self.assertIsNotNone(saved_import)
            
        except Exception as e:
            # Rollback in case of exception
            db.session.rollback()
            self.fail(f"Transaction failed unexpectedly: {e}")
    
    def test_transaction_rollback(self):
        """Test transaction rollback on error."""
        # First, add a data source that we can reference
        data_source = DataSource(name='rollback_source', type='manual')
        db.session.add(data_source)
        db.session.commit()
        
        # Start a new transaction that will fail
        initial_count = HealthData.query.count()
        
        try:
            # Add some valid health data
            health_data1 = HealthData(
                date=date(2025, 4, 1),
                source='rollback_source',
                metric_name='rollback_metric',
                metric_value=42.0,
                metric_units='units'
            )
            db.session.add(health_data1)
            
            health_data2 = HealthData(
                date=date(2025, 4, 2),
                source='rollback_source',
                metric_name='rollback_metric',
                metric_value=43.0,
                metric_units='units'
            )
            db.session.add(health_data2)
            
            # Add invalid data (will cause constraint violation)
            # Same date, source, and metric_name as health_data1
            invalid_data = HealthData(
                date=date(2025, 4, 1),
                source='rollback_source',
                metric_name='rollback_metric',
                metric_value=44.0,
                metric_units='units'
            )
            db.session.add(invalid_data)
            
            # This should fail and trigger a rollback
            db.session.commit()
            
            # We should never reach this assertion
            self.fail("Transaction should have failed but didn't")
            
        except IntegrityError:
            # Expected exception due to unique constraint violation
            db.session.rollback()
            
            # Verify no records were added (rollback worked)
            current_count = HealthData.query.count()
            self.assertEqual(current_count, initial_count)
            
            # Verify specific records aren't present
            rollback_data = HealthData.query.filter_by(
                date=date(2025, 4, 1),
                source='rollback_source',
                metric_name='rollback_metric'
            ).first()
            self.assertIsNone(rollback_data)
    
    def test_nested_transactions(self):
        """Test nested transactions using savepoints."""
        try:
            # Add a data source in the outer transaction
            data_source = DataSource(name='nested_source', type='api')
            db.session.add(data_source)
            
            # Savepoint - we can rollback to this point
            savepoint = db.session.begin_nested()
            
            try:
                # Add health data in the nested transaction
                health_data = HealthData(
                    date=date(2025, 5, 1),
                    source='nested_source',
                    metric_name='nested_metric',
                    metric_value=42.0,
                    metric_units='units'
                )
                db.session.add(health_data)
                
                # Force a constraint violation
                duplicate_data = HealthData(
                    date=date(2025, 5, 1),
                    source='nested_source',
                    metric_name='nested_metric',
                    metric_value=43.0,
                    metric_units='units'
                )
                db.session.add(duplicate_data)
                
                # This will fail due to the unique constraint
                savepoint.commit()
                
                # We should never reach this point
                self.fail("Nested transaction should have failed but didn't")
                
            except IntegrityError:
                # Expected exception
                savepoint.rollback()
                
                # The health data in the nested transaction should be rolled back
                # but the data source should still be pending
            
            # Commit the outer transaction - data source should be saved
            db.session.commit()
            
            # Verify that the data source was saved
            saved_source = DataSource.query.filter_by(name='nested_source').first()
            self.assertIsNotNone(saved_source)
            
            # Verify that the health data was not saved
            health_data = HealthData.query.filter_by(
                source='nested_source',
                metric_name='nested_metric'
            ).first()
            self.assertIsNone(health_data)
            
        except Exception as e:
            db.session.rollback()
            self.fail(f"Transaction failed unexpectedly: {e}")
    
    def test_object_state_tracking(self):
        """Test SQLAlchemy session's object state tracking."""
        # Create a data source
        source = DataSource(name='tracking_source', type='csv')
        db.session.add(source)
        db.session.commit()
        
        # Create and add health data
        health_data = HealthData(
            date=date(2025, 6, 1),
            source='tracking_source',
            metric_name='tracking_metric',
            metric_value=42.0,
            metric_units='units'
        )
        db.session.add(health_data)
        
        # Before commit, object should be in the session but not in the database
        session_object = db.session.query(HealthData).filter_by(
            source='tracking_source',
            metric_name='tracking_metric'
        ).first()
        self.assertIsNotNone(session_object)
        self.assertEqual(session_object, health_data)  # Should be the same object
        
        # Now commit
        db.session.commit()
        
        # After commit, modify the object
        health_data.metric_value = 50.0
        
        # Verify the change is tracked in the session
        modified_object = db.session.query(HealthData).filter_by(
            source='tracking_source',
            metric_name='tracking_metric'
        ).first()
        self.assertEqual(modified_object.metric_value, 50.0)
        
        # Commit changes
        db.session.commit()
        
        # Verify changes were persisted
        persisted_object = db.session.query(HealthData).filter_by(
            source='tracking_source',
            metric_name='tracking_metric'
        ).first()
        self.assertEqual(persisted_object.metric_value, 50.0)
        
        # Test making changes and rolling back
        health_data.metric_value = 60.0
        health_data.metric_units = 'new_units'
        
        # Rollback the changes
        db.session.rollback()
        
        # Verify original values are restored
        rolled_back = db.session.query(HealthData).filter_by(
            source='tracking_source',
            metric_name='tracking_metric'
        ).first()
        self.assertEqual(rolled_back.metric_value, 50.0)
        self.assertEqual(rolled_back.metric_units, 'units')
    
    def test_expiring_objects(self):
        """Test expiring objects to refresh from database."""
        # Create a data source
        source = DataSource(name='expire_source', type='manual')
        db.session.add(source)
        db.session.commit()
        
        # Create health data record
        health_data = HealthData(
            date=date(2025, 7, 1),
            source='expire_source',
            metric_name='expire_metric',
            metric_value=42.0,
            metric_units='units'
        )
        db.session.add(health_data)
        db.session.commit()
        
        # Store the ID for later retrieval
        data_id = health_data.id
        
        # Create a copy of the original value
        original_value = health_data.metric_value
        self.assertEqual(original_value, 42.0)
        
        # Detach the object from the session to prevent auto-refresh
        db.session.expunge(health_data)
        
        # Modify directly in the database using SQL (bypassing SQLAlchemy ORM)
        db.session.execute(
            text(f"UPDATE health_data SET metric_value = 100.0 WHERE id = {data_id}")
        )
        # Commit the SQL change
        db.session.commit()
        
        # Fetch the object again - should have the new value
        updated_data = db.session.query(HealthData).get(data_id)
        self.assertEqual(updated_data.metric_value, 100.0)
        
        # Original detached object should still have old value
        self.assertEqual(health_data.metric_value, 42.0)
    
    def test_cascading_delete(self):
        """Test cascading delete behavior."""
        # The models don't have cascading relationships defined,
        # but we can still test delete behavior with related records
        
        # Create a data source
        source_name = 'cascade_source'
        source = DataSource(name=source_name, type='api')
        db.session.add(source)
        db.session.commit()
        
        # Create health data records with this source
        for i in range(3):
            health_data = HealthData(
                date=date(2025, 8, i+1),
                source=source_name,
                metric_name=f'cascade_metric_{i}',
                metric_value=i * 10.0,
                metric_units='units'
            )
            db.session.add(health_data)
        db.session.commit()
        
        # Verify records exist
        health_entries = HealthData.query.filter_by(source=source_name).all()
        self.assertEqual(len(health_entries), 3)
        
        # Delete the source
        db.session.delete(source)
        db.session.commit()
        
        # Health data records should still exist (no cascade defined)
        # but we can manually delete them
        HealthData.query.filter_by(source=source_name).delete()
        db.session.commit()
        
        # Verify health data records are gone
        remaining_entries = HealthData.query.filter_by(source=source_name).all()
        self.assertEqual(len(remaining_entries), 0) 