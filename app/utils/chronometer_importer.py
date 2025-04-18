import pandas as pd
from datetime import datetime
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List, Any, Tuple

from .. import db
from ..models.base import HealthData, DataType

class ChronometerImporter:
    """
    Utility class for importing Chronometer nutrition and food category data from CSV files.

    Handles processing of CSV data, mapping to database models, and storing
    the information, including optimizations for performance and robust error handling.
    """

    SOURCE_NAME = 'chronometer'

    def __init__(self):
        """Initializes the importer and defines metric configurations."""
        # Consolidated configuration for metrics
        # Key: Canonical metric name used internally and in the database
        # Value: Dict with 'csv_col' (name in CSV), 'unit', and 'type' ('nutrition' or 'category')
        self.metrics_config: Dict[str, Dict[str, str]] = {
            'Energy': {'csv_col': 'Energy (kcal)', 'unit': 'kcal', 'type': 'nutrition'},
            'Alcohol': {'csv_col': 'Alcohol (g)', 'unit': 'g', 'type': 'nutrition'},
            'Protein': {'csv_col': 'Protein (g)', 'unit': 'g', 'type': 'nutrition'},
            'Carbs': {'csv_col': 'Carbs (g)', 'unit': 'g', 'type': 'nutrition'},
            'Net Carbs': {'csv_col': 'Net Carbs (g)', 'unit': 'g', 'type': 'nutrition'},
            'Fat': {'csv_col': 'Fat (g)', 'unit': 'g', 'type': 'nutrition'},
            'Monounsaturated Fat': {'csv_col': 'Monounsaturated (g)', 'unit': 'g', 'type': 'nutrition'},
            'Polyunsaturated Fat': {'csv_col': 'Polyunsaturated (g)', 'unit': 'g', 'type': 'nutrition'},
            'Saturated Fat': {'csv_col': 'Saturated (g)', 'unit': 'g', 'type': 'nutrition'},
            'Trans-Fats': {'csv_col': 'Trans-Fats (g)', 'unit': 'g', 'type': 'nutrition'},
            'Fiber': {'csv_col': 'Fiber (g)', 'unit': 'g', 'type': 'nutrition'},
            'Sugar': {'csv_col': 'Sugars (g)', 'unit': 'g', 'type': 'nutrition'}, # Note CSV name difference
            'Starch': {'csv_col': 'Starch (g)', 'unit': 'g', 'type': 'nutrition'},
            'Sodium': {'csv_col': 'Sodium (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Potassium': {'csv_col': 'Potassium (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Calcium': {'csv_col': 'Calcium (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Iron': {'csv_col': 'Iron (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Vitamin C': {'csv_col': 'Vitamin C (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Vitamin D': {'csv_col': 'Vitamin D (IU)', 'unit': 'IU', 'type': 'nutrition'},
            'Vitamin E': {'csv_col': 'Vitamin E (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Vitamin K': {'csv_col': 'Vitamin K (µg)', 'unit': 'µg', 'type': 'nutrition'},
            'Omega-3': {'csv_col': 'Omega-3 (g)', 'unit': 'g', 'type': 'nutrition'},
            'Omega-6': {'csv_col': 'Omega-6 (g)', 'unit': 'g', 'type': 'nutrition'},
            'Cholesterol': {'csv_col': 'Cholesterol (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Magnesium': {'csv_col': 'Magnesium (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Copper': {'csv_col': 'Copper (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Phosphorus': {'csv_col': 'Phosphorus (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Selenium': {'csv_col': 'Selenium (µg)', 'unit': 'µg', 'type': 'nutrition'},
            'Manganese': {'csv_col': 'Manganese (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Zinc': {'csv_col': 'Zinc (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'B12 (Cobalamin)': {'csv_col': 'B12 (Cobalamin) (µg)', 'unit': 'µg', 'type': 'nutrition'},
            'Choline': {'csv_col': 'Choline (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'Folate': {'csv_col': 'Folate (µg)', 'unit': 'µg', 'type': 'nutrition'},
            'B6 (Pyridoxine)': {'csv_col': 'B6 (Pyridoxine) (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'B1 (Thiamine)': {'csv_col': 'B1 (Thiamine) (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'B2 (Riboflavin)': {'csv_col': 'B2 (Riboflavin) (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'B3 (Niacin)': {'csv_col': 'B3 (Niacin) (mg)', 'unit': 'mg', 'type': 'nutrition'},
            'B5 (Pantothenic Acid)': {'csv_col': 'B5 (Pantothenic Acid) (mg)', 'unit': 'mg', 'type': 'nutrition'},
            # Configuration for food category processing
            'Food Category': {'csv_col': 'Category', 'unit': 'kcal', 'type': 'category', 'value_col': 'Energy (kcal)'}
        }

        # Extract nutrition-specific metrics for easier access
        self.nutrition_metrics: Dict[str, Dict[str, str]] = {
            k: v for k, v in self.metrics_config.items() if v['type'] == 'nutrition'
        }

    def import_from_csv(self, file_path: str, store_categories: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Import Chronometer data from a CSV file, process nutrition and categories, and store it.

        Args:
            file_path: Path to the Chronometer CSV file.

        Returns:
            A tuple containing two lists:
            1. Processed nutrition data points.
            2. Processed food category data points.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
            pd.errors.EmptyDataError: If the CSV file is empty.
            Exception: For other potential Pandas or file reading errors.
            SQLAlchemyError: If there's an issue during database operations.
        """
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                current_app.logger.warning(f"CSV file is empty: {file_path}")
                return [], []
        except FileNotFoundError:
            current_app.logger.error(f"CSV file not found: {file_path}")
            raise
        except pd.errors.EmptyDataError:
             current_app.logger.error(f"CSV file is empty or invalid: {file_path}")
             raise # Re-raise specific error
        except Exception as e:
            current_app.logger.error(f"Error reading CSV file '{file_path}': {e}")
            raise # Re-raise other read errors

        # --- Process Nutrition Data ---
        processed_nutrition = []
        try:
            processed_nutrition = self._process_nutrition_data(df.copy(), file_path) # Use copy to avoid side effects
            if processed_nutrition:
                 self._store_data(processed_nutrition, data_kind='nutrition')
                 current_app.logger.info(f"Successfully processed and stored {len(processed_nutrition)} nutrition data points from '{file_path}'.")
            else:
                 current_app.logger.info(f"No valid nutrition data found or processed from '{file_path}'.")
        except Exception as e:
            # Log error but continue to category processing if possible
            current_app.logger.error(f"Error processing nutrition data from '{file_path}': {e}", exc_info=True)


        # --- Process Food Category Data ---
        processed_categories = []
        try:
            processed_categories = self._process_food_categories(df.copy(), file_path) # Use copy
            if processed_categories and store_categories == True:
                self._store_data(processed_categories, data_kind='food category')
                current_app.logger.info(f"Successfully processed and stored {len(processed_categories)} food category data points from '{file_path}'.")
            else:
                 current_app.logger.info(f"No valid food category data found or processed from '{file_path}'.")
        except Exception as e:
            current_app.logger.error(f"Error processing food category data from '{file_path}': {e}", exc_info=True)
            # If storing nutrition succeeded but categories failed, the source timestamp might only reflect nutrition.
            # Consider if separate timestamp updates are needed or if partial success is acceptable.

        # --- Update Data Source Timestamp ---
        # Update timestamp only if at least one part succeeded without raising SQLAlchemyError during storage
        if processed_nutrition or processed_categories:
             try:
                 self._update_data_source()
             except Exception as e:
                 current_app.logger.error(f"Failed to update data source timestamp for '{self.SOURCE_NAME}': {e}", exc_info=True)


        return processed_nutrition, processed_categories

    def _validate_columns(self, df_columns: pd.Index, expected_mapping: Dict[str, str], file_path: str, data_kind: str) -> set:
        """Checks for missing expected columns and logs warnings."""
        actual_cols = set(df_columns)
        expected_cols = set(expected_mapping.values())
        missing_cols = expected_cols - actual_cols

        if 'Day' not in actual_cols:
             current_app.logger.error(f"Critical missing column 'Day' in {data_kind} data from '{file_path}'. Cannot process.")
             raise KeyError("Missing essential 'Day' column in CSV.")

        if missing_cols:
            current_app.logger.warning(
                f"File '{file_path}': Missing expected {data_kind} columns: {', '.join(sorted(list(missing_cols)))}. "
                f"Metrics associated with these columns will be skipped or treated as zero."
            )
        return actual_cols # Return the set of columns actually present

    def _process_nutrition_data(self, df: pd.DataFrame, file_path: str) -> List[Dict[str, Any]]:
        """Processes raw Chronometer nutrition CSV data using vectorized operations."""
        current_app.logger.debug(f"Starting nutrition data processing for '{file_path}'.")

        # Define expected columns based on nutrition metrics config
        expected_csv_cols_map = {metric: config['csv_col'] for metric, config in self.nutrition_metrics.items()}
        present_cols = self._validate_columns(df.columns, expected_csv_cols_map, file_path, 'nutrition')

        # Filter columns: Keep 'Day' and only the expected nutrition columns that are actually present
        cols_to_keep = ['Day'] + [csv_col for csv_col in expected_csv_cols_map.values() if csv_col in present_cols]
        df_filtered = df[cols_to_keep].copy() # Explicit copy

        # Convert 'Day' to datetime objects, coercing errors to NaT (Not a Time)
        df_filtered['date'] = pd.to_datetime(df_filtered['Day'], errors='coerce').dt.date
        # Drop rows where date conversion failed
        original_rows = len(df_filtered)
        df_filtered.dropna(subset=['date'], inplace=True)
        if len(df_filtered) < original_rows:
             current_app.logger.warning(f"File '{file_path}': Dropped {original_rows - len(df_filtered)} rows due to invalid date format in 'Day' column.")

        if df_filtered.empty:
            current_app.logger.warning(f"File '{file_path}': No valid rows remaining after date processing for nutrition data.")
            return []

        # Convert nutrient columns to numeric, coercing errors to NaN
        nutrient_csv_cols = [col for col in cols_to_keep if col != 'Day']
        for col in nutrient_csv_cols:
            # Attempt conversion, log errors for specific problematic values if needed
            try:
                df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
            except Exception as e: # Catch broader errors during conversion if necessary
                 current_app.logger.warning(f"File '{file_path}': Issue converting column '{col}' to numeric: {e}. Non-numeric values will be NaN.")
                 df_filtered[col] = pd.Series(index=df_filtered.index, dtype=float) # Ensure column exists as float type even if all fail

            # Optional: Log if conversion introduced NaNs (can be verbose)
            # if df_filtered[col].isnull().any():
            #     null_count = df_filtered[col].isnull().sum()
            #     current_app.logger.debug(f"File '{file_path}': Column '{col}' conversion resulted in {null_count} NaN values.")

        # Group by date and sum up values. Fill NaN with 0 before summing.
        # Using fillna(0) explicitly before sum handles cases where a whole day might have NaNs for a metric
        daily_totals = df_filtered.groupby('date')[nutrient_csv_cols].agg(lambda x: x.fillna(0).sum())


        # Rename columns from CSV names back to canonical metric names for melting
        # Create a reverse map: {csv_col: canonical_metric}
        reverse_col_map = {v['csv_col']: k for k, v in self.nutrition_metrics.items() if v['csv_col'] in daily_totals.columns}
        daily_totals.rename(columns=reverse_col_map, inplace=True)

        # Melt the DataFrame from wide to long format
        daily_totals_long = daily_totals.reset_index().melt(
            id_vars=['date'],
            var_name='metric_name',
            value_name='metric_value'
        )

        # Add units based on the canonical metric name
        daily_totals_long['metric_units'] = daily_totals_long['metric_name'].apply(
            lambda name: self.nutrition_metrics.get(name, {}).get('unit', '')
        )

        # Filter out rows where value is NaN (unlikely after fillna(0).sum() but safe)
        daily_totals_long.dropna(subset=['metric_value'], inplace=True)

        # Convert to list of dictionaries
        processed_data = daily_totals_long.to_dict('records')
        current_app.logger.debug(f"Finished nutrition data processing for '{file_path}'. Found {len(processed_data)} data points.")
        return processed_data


    def _process_food_categories(self, df: pd.DataFrame, file_path: str) -> List[Dict[str, Any]]:
        """Processes food category data using vectorized operations."""
        current_app.logger.debug(f"Starting food category processing for '{file_path}'.")
        category_config = self.metrics_config.get('Food Category')
        if not category_config:
             current_app.logger.error("Internal configuration error: 'Food Category' not found in metrics_config.")
             return []

        category_col = category_config['csv_col'] # 'Category'
        value_col = category_config['value_col']   # 'Energy (kcal)'
        unit = category_config['unit']             # 'kcal'

        # Validate required columns for category processing
        required_cols = {'Day', category_col, value_col}
        actual_cols = set(df.columns)
        missing_cols = required_cols - actual_cols

        if 'Day' not in actual_cols:
             current_app.logger.error(f"Critical missing column 'Day' in food category data from '{file_path}'. Cannot process.")
             raise KeyError("Missing essential 'Day' column in CSV for category processing.")
        if missing_cols:
             current_app.logger.warning(f"File '{file_path}': Missing columns required for category processing: {', '.join(sorted(list(missing_cols)))}. Processing may be incomplete.")
             # Decide if processing should stop or continue with available columns
             if category_col not in actual_cols or value_col not in actual_cols:
                 current_app.logger.error(f"File '{file_path}': Cannot process food categories due to missing '{category_col}' or '{value_col}'.")
                 return [] # Stop category processing if essential cols are missing

        cols_to_keep = ['Day'] + [col for col in [category_col, value_col] if col in actual_cols]
        df_filtered = df[cols_to_keep].copy()

        # Convert 'Day' to datetime objects, coercing errors to NaT
        df_filtered['date'] = pd.to_datetime(df_filtered['Day'], errors='coerce').dt.date
        original_rows = len(df_filtered)
        df_filtered.dropna(subset=['date'], inplace=True)
        if len(df_filtered) < original_rows:
             current_app.logger.warning(f"File '{file_path}': Dropped {original_rows - len(df_filtered)} rows due to invalid date format in 'Day' column during category processing.")

        if df_filtered.empty:
            current_app.logger.warning(f"File '{file_path}': No valid rows remaining after date processing for food categories.")
            return []

        # Handle missing categories and convert value column to numeric
        if category_col in df_filtered.columns:
            df_filtered[category_col] = df_filtered[category_col].fillna('Uncategorized')
        else:
             df_filtered[category_col] = 'Uncategorized' # Assign default if column was missing entirely

        if value_col in df_filtered.columns:
             try:
                 df_filtered[value_col] = pd.to_numeric(df_filtered[value_col], errors='coerce').fillna(0)
             except Exception as e:
                 current_app.logger.warning(f"File '{file_path}': Issue converting category value column '{value_col}' to numeric: {e}. Non-numeric values will be 0.")
                 df_filtered[value_col] = 0 # Ensure column is numeric type with 0 for errors
        else:
             df_filtered[value_col] = 0 # Assign 0 if value column was missing

        # Group by date and category, then sum the value column
        category_totals = df_filtered.groupby(['date', category_col])[value_col].sum().reset_index()

        # Rename columns and add metric details
        category_totals.rename(columns={value_col: 'metric_value', category_col: 'category'}, inplace=True)
        category_totals['metric_name'] = "Food Category: " + category_totals['category'].astype(str) # Ensure category is string
        category_totals['metric_units'] = unit

        # Select and order final columns
        processed_data = category_totals[['date', 'metric_name', 'metric_value', 'metric_units']].to_dict('records')

        current_app.logger.debug(f"Finished food category processing for '{file_path}'. Found {len(processed_data)} data points.")
        return processed_data


    def _store_data(self, processed_data: List[Dict[str, Any]], data_kind: str):
        """
        Stores processed data (either nutrition or category) in the database with optimizations.

        Args:
            processed_data: A list of dictionaries, each representing a data point.
                            Expected keys: 'date', 'metric_name', 'metric_value', 'metric_units'.
            data_kind: A string descriptor ('nutrition' or 'food category') for logging.

        Raises:
            SQLAlchemyError: If a database error occurs during the transaction.
        """
        if not processed_data:
            current_app.logger.info(f"No {data_kind} data provided to store.")
            return

        current_app.logger.debug(f"Starting database storage for {len(processed_data)} {data_kind} items.")
        # --- Step 1: Get or Create DataType entries ---
        metric_names = {item['metric_name'] for item in processed_data}
        existing_types = DataType.query.filter(
            DataType.source == self.SOURCE_NAME,
            DataType.metric_name.in_(metric_names)
        ).all()
        data_type_map: Dict[str, DataType] = {dt.metric_name: dt for dt in existing_types}

        new_types_to_add = []
        processed_metrics = set() # Track metrics already processed for adding new types
        for item in processed_data:
            metric_name = item['metric_name']
            if metric_name not in data_type_map and metric_name not in processed_metrics:
                new_type = DataType(
                    source=self.SOURCE_NAME,
                    metric_name=metric_name,
                    metric_units=item.get('metric_units', '') # Use .get for safety
                )
                new_types_to_add.append(new_type)
                processed_metrics.add(metric_name) # Mark as processed for this batch

        if new_types_to_add:
            try:
                db.session.add_all(new_types_to_add)
                db.session.flush() # Flush to get IDs and make them available
                current_app.logger.info(f"Added {len(new_types_to_add)} new DataType entries for {data_kind}.")
                # Add newly created types to the map
                for nt in new_types_to_add:
                    data_type_map[nt.metric_name] = nt
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(f"Database error adding new DataTypes for {data_kind}: {e}", exc_info=True)
                raise # Re-raise to indicate storage failure

        # --- Step 2: Prepare HealthData for Upsert ---
        updates = []
        inserts = []
        unique_dates = {item['date'] for item in processed_data}
        # Ensure data_type_map is up-to-date after potential additions
        data_type_ids = {dt.id for dt in data_type_map.values() if dt.id is not None} # Filter out None IDs if flush failed somehow

        if not data_type_ids:
             current_app.logger.warning(f"No valid DataType IDs found for {data_kind} data. Skipping HealthData storage.")
             return


        # Fetch existing HealthData records relevant to this batch
        existing_health_data_list = []
        try:
            existing_health_data_query = HealthData.query.filter(
                HealthData.data_type_id.in_(data_type_ids),
                HealthData.date.in_(unique_dates)
            )
            existing_health_data_list = existing_health_data_query.all()
        except SQLAlchemyError as e:
             current_app.logger.error(f"Database error fetching existing HealthData for {data_kind}: {e}", exc_info=True)
             raise # Re-raise as we cannot proceed reliably

        # Create a lookup map: (data_type_id, date) -> HealthData object
        existing_health_data_map: Dict[Tuple[int, datetime.date], HealthData] = {
            (hd.data_type_id, hd.date): hd for hd in existing_health_data_list
        }
        current_app.logger.debug(f"Fetched {len(existing_health_data_list)} existing HealthData records for potential update ({data_kind}).")


        for item in processed_data:
            metric_name = item['metric_name']
            data_type = data_type_map.get(metric_name)

            # Ensure data_type and its id are valid before proceeding
            if not data_type or data_type.id is None:
                 current_app.logger.warning(f"Skipping item due to missing or invalid DataType ID for metric '{metric_name}'. Item: {item}")
                 continue

            lookup_key = (data_type.id, item['date'])
            existing_record = existing_health_data_map.get(lookup_key)

            # Ensure metric_value is a float or can be converted; handle potential errors
            try:
                metric_value = float(item['metric_value'])
            except (ValueError, TypeError) as e:
                 current_app.logger.warning(f"Could not convert metric_value '{item['metric_value']}' to float for metric '{metric_name}' on date {item['date']}. Skipping record. Error: {e}")
                 continue # Skip this record

            if existing_record:
                # Update existing record only if value has changed
                if existing_record.metric_value != metric_value:
                    existing_record.metric_value = metric_value
                    # Ensure the fetched object is associated with the session if not already
                    if existing_record not in db.session:
                         db.session.add(existing_record)
            else:
                # Prepare for insert
                new_data = HealthData(
                    date=item['date'],
                    data_type_id=data_type.id, # Use the ID directly
                    metric_value=metric_value
                )
                inserts.append(new_data)


        # --- Step 3: Commit Changes ---
        try:
            if inserts:
                db.session.add_all(inserts)
                current_app.logger.info(f"Prepared {len(inserts)} new HealthData records for insertion ({data_kind}).")
            # Updates to existing_record objects are tracked by the session

            # Check if there are any pending changes before committing
            if db.session.new or db.session.dirty:
                 current_app.logger.debug(f"Session has {len(db.session.new)} new and {len(db.session.dirty)} dirty objects to commit for {data_kind}.")
                 db.session.commit()
                 current_app.logger.info(f"Successfully committed database changes for {data_kind}.")
            else:
                 current_app.logger.info(f"No database changes detected for {data_kind}. Commit skipped.")


        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Database error storing {data_kind} data: {e}", exc_info=True)
            raise # Re-raise the error after rollback


    def _update_data_source(self):
        """Updates the last import timestamp for all data types from this source."""
        try:
            # Ensure the update happens in a transaction
            DataType.update_last_import(self.SOURCE_NAME)
            db.session.commit() # Commit the timestamp update separately or as part of the main transaction
            current_app.logger.info(f"Updated last import timestamp for source '{self.SOURCE_NAME}'.")
        except SQLAlchemyError as e:
             db.session.rollback() # Rollback if timestamp update fails
             current_app.logger.error(f"Database error updating last import time for source '{self.SOURCE_NAME}': {e}", exc_info=True)
             # Decide if this error should be raised or just logged
             raise # Re-raise to signal potential issue
