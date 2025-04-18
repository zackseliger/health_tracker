# This script is for ad-hoc database queries and analysis.
# It connects to the application's database and allows for custom calculations.

import sys
import os
import pandas as pd # Import pandas

# Add the parent directory to the system path to allow importing app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.base import db, HealthData, DataType # Import db, HealthData, DataType

# Create a minimal app context to access the database
# This assumes your app uses Flask-SQLAlchemy or similar and initializes db via app
app = create_app()
app.app_context().push()

# --- Example Queries ---

def calculate_average_sleep_score_when_sedentary_low(sedentary_threshold_hours=8):
    """
    Calculates the average sleep score for days where sedentary time is below a threshold.
    This is a placeholder and requires actual Sleep and Activity models with relevant fields.
    """
    print(f"Calculating average sleep score when sedentary time < {sedentary_threshold_hours} hours...")

    try:
        # Define data type IDs
        sedentary_time_type_id = 91
        sleep_score_type_id = 57

        # Fetch sedentary time data
        sedentary_data = db.session.query(
            HealthData.date,
            HealthData.metric_value
        ).filter(
            HealthData.data_type_id == sedentary_time_type_id
        ).order_by(HealthData.date).all()

        # Fetch sleep score data
        sleep_score_data = db.session.query(
            HealthData.date,
            HealthData.metric_value
        ).filter(
            HealthData.data_type_id == sleep_score_type_id
        ).order_by(HealthData.date).all()

        # Convert to pandas Series, indexed by date
        sedentary_series = pd.Series(
            [d.metric_value for d in sedentary_data],
            index=pd.to_datetime([d.date for d in sedentary_data])
        )
        sleep_score_series = pd.Series(
            [d.metric_value for d in sleep_score_data],
            index=pd.to_datetime([d.date for d in sleep_score_data])
        )

        # Merge the two series on date. This drops dates missing in either.
        # Use 'outer' merge and then dropna to be explicit about dropping missing pairs
        merged_df = pd.merge(
            sedentary_series.rename('sedentary_time'),
            sleep_score_series.rename('sleep_score'),
            left_index=True,
            right_index=True,
            how='outer' # Use outer to see all dates, then dropna
        ).dropna() # Drop rows where either metric is missing

        if merged_df.empty:
            print("No common dates with both sedentary time and sleep score data found.")
            return

        # Shift the sleep score by 1 day forward (index shift of -1)
        merged_df['sleep_score_shifted'] = merged_df['sleep_score'].shift(-1)

        # Drop the last row which will have a NaN shifted sleep score
        merged_df = merged_df.dropna(subset=['sleep_score_shifted'])

        if merged_df.empty:
            print("No data points remaining after shifting sleep score and dropping missing values.")
            return

        # Filter data where sedentary time is less than the threshold
        filtered_df = merged_df[merged_df['sedentary_time'] < sedentary_threshold_hours]

        if filtered_df.empty:
            print(f"No data found where sedentary time was less than {sedentary_threshold_hours} hours.")
            return

        # Calculate the average sleep score from the filtered data
        average_score = filtered_df['sleep_score_shifted'].mean()

        print(f"Found {len(filtered_df)} matching entries after filtering and shifting.")
        print(f"Average Sleep Score (shifted) when Sedentary Time < {sedentary_threshold_hours} hours: {average_score:.2f}")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.session.rollback() # Rollback in case of error

def calculate_average_sleep_score_when_sedentary_high(sedentary_threshold_hours=12):
    """
    Calculates the average sleep score for days where sedentary time is below a threshold.
    This is a placeholder and requires actual Sleep and Activity models with relevant fields.
    """
    print(f"Calculating average sleep score when sedentary time > {sedentary_threshold_hours} hours...")

    try:
        # Define data type IDs
        sedentary_time_type_id = 91
        sleep_score_type_id = 57

        # Fetch sedentary time data
        sedentary_data = db.session.query(
            HealthData.date,
            HealthData.metric_value
        ).filter(
            HealthData.data_type_id == sedentary_time_type_id
        ).order_by(HealthData.date).all()

        # Fetch sleep score data
        sleep_score_data = db.session.query(
            HealthData.date,
            HealthData.metric_value
        ).filter(
            HealthData.data_type_id == sleep_score_type_id
        ).order_by(HealthData.date).all()

        # Convert to pandas Series, indexed by date
        sedentary_series = pd.Series(
            [d.metric_value for d in sedentary_data],
            index=pd.to_datetime([d.date for d in sedentary_data])
        )
        sleep_score_series = pd.Series(
            [d.metric_value for d in sleep_score_data],
            index=pd.to_datetime([d.date for d in sleep_score_data])
        )

        # Merge the two series on date. This drops dates missing in either.
        # Use 'outer' merge and then dropna to be explicit about dropping missing pairs
        merged_df = pd.merge(
            sedentary_series.rename('sedentary_time'),
            sleep_score_series.rename('sleep_score'),
            left_index=True,
            right_index=True,
            how='outer' # Use outer to see all dates, then dropna
        ).dropna() # Drop rows where either metric is missing

        if merged_df.empty:
            print("No common dates with both sedentary time and sleep score data found.")
            return

        # Shift the sleep score by 1 day forward (index shift of -1)
        merged_df['sleep_score_shifted'] = merged_df['sleep_score'].shift(-1)

        # Drop the last row which will have a NaN shifted sleep score
        merged_df = merged_df.dropna(subset=['sleep_score_shifted'])

        if merged_df.empty:
            print("No data points remaining after shifting sleep score and dropping missing values.")
            return

        # Filter data where sedentary time is less than the threshold
        filtered_df = merged_df[merged_df['sedentary_time'] > sedentary_threshold_hours]

        if filtered_df.empty:
            print(f"No data found where sedentary time was less than {sedentary_threshold_hours} hours.")
            return

        # Calculate the average sleep score from the filtered data
        average_score = filtered_df['sleep_score_shifted'].mean()

        print(f"Found {len(filtered_df)} matching entries after filtering and shifting.")
        print(f"Average Sleep Score (shifted) when Sedentary Time > {sedentary_threshold_hours} hours: {average_score:.2f}")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.session.rollback() # Rollback in case of error

# --- Main Execution Block ---
if __name__ == "__main__":
    print("Running ad-hoc analysis script.")

    # Example usage:
    calculate_average_sleep_score_when_sedentary_low(sedentary_threshold_hours=8)

    calculate_average_sleep_score_when_sedentary_high(sedentary_threshold_hours=12)

    # Add other analysis functions and call them here as needed
    # e.g., calculate_average_variable_X_when_variable_Y_is_Z(...)

    print("Script finished.")

# The app context is automatically popped when the script finishes
