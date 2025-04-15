from datetime import datetime, date, timedelta
import sys
import os
import time
# Add the parent directory to the path to make app importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_base import BaseTestCase
from app import db
from app.models.base import HealthData, DataType
from sqlalchemy import or_, and_, func, desc

class DatabaseAdvancedTestCase(BaseTestCase):
    """Test case for more advanced database operations."""
    
    def setUp(self):
        """Set up test data before each test."""
        super().setUp()
        
        # Add test data for performance and advanced query testing
        self._create_test_data()
    
    def _create_test_data(self):
        """Create test data for advanced database tests"""
        # Create data sources
        sources = ['oura', 'chronometer', 'fitbit', 'custom']
        for source in sources:
            source_type = 'api' if source != 'custom' else 'manual'
            db.session.add(DataType(
                source=source,
                metric_name='source_info',
                source_type=source_type,
                last_import=datetime.now()
            ))
        
        # Create metrics
        metrics = [
            ('sleep_duration', 'hours', 'Sleep duration'),
            ('steps', 'count', 'Steps taken'),
            ('calories', 'kcal', 'Calories consumed'),
            ('weight', 'kg', 'Body weight'),
            ('protein', 'g', 'Protein consumed')
        ]
        
        # Create DataTypes for different metrics
        data_types = {}
        for source in sources:
            for metric_name, units, desc in metrics:
                # Only create some combinations to simulate real-world data 
                if (source == 'oura' and metric_name in ['sleep_duration', 'steps']) or \
                   (source == 'chronometer' and metric_name in ['calories', 'protein']) or \
                   (source == 'custom' and metric_name == 'weight') or \
                   (source == 'fitbit' and metric_name in ['steps', 'calories']):
                    data_type = DataType(
                        source=source,
                        metric_name=metric_name,
                        metric_units=units,
                        description=desc
                    )
                    db.session.add(data_type)
                    data_types[(source, metric_name)] = data_type
        
        db.session.flush()
        
        # Generate health data for the past 30 days
        today = date.today()
        for i in range(30):
            # Date for this iteration
            day = today - timedelta(days=i)
            
            # Add weight data (from 'custom' source)
            weight_data_type = data_types.get(('custom', 'weight'))
            if weight_data_type:
                weight = HealthData(
                    date=day, 
                    data_type=weight_data_type,
                    metric_value=70.0 + (i % 5 - 2)  # Small fluctuations
                )
                db.session.add(weight)
            
            # Add sleep data (from 'oura' source)
            sleep_data_type = data_types.get(('oura', 'sleep_duration'))
            if sleep_data_type:
                sleep = HealthData(
                    date=day, 
                    data_type=sleep_data_type,
                    metric_value=7.5 + (i % 3 - 1) * 0.5  # Range from 6.5 to 8.5 hours
                )
                db.session.add(sleep)
            
            # Add steps data (from both 'oura' and 'fitbit' sources)
            for source in ['oura', 'fitbit']:
                steps_data_type = data_types.get((source, 'steps'))
                if steps_data_type:
                    # Slightly different step counts from different sources
                    base_steps = 8000 + (i % 7 - 3) * 1000
                    variation = 200 if source == 'oura' else -200  # Simulate different tracking methods
                    
                    steps = HealthData(
                        date=day, 
                        data_type=steps_data_type,
                        metric_value=base_steps + variation
                    )
                    db.session.add(steps)
            
            # Add nutrition data (from 'chronometer' source)
            calories_data_type = data_types.get(('chronometer', 'calories'))
            if calories_data_type:
                calories = HealthData(
                    date=day, 
                    data_type=calories_data_type,
                    metric_value=2000 + (i % 5 - 2) * 200  # Range from 1600 to 2400 calories
                )
                db.session.add(calories)
            
            protein_data_type = data_types.get(('chronometer', 'protein'))
            if protein_data_type:
                protein = HealthData(
                    date=day, 
                    data_type=protein_data_type,
                    metric_value=80 + (i % 5 - 2) * 10  # Range from 60 to 100g protein
                )
                db.session.add(protein)

        # Commit all data
        db.session.commit()
    
    def test_query_performance(self):
        """Test database query performance."""
        # Measure time to query all health data
        start_time = time.time()
        results = HealthData.query.all()
        end_time = time.time()
        
        print(f"Time to query all health data: {end_time - start_time:.6f} seconds")
        self.assertGreater(len(results), 100)  # Should have at least 100 records
        
        # Test performance of a more complex query with joins
        start_time = time.time()
        results = db.session.query(HealthData, DataType).join(
            DataType, HealthData.data_type_id == DataType.id
        ).filter(
            DataType.source == 'oura',
            HealthData.date > date.today() - timedelta(days=10)
        ).all()
        end_time = time.time()
        
        print(f"Time for complex query: {end_time - start_time:.6f} seconds")
        self.assertGreaterEqual(len(results), 10)  # Should have some results
    
    def test_complex_queries(self):
        """Test more complex queries."""
        # Find days where step count and sleep duration were both recorded from Oura
        steps_data_type = DataType.query.filter_by(source='oura', metric_name='steps').first()
        sleep_data_type = DataType.query.filter_by(source='oura', metric_name='sleep_duration').first()
        
        if steps_data_type and sleep_data_type:
            query = db.session.query(HealthData.date).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.id == steps_data_type.id
            ).intersect(
                db.session.query(HealthData.date).join(
                    DataType, HealthData.data_type_id == DataType.id
                ).filter(
                    DataType.id == sleep_data_type.id
                )
            )
            
            days_with_both = query.all()
            self.assertGreaterEqual(len(days_with_both), 20)  # Should have at least 20 days with both
        
        # Find the average sleep duration
        if sleep_data_type:
            avg_sleep = db.session.query(func.avg(HealthData.metric_value)).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.id == sleep_data_type.id
            ).scalar()
            
            self.assertIsNotNone(avg_sleep)
            self.assertGreater(avg_sleep, 6.0)  # Average sleep should be more than 6 hours
            self.assertLess(avg_sleep, 9.0)  # Average sleep should be less than 9 hours
    
    def test_database_constraints(self):
        """Test database constraints in more complex scenarios."""
        # Test that HealthData.date and data_type_id combination must be unique
        
        # Create a new DataType specifically for this test
        test_data_type = DataType(
            source='constraint_test',
            metric_name='unique_test',
            metric_units='units'
        )
        db.session.add(test_data_type)
        db.session.commit()
        
        # Create a HealthData record
        test_date = date(2023, 1, 1)  # Use a specific date to avoid conflicts
        health_data = HealthData(
            date=test_date,
            data_type=test_data_type,
            metric_value=42.0
        )
        db.session.add(health_data)
        db.session.commit()
        
        # Create another record with the same date and data_type
        duplicate_data = HealthData(
            date=test_date,
            data_type=test_data_type,
            metric_value=43.0
        )
        
        # This should raise an exception due to the unique constraint
        with self.assertRaises(Exception):
            db.session.add(duplicate_data)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
        
        # Test DataType source and metric_name combination must be unique
        # Create a duplicate DataType with the same source and metric_name
        duplicate_type = DataType(
            source='constraint_test',
            metric_name='unique_test',
            metric_units='different_units'
        )
        
        # This should raise an exception due to the unique constraint
        with self.assertRaises(Exception):
            db.session.add(duplicate_type)
            db.session.commit()
        
        # Rollback the session to clean up
        db.session.rollback()
    
    def test_bulk_operations(self):
        """Test bulk insert and update operations."""
        # Create a data type for bulk testing
        bulk_data_type = DataType(
            source='bulk_test',
            metric_name='bulk_metric',
            metric_units='units'
        )
        db.session.add(bulk_data_type)
        db.session.commit()
        
        # Bulk insert 100 records
        start_time = time.time()
        
        # Create a list of dictionaries for bulk insert
        bulk_data = []
        for i in range(100):
            bulk_data.append({
                'date': date.today() - timedelta(days=i),
                'data_type_id': bulk_data_type.id,
                'metric_value': i,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
        
        # Use SQLAlchemy Core for bulk insert
        db.session.execute(
            HealthData.__table__.insert(),
            bulk_data
        )
        db.session.commit()
        
        end_time = time.time()
        print(f"Time for bulk insert of 100 records: {end_time - start_time:.6f} seconds")
        
        # Verify insert
        count = HealthData.query.filter(
            HealthData.data_type_id == bulk_data_type.id
        ).count()
        self.assertEqual(count, 100)
        
        # Bulk update (let's double all values)
        start_time = time.time()
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE health_data SET metric_value = metric_value * 2 WHERE data_type_id = :data_type_id"),
            {"data_type_id": bulk_data_type.id}
        )
        db.session.commit()
        end_time = time.time()
        
        print(f"Time for bulk update of 100 records: {end_time - start_time:.6f} seconds")
        
        # Verify update
        avg_value = db.session.query(func.avg(HealthData.metric_value)).join(
            DataType, HealthData.data_type_id == DataType.id
        ).filter(
            DataType.source == 'bulk_test'
        ).scalar()
        self.assertAlmostEqual(avg_value, 99.0, places=1)  # Average of 0-99 doubled is 99
    
    def test_date_range_queries(self):
        """Test queries with date ranges."""
        # Test querying data within a date range
        start_date = date.today() - timedelta(days=15)
        end_date = date.today() - timedelta(days=5)
        
        results = HealthData.query.filter(
            HealthData.date >= start_date,
            HealthData.date <= end_date
        ).all()
        
        # Should have data for each day in the range
        self.assertGreaterEqual(len(results), 10)
        
        # Test aggregation by date
        daily_counts = db.session.query(
            HealthData.date, func.count(HealthData.id)
        ).group_by(HealthData.date).all()
        
        # Should have multiple records per day
        self.assertGreater(len(daily_counts), 0)
        for day_data in daily_counts:
            self.assertGreaterEqual(day_data[1], 1)
    
    def test_query_optimization(self):
        """Test query optimization techniques."""
        # Test using eager loading to reduce the number of database queries
        
        # Without eager loading (will cause N+1 query problem)
        start_time = time.time()
        health_data = HealthData.query.limit(10).all()
        for record in health_data:
            # Accessing the relationship will trigger a separate query for each record
            data_type = record.data_type
            source = data_type.source if data_type else None
        end_time = time.time()
        time_without_eager = end_time - start_time
        
        # With eager loading
        start_time = time.time()
        health_data_eager = HealthData.query.options(db.joinedload(HealthData.data_type)).limit(10).all()
        for record in health_data_eager:
            # Data is already loaded, no additional queries needed
            data_type = record.data_type
            source = data_type.source if data_type else None
        end_time = time.time()
        time_with_eager = end_time - start_time
        
        # Eager loading should generally be faster, but not always in small datasets
        # due to overhead, so we just print the times for inspection
        print(f"Time without eager loading: {time_without_eager:.6f} seconds")
        print(f"Time with eager loading: {time_with_eager:.6f} seconds") 