import pandas as pd
from datetime import datetime
from flask import current_app
from .. import db
from ..models.base import HealthData, DataType


class ChronometerImporter:
    """Utility class for importing Chronometer data from CSV files"""
    
    def __init__(self):
        # Define nutrition metrics we want to extract
        self.nutrition_metrics = [
            'Energy (kcal)',
            'Alcohol (g)',
            'Protein (g)',
            'Carbs (g)',
            'Fat (g)', 
            'Fiber (g)',
            'Sugar (g)',
            'Sodium (mg)',
            'Potassium (mg)',
            'Calcium (mg)',
            'Iron (mg)',
            'Vitamin C (mg)',
            'Vitamin D (IU)',
            'Vitamin K (µg)',
            'Omega-3 (g)',
            'Omega-6 (g)',
            'Cholesterol (mg)',
            'Magnesium (mg)',
            'Phosphorus (mg)',
            'Manganese (mg)',
            'Zinc (mg)',
            'B12 (Cobalamin) (µg)',
            'Folate (µg)',
            'B6 (Pyridoxine) (mg)',
            'B1 (Thiamine) (mg)',
            'B2 (Riboflavin) (mg)',
            'B3 (Niacin) (mg)',
            'B5 (Pantothenic Acid) (mg)'
        ]
        
        # Mapping from nutrition metrics to column names in CSV
        self.column_mapping = {
            'Energy (kcal)': 'Energy (kcal)',
            'Alcohol (g)': 'Alcohol (g)',
            'Protein (g)': 'Protein (g)',
            'Carbs (g)': 'Carbs (g)',
            'Fat (g)': 'Fat (g)',
            'Fiber (g)': 'Fiber (g)',
            'Sugar (g)': 'Sugars (g)',
            'Sodium (mg)': 'Sodium (mg)',
            'Potassium (mg)': 'Potassium (mg)',
            'Calcium (mg)': 'Calcium (mg)',
            'Iron (mg)': 'Iron (mg)',
            'Vitamin C (mg)': 'Vitamin C (mg)',
            'Vitamin D (IU)': 'Vitamin D (IU)',
            'Vitamin K (µg)': 'Vitamin K (µg)',
            'Omega-3 (g)': 'Omega-3 (g)',
            'Omega-6 (g)': 'Omega-6 (g)',
            'Cholesterol (mg)': 'Cholesterol (mg)',
            'Magnesium (mg)': 'Magnesium (mg)',
            'Phosphorus (mg)': 'Phosphorus (mg)',
            'Manganese (mg)': 'Manganese (mg)',
            'Zinc (mg)': 'Zinc (mg)',
            'B12 (Cobalamin) (µg)': 'B12 (Cobalamin) (µg)',
            'Folate (µg)': 'Folate (µg)',
            'B6 (Pyridoxine) (mg)': 'B6 (Pyridoxine) (mg)',
            'B1 (Thiamine) (mg)': 'B1 (Thiamine) (mg)',
            'B2 (Riboflavin) (mg)': 'B2 (Riboflavin) (mg)',
            'B3 (Niacin) (mg)': 'B3 (Niacin) (mg)',
            'B5 (Pantothenic Acid) (mg)': 'B5 (Pantothenic Acid) (mg)'
        }
        
        # Mapping of units
        self.units_mapping = {
            'Energy (kcal)': 'kcal',
            'Alcohol (g)': 'g',
            'Protein (g)': 'g',
            'Carbs (g)': 'g',
            'Fat (g)': 'g',
            'Fiber (g)': 'g',
            'Sugar (g)': 'g',
            'Sodium (mg)': 'mg',
            'Potassium (mg)': 'mg',
            'Calcium (mg)': 'mg',
            'Iron (mg)': 'mg',
            'Vitamin C (mg)': 'mg',
            'Vitamin D (IU)': 'IU',
            'Vitamin K (µg)': 'µg',
            'Omega-3 (g)': 'g',
            'Omega-6 (g)': 'g',
            'Cholesterol (mg)': 'mg',
            'Magnesium (mg)': 'mg',
            'Phosphorus (mg)': 'mg',
            'Manganese (mg)': 'mg',
            'Zinc (mg)': 'mg',
            'B12 (Cobalamin) (µg)': 'µg',
            'Folate (µg)': 'µg',
            'B6 (Pyridoxine) (mg)': 'mg',
            'B1 (Thiamine) (mg)': 'mg',
            'B2 (Riboflavin) (mg)': 'mg',
            'B3 (Niacin) (mg)': 'mg',
            'B5 (Pantothenic Acid) (mg)': 'mg'
        }
    
    def import_from_csv(self, file_path):
        """Import Chronometer data from a CSV file"""
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            current_app.logger.error(f"Error reading CSV file: {e}")
            raise
        
        # Process the data
        processed_data = self._process_csv_data(df)
        
        # Store the data
        self._store_data(processed_data)
        
        return processed_data
    
    def _process_csv_data(self, df):
        """Process raw Chronometer CSV data into a format for our database"""
        processed_data = []
        
        # Get daily totals for each nutrient
        daily_totals = {}
        
        for _, row in df.iterrows():
            # Convert date string to datetime object
            try:
                date_str = row['Day']
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (KeyError, ValueError) as e:
                current_app.logger.error(f"Error processing date: {e}")
                continue
            
            # Initialize daily totals for this date if not already there
            if date_obj not in daily_totals:
                daily_totals[date_obj] = {metric: 0 for metric in self.nutrition_metrics}
            
            # Sum up nutritional values for the day
            for metric in self.nutrition_metrics:
                col_name = self.column_mapping.get(metric)
                if col_name in df.columns and not pd.isna(row[col_name]):
                    daily_totals[date_obj][metric] += float(row[col_name])
        
        # Convert daily totals to list of data points
        for date_obj, metrics in daily_totals.items():
            for metric, value in metrics.items():
                processed_data.append({
                    'date': date_obj,
                    'metric_name': metric,
                    'metric_value': value,
                    'metric_units': self.units_mapping.get(metric, '')
                })
        
        return processed_data
    
    def _store_data(self, processed_data):
        """Store processed data in the database"""
        for item in processed_data:
            # Get or create the DataType
            data_type = DataType.query.filter_by(
                source='chronometer',
                metric_name=item['metric_name']
            ).first()
            
            if not data_type:
                data_type = DataType(
                    source='chronometer',
                    metric_name=item['metric_name'],
                    metric_units=item.get('metric_units')
                )
                db.session.add(data_type)
                db.session.flush()  # Flush to get the ID
            
            # Check if record already exists
            existing = HealthData.query.join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                HealthData.date == item['date'],
                DataType.source == 'chronometer',
                DataType.metric_name == item['metric_name']
            ).first()
            
            if existing:
                # Update existing record
                existing.metric_value = item['metric_value']
            else:
                # Create new record
                new_data = HealthData(
                    date=item['date'],
                    data_type=data_type,
                    metric_value=item['metric_value']
                )
                db.session.add(new_data)
        
        db.session.commit()
        
        # Update the data source last import date
        self._update_data_source('chronometer')
        
        return processed_data
    
    def _update_data_source(self, source_name):
        """Update the last import timestamp for data types from this source"""
        DataType.update_last_import(source_name)
    
    def process_food_categories(self, df):
        """Process food categories from Chronometer data"""
        category_totals = {}
        
        for _, row in df.iterrows():
            try:
                date_str = row['Day']
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                category = row.get('Category', 'Uncategorized')
                energy = row.get('Energy (kcal)', 0)
                
                if pd.isna(category):
                    category = 'Uncategorized'
                    
                if pd.isna(energy):
                    energy = 0
                
                # Initialize category tracking for this date
                if date_obj not in category_totals:
                    category_totals[date_obj] = {}
                
                # Add calories to the category
                if category not in category_totals[date_obj]:
                    category_totals[date_obj][category] = 0
                
                category_totals[date_obj][category] += float(energy)
                
            except (KeyError, ValueError) as e:
                current_app.logger.error(f"Error processing food category: {e}")
                continue
        
        # Convert category totals to data points
        processed_data = []
        
        for date_obj, categories in category_totals.items():
            for category, energy in categories.items():
                metric_name = f"Food Category: {category}"
                processed_data.append({
                    'date': date_obj,
                    'metric_name': metric_name,
                    'metric_value': energy,
                    'metric_units': 'kcal'
                })
        
        # Store the data
        self._store_data(processed_data)
        
        return processed_data 