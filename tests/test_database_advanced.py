from datetime import datetime, date, timedelta
import sys
import os
import time
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataSource, UserDefinedMetric, ImportRecord
from sqlalchemy import or_, and_, func, desc

class DatabaseAdvancedTestCase(BaseTestCase):
    """Test case for more advanced database operations."""
    
    def setUp(self):
        """Set up test data before each test."""
        super().setUp()
        
        # Add test data for performance and advanced query testing
        self._create_test_data()
    
    def _create_test_data(self):
        """Create a larger dataset for testing."""
        # Create multiple data sources
        sources = ['oura', 'chronometer', 'custom', 'fitbit']
        source_objects = []
        
        for source in sources:
            ds = DataSource(name=source, type='api' if source in ['oura', 'fitbit'] else 'csv' if source == 'chronometer' else 'manual')
            db.session.add(ds)
            source_objects.append(ds)
        
        # Create user-defined metrics
        metrics = [
            ('weight', 'kg', 'Body weight measurement', 'daily'),
            ('sleep_duration', 'hours', 'Total sleep time', 'daily'),
            ('steps', 'count', 'Steps taken during the day', 'daily'),
            ('calories', 'kcal', 'Calories consumed', 'daily'),
            ('protein', 'g', 'Protein consumed', 'daily')
        ]
        
        for name, units, desc, freq in metrics:
            metric = UserDefinedMetric(name=name, units=units, description=desc, frequency=freq)
            db.session.add(metric)
        
        # Generate health data for the past 30 days
        today = date.today()
        for i in range(30):
            # Date for this iteration
            day = today - timedelta(days=i)
            
            # Add weight data (from 'custom' source)
            weight = HealthData(
                date=day, 
                source='custom', 
                metric_name='weight',
                metric_value=70.0 + (i % 5 - 2),  # Small fluctuations
                metric_units='kg'
            )
            db.session.add(weight)
            
            # Add sleep data (from 'oura' source)
            if i % 7 != 0:  # Skip every 7th day to simulate missing data
                sleep = HealthData(
                    date=day, 
                    source='oura', 
                    metric_name='sleep_duration',
                    metric_value=7.5 + (i % 4 - 1.5),  # Fluctuations in sleep
                    metric_units='hours'
                )
                db.session.add(sleep)
            
            # Add steps data (from 'fitbit' source)
            steps = HealthData(
                date=day, 
                source='fitbit', 
                metric_name='steps',
                metric_value=8000 + (i * 100 % 4000 - 2000),  # Varying step counts
                metric_units='count'
            )
            db.session.add(steps)
            
            # Add nutrition data (from 'chronometer' source)
            calories = HealthData(
                date=day, 
                source='chronometer', 
                metric_name='calories',
                metric_value=2000 + (i * 50 % 500 - 250),  # Varying calorie intake
                metric_units='kcal'
            )
            db.session.add(calories)
            
            protein = HealthData(
                date=day, 
                source='chronometer', 
                metric_name='protein',
                metric_value=100 + (i * 5 % 40 - 20),  # Varying protein intake
                metric_units='g'
            )
            db.session.add(protein)
        
        # Add import records
        import_records = [
            ('oura_sleep', 'success', 26, today - timedelta(days=30), today),
            ('chronometer_csv', 'success', 60, today - timedelta(days=30), today),
            ('fitbit_activity', 'partial', 30, today - timedelta(days=30), today, 'Some data missing'),
            ('custom_weight', 'success', 30, today - timedelta(days=30), today)
        ]
        
        for rec in import_records:
            if len(rec) == 6:
                source, status, count, start, end, error = rec
            else:
                source, status, count, start, end = rec
                error = None
                
            ir = ImportRecord(
                source=source,
                date_imported=datetime.utcnow(),
                date_range_start=start,
                date_range_end=end,
                record_count=count,
                status=status,
                error_message=error
            )
            db.session.add(ir)
        
        # Commit all test data
        db.session.commit()
    
    def test_query_performance(self):
        """Test database query performance."""
        # Record start time
        start_time = time.time()
        
        # Query to get all health data from the past week
        today = date.today()
        one_week_ago = today - timedelta(days=7)
        results = HealthData.query.filter(HealthData.date >= one_week_ago).all()
        
        # Verify results
        self.assertGreaterEqual(len(results), 30)  # Should have at least 30 records (5 metrics * 6 days)
        
        # Check query execution time - should be fast (<0.1s) for this small dataset
        query_time = time.time() - start_time
        self.assertLess(query_time, 0.1)
    
    def test_complex_queries(self):
        """Test more complex queries."""
        # Get average weight per week
        query = db.session.query(
            func.strftime('%W', HealthData.date).label('week'),
            func.avg(HealthData.metric_value).label('avg_weight')
        ).filter(
            HealthData.metric_name == 'weight'
        ).group_by('week').order_by('week')
        
        results = query.all()
        self.assertGreater(len(results), 0)
        
        # Get correlation between sleep and weight
        # Get recent sleep data
        recent_sleep = HealthData.query.filter(
            HealthData.metric_name == 'sleep_duration',
            HealthData.source == 'oura'
        ).order_by(HealthData.date.desc()).limit(10).all()
        
        # Get corresponding weight data (same dates)
        sleep_dates = [s.date for s in recent_sleep]
        corresponding_weight = HealthData.query.filter(
            HealthData.metric_name == 'weight',
            HealthData.date.in_(sleep_dates)
        ).all()
        
        # Verify we have matching data
        self.assertGreaterEqual(len(corresponding_weight), len(recent_sleep) // 2)
    
    def test_database_constraints(self):
        """Test database constraints in more complex scenarios."""
        # Try to insert data for multiple sources on the same day
        today = date.today()
        # Same metric from different sources should work
        sleep_data1 = HealthData(
            date=today,
            source='manual_entry',  # New source
            metric_name='sleep_duration',  # Same metric exists from 'oura'
            metric_value=8.0,
            metric_units='hours'
        )
        
        db.session.add(sleep_data1)
        db.session.commit()
        
        # Verify it worked
        saved_data = HealthData.query.filter_by(
            date=today, 
            source='manual_entry',
            metric_name='sleep_duration'
        ).first()
        
        self.assertIsNotNone(saved_data)
        
        # Same metric, same source, but different date should work
        yesterday = today - timedelta(days=1)
        sleep_data2 = HealthData(
            date=yesterday,
            source='manual_entry',
            metric_name='sleep_duration',
            metric_value=7.0,
            metric_units='hours'
        )
        
        db.session.add(sleep_data2)
        db.session.commit()
        
        # Verify it worked
        saved_data2 = HealthData.query.filter_by(
            date=yesterday, 
            source='manual_entry',
            metric_name='sleep_duration'
        ).first()
        
        self.assertIsNotNone(saved_data2)
    
    def test_bulk_operations(self):
        """Test bulk insert and update operations."""
        # Bulk insert data
        bulk_data = []
        base_date = date.today() - timedelta(days=60)
        
        for i in range(10):
            entry_date = base_date + timedelta(days=i)
            bulk_data.append(HealthData(
                date=entry_date,
                source='bulk_test',
                metric_name='bulk_metric',
                metric_value=i * 10,
                metric_units='units'
            ))
        
        db.session.bulk_save_objects(bulk_data)
        db.session.commit()
        
        # Verify bulk insert
        bulk_entries = HealthData.query.filter_by(source='bulk_test').all()
        self.assertEqual(len(bulk_entries), 10)
        
        # Bulk update (would use SQLAlchemy core for real bulk updates,
        # but we'll simulate with multiple updates in one transaction)
        entries_to_update = HealthData.query.filter_by(source='bulk_test').all()
        for entry in entries_to_update:
            entry.metric_value += 5
        
        db.session.commit()
        
        # Verify bulk update
        updated_entries = HealthData.query.filter_by(source='bulk_test').all()
        for entry in updated_entries:
            self.assertEqual(entry.metric_value % 5, 0)  # All should now end with 5
            self.assertGreater(entry.metric_value, 0)
    
    def test_date_range_queries(self):
        """Test queries with date ranges."""
        # Get data for last 15 days
        today = date.today()
        start_date = today - timedelta(days=15)
        
        results = HealthData.query.filter(
            HealthData.date.between(start_date, today)
        ).order_by(HealthData.date).all()
        
        # Group by date and count
        dates = {}
        for result in results:
            if result.date not in dates:
                dates[result.date] = 0
            dates[result.date] += 1
        
        # Should have data for each day
        self.assertGreaterEqual(len(dates), 14)  # At least 14 days with data
        
        # Each day should have multiple metrics
        for date_key, count in dates.items():
            self.assertGreaterEqual(count, 3)  # At least 3 metrics per day
    
    def test_query_optimization(self):
        """Test query optimization techniques."""
        # Test using 'exists' subquery for efficiency
        exists_subquery = db.session.query(HealthData).filter(
            HealthData.source == 'oura',
            HealthData.date > date.today() - timedelta(days=7)
        ).exists()
        
        result = db.session.query(exists_subquery).scalar()
        self.assertTrue(result)
        
        # Test using a join query
        import_record = db.session.query(ImportRecord).filter(
            ImportRecord.source.like('oura%')
        ).first()
        
        self.assertIsNotNone(import_record)
        
        # Find records matching this import's date range
        if import_record and import_record.date_range_start and import_record.date_range_end:
            data = HealthData.query.filter(
                HealthData.source == 'oura',
                HealthData.date.between(import_record.date_range_start, import_record.date_range_end)
            ).all()
            
            self.assertGreater(len(data), 0) 