import pandas as pd
from scipy import stats
from sqlalchemy import func
from .. import db
from ..models.base import HealthData, DataType

class HealthAnalyzer:
    """Utility class for analyzing health data correlations"""
    
    def __init__(self):
        pass
    
    def get_available_metrics(self):
        """Get a list of all available metrics in the database"""
        metrics = db.session.query(
            DataType.metric_name, 
            DataType.source,
            func.count(HealthData.id).label('count')
        ).join(
            HealthData, HealthData.data_type_id == DataType.id
        ).group_by(
            DataType.metric_name, 
            DataType.source
        ).all()
        
        result = []
        for metric_name, source, count in metrics:
            result.append({
                'metric_name': metric_name,
                'source': source,
                'count': count,
                'display_name': f"{metric_name} ({source})"
            })
        
        return result
    
    def get_metric_data(self, metric_name, source, start_date=None, end_date=None):
        """Get data for a specific metric"""
        query = db.session.query(
            HealthData.date,
            HealthData.metric_value,
            DataType.metric_units
        ).join(
            DataType, HealthData.data_type_id == DataType.id
        ).filter(
            DataType.metric_name == metric_name,
            DataType.source == source
        )
        
        if start_date:
            query = query.filter(HealthData.date >= start_date)
        
        if end_date:
            query = query.filter(HealthData.date <= end_date)
        
        query = query.order_by(HealthData.date)
        
        return query.all()
    
    def get_metric_dataframe(self, start_date=None, end_date=None, include_derived=False):
        """Get a dataframe of all metrics by date
        
        Args:
            start_date: Start date for filtering data
            end_date: End date for filtering data
            include_derived: Whether to include derived metrics like nutrient density
            
        Returns:
            DataFrame with dates as index and metrics as columns
        """
        # First, query all data within date range
        query = db.session.query(
            HealthData.date,
            DataType.source,
            DataType.metric_name,
            HealthData.metric_value
        ).join(
            DataType, HealthData.data_type_id == DataType.id
        )
        
        if start_date:
            query = query.filter(HealthData.date >= start_date)
        
        if end_date:
            query = query.filter(HealthData.date <= end_date)
            
        results = query.all()
        
        # Convert to dataframe
        df = pd.DataFrame([(
            r.date,
            r.source,
            r.metric_name,
            r.metric_value
        ) for r in results], columns=['date', 'source', 'metric_name', 'value'])
        
        # Pivot to wide format with dates as index and metrics as columns
        pivot_df = df.pivot_table(
            index='date', 
            columns=['source', 'metric_name'], 
            values='value',
            aggfunc='first'
        )
        
        # Flatten column multi-index
        pivot_df.columns = [f"{source}:{metric}" for source, metric in pivot_df.columns]
        
        # Calculate derived metrics if requested
        if include_derived:
            pivot_df = self._add_nutrient_density_metrics(pivot_df)
        
        return pivot_df
    
    def _add_nutrient_density_metrics(self, df):
        """Add nutrient density metrics (nutrient per calorie) to the dataframe
        
        Args:
            df: DataFrame with metrics as columns
            
        Returns:
            DataFrame with additional derived metrics
        """
        # Find all calorie/energy columns
        energy_cols = [col for col in df.columns if 'energy' in col.lower() or 'calories' in col.lower()]
        
        # If no energy metrics are found, we can't calculate density
        if not energy_cols:
            return df
            
        # For each source that has energy data, create nutrient density metrics
        for energy_col in energy_cols:
            source = energy_col.split(':')[0]  # Extract the source (e.g., 'chronometer')
            
            # Find all columns for this source that aren't energy/calories
            nutrient_cols = [col for col in df.columns 
                           if col.startswith(f"{source}:") 
                           and col != energy_col
                           and 'calories' not in col.lower()
                           and 'energy' not in col.lower()]
            
            # Dictionary to store the new density columns before adding them
            new_density_cols = {}
            
            # For each nutrient, calculate its density metric (per 100 calories)
            for nutrient_col in nutrient_cols:
                nutrient_name = nutrient_col.split(':')[1]  # Extract the metric name
                density_col = f"{source}:density_{nutrient_name}"
                
                # Calculate: nutrient value per 100 calories
                # Use .div for division to handle NaN values better than the / operator
                calculated_density = df[nutrient_col].div(df[energy_col]).multiply(100)
                new_density_cols[density_col] = calculated_density
        
            # If any density columns were calculated, add them all at once
            if new_density_cols:
                density_df = pd.DataFrame(new_density_cols, index=df.index)
                df = pd.concat([df, density_df], axis=1)
        return df
    
    def calculate_correlation(self, metric1_name, metric1_source, metric2_name, metric2_source, 
                             start_date=None, end_date=None, method='pearson', 
                             min_pairs=10, interpolate=False, handle_missing='drop',
                             time_shift=None, use_density=False):
        """Calculate correlation between two metrics
        
        Args:
            metric1_name: Name of first metric
            metric1_source: Source of first metric
            metric2_name: Name of second metric
            metric2_source: Source of second metric
            start_date: Start date for analysis
            end_date: End date for analysis
            method: Correlation method ('pearson', 'spearman', 'kendall')
            min_pairs: Minimum number of data point pairs required
            interpolate: Whether to interpolate missing values
            handle_missing: How to handle missing data 
                            'drop' - only use dates where both metrics have data (default)
                            'interpolate' - use linear interpolation to fill missing values
                            'ffill' - forward fill missing values
            time_shift: Dictionary specifying time shifts for metrics by source
                        e.g., {'oura': -1} shifts oura data back by 1 day
            use_density: Whether to use nutrient density instead of raw values
            
        Returns:
            Dict with correlation results
        """
        # Define a list of Oura sleep metrics that should be time-shifted
        OURA_SLEEP_METRICS = [
            'sleep_score', 'rem_sleep', 'deep_sleep', 'light_sleep', 
            'total_sleep', 'sleep_latency', 'awake_time', 'rem_sleep_score',
            'deep_sleep_score', 'sleep_efficiency', 'avg_hr', 'avg_hrv',
            'avg_resp', 'long_hr', 'long_hrv', 'long_resp', 'long_efficiency',
            'total_sleep_score', 'sleep_latency_score', 'sleep_efficiency_score',
            'sleep_restfulness_score', 'sleep_timing_score'
        ]
        
        # Get data for both metrics, including derived metrics if needed
        df = self.get_metric_dataframe(start_date, end_date, include_derived=use_density)
        
        # If using density metrics and they're available, modify the metric names
        if use_density:
            # Only apply to chronometer or other nutrition sources, not to sleep/activity metrics
            if metric1_source == 'chronometer' and 'energy' not in metric1_name and 'calories' not in metric1_name:
                density_metric1 = f"{metric1_source}:density_{metric1_name}"
                if density_metric1 in df.columns:
                    metric1_name = f"density_{metric1_name}"
            
            if metric2_source == 'chronometer' and 'energy' not in metric2_name and 'calories' not in metric2_name:
                density_metric2 = f"{metric2_source}:density_{metric2_name}"
                if density_metric2 in df.columns:
                    metric2_name = f"density_{metric2_name}"
        
        # Extract the columns for our metrics
        col1 = f"{metric1_source}:{metric1_name}"
        col2 = f"{metric2_source}:{metric2_name}"
        
        if col1 not in df.columns or col2 not in df.columns:
            return {
                'error': 'One or both metrics not found in data'
            }
        
        # Extract the series
        series1 = df[col1].copy()
        series2 = df[col2].copy()
        
        # Apply time shifts if specified, but only to sleep metrics from Oura
        if time_shift is not None:
            # Handle shifting Oura sleep metrics to align with food/nutrition data
            if metric1_source == 'oura' and metric1_source in time_shift:
                # Only shift if it's a sleep metric
                if metric1_name in OURA_SLEEP_METRICS:
                    series1 = series1.shift(time_shift[metric1_source])
            
            if metric2_source == 'oura' and metric2_source in time_shift:
                # Only shift if it's a sleep metric
                if metric2_name in OURA_SLEEP_METRICS:
                    series2 = series2.shift(time_shift[metric2_source])
        
        # Create a new dataframe with the potentially shifted series
        corr_df = pd.DataFrame({
            'metric1': series1,
            'metric2': series2
        })
        
        # Check for missing data in each series
        total_rows = corr_df.shape[0]
        missing_metric1 = corr_df['metric1'].isna().sum()
        missing_metric2 = corr_df['metric2'].isna().sum()
        
        # Count valid pairs (where both values exist)
        valid_df = corr_df.dropna()
        valid_pairs = valid_df.shape[0]
        
        # Handle insufficient data
        if valid_pairs < min_pairs:
            return {
                'error': f'Insufficient data points ({valid_pairs}). Need at least {min_pairs}.',
                'valid_pairs': valid_pairs,
                'min_pairs': min_pairs,
                'total_rows': total_rows,
                'missing_metric1': missing_metric1,
                'missing_metric2': missing_metric2
            }
        
        # Handle missing data according to specified method
        if handle_missing == 'interpolate' and (missing_metric1 > 0 or missing_metric2 > 0):
            corr_df = corr_df.interpolate(method='linear')
        elif handle_missing == 'ffill' and (missing_metric1 > 0 or missing_metric2 > 0):
            corr_df = corr_df.ffill()
        elif handle_missing == 'drop' or (missing_metric1 == 0 and missing_metric2 == 0):
            # Only keep rows where both metrics have data
            corr_df = valid_df
        
        # Calculate correlation
        if method == 'pearson':
            corr, p_value = stats.pearsonr(
                corr_df['metric1'].dropna(), 
                corr_df['metric2'].dropna()
            )
        elif method == 'spearman':
            corr, p_value = stats.spearmanr(
                corr_df['metric1'].dropna(), 
                corr_df['metric2'].dropna()
            )
        elif method == 'kendall':
            corr, p_value = stats.kendalltau(
                corr_df['metric1'].dropna(), 
                corr_df['metric2'].dropna()
            )
        else:
            return {
                'error': f'Unknown correlation method: {method}'
            }
        
        # Prepare result
        result = {
            'metric1': {
                'name': metric1_name,
                'source': metric1_source,
                'display': f"{metric1_name} ({metric1_source})"
            },
            'metric2': {
                'name': metric2_name,
                'source': metric2_source,
                'display': f"{metric2_name} ({metric2_source})"
            },
            'correlation': {
                'coefficient': float(corr),
                'p_value': float(p_value),
                'method': method,
                'interpretation': self._interpret_correlation(corr, p_value),
                'valid_pairs': valid_pairs,
                'data_info': {
                    'total_dates': total_rows,
                    'missing_metric1': missing_metric1,
                    'missing_metric2': missing_metric2,
                    'common_dates': valid_pairs,
                    'handling_method': handle_missing
                },
                'time_shifted': time_shift is not None and (
                    (metric1_source == 'oura' and metric1_source in time_shift and metric1_name in OURA_SLEEP_METRICS) or
                    (metric2_source == 'oura' and metric2_source in time_shift and metric2_name in OURA_SLEEP_METRICS)
                ),
                'nutrient_density': use_density and (
                    metric1_name.startswith('density_') or
                    metric2_name.startswith('density_')
                )
            },
            'data_points': [
                {'date': row[0].strftime('%Y-%m-%d'), 
                 'metric1': None if pd.isna(row[1]) else float(row[1]), 
                 'metric2': None if pd.isna(row[2]) else float(row[2])}
                for row in corr_df.reset_index().values
            ]
        }
        
        return result
    
    def _interpret_correlation(self, corr, p_value):
        """Interpret the correlation coefficient and p-value"""
        strength = ""
        significance = ""
        
        # Interpret correlation strength
        corr_abs = abs(corr)
        if corr_abs < 0.1:
            strength = "negligible"
        elif corr_abs < 0.3:
            strength = "weak"
        elif corr_abs < 0.5:
            strength = "moderate"
        elif corr_abs < 0.7:
            strength = "strong"
        else:
            strength = "very strong"
        
        # Add direction
        if corr > 0:
            direction = "positive"
        else:
            direction = "negative"
        
        # Interpret statistical significance
        if p_value < 0.001:
            significance = "highly significant (p < 0.001)"
        elif p_value < 0.01:
            significance = "significant (p < 0.01)"
        elif p_value < 0.05:
            significance = "significant (p < 0.05)"
        elif p_value < 0.1:
            significance = "marginally significant (p < 0.1)"
        else:
            significance = "not statistically significant"
        
        return f"A {strength} {direction} correlation, {significance}"
    
    def calculate_multiple_correlations(self, target_metric_name, target_metric_source, 
                                       start_date=None, end_date=None, method='pearson',
                                       min_pairs=10, top_n=10, handle_missing='drop',
                                       time_shift=None, use_density=False):
        """Calculate correlations between target metric and all other metrics"""
        # Get all available metrics
        all_metrics = self.get_available_metrics()
        
        results = []
        
        for metric in all_metrics:
            # Skip the target metric itself
            if (metric['metric_name'] == target_metric_name and 
                metric['source'] == target_metric_source):
                continue
            
            # Calculate correlation with this metric
            corr_result = self.calculate_correlation(
                target_metric_name, target_metric_source,
                metric['metric_name'], metric['source'],
                start_date, end_date, method, min_pairs, False, handle_missing,
                time_shift, use_density
            )
            
            # If there was an error, skip this metric
            if 'error' in corr_result:
                continue
            
            # Add this to the results
            results.append({
                'metric': {
                    'name': metric['metric_name'],
                    'source': metric['source'],
                    'display': metric['display_name']
                },
                'correlation': corr_result['correlation']['coefficient'],
                'p_value': corr_result['correlation']['p_value'],
                'valid_pairs': corr_result['correlation']['valid_pairs']
            })
        
        # Sort by absolute correlation value
        results.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        # Return top N results
        return results[:top_n] 