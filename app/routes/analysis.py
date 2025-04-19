from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import traceback
from ..utils.analyzer import HealthAnalyzer
from scipy import stats
import pandas as pd

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/correlation', methods=['GET', 'POST'])
def correlation():
    """Correlation analysis page"""
    analyzer = HealthAnalyzer()
    metrics = analyzer.get_available_metrics()
    
    if request.method == 'POST':
        # Get form data
        metric1_name = request.form.get('metric1_name')
        metric1_source = request.form.get('metric1_source')
        metric2_name = request.form.get('metric2_name')
        metric2_source = request.form.get('metric2_source')
        date_range = request.form.get('date_range', '1year')
        method = request.form.get('method', 'pearson')
        min_pairs = int(request.form.get('min_pairs', 10))
        handle_missing = request.form.get('handle_missing', 'drop')
        time_shift_oura = request.form.get('time_shift_oura', 'no') == 'yes'
        use_density = request.form.get('use_density', 'no') == 'yes'
        interpolate = request.form.get('interpolate', 'no') == 'yes'
        
        # Calculate date range
        end_date = datetime.now().date()
        if date_range == '1month':
            start_date = end_date - relativedelta(months=1)
        elif date_range == '3months':
            start_date = end_date - relativedelta(months=3)
        elif date_range == '6months':
            start_date = end_date - relativedelta(months=6)
        elif date_range == '1year':
            start_date = end_date - relativedelta(years=1)
        elif date_range == '2years':
            start_date = end_date - relativedelta(years=2)
        elif date_range == '5years':
            start_date = end_date - relativedelta(years=5)
        elif date_range == 'all':
            start_date = None
        else:
            # Custom date range
            try:
                start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                start_date = end_date - relativedelta(years=1)
        
        # Calculate correlation
        result = analyzer.calculate_correlation(
            metric1_name, metric1_source,
            metric2_name, metric2_source,
            start_date, end_date, method, min_pairs, interpolate, handle_missing,
            {'oura': -1} if time_shift_oura else None,
            use_density
        )
        
        return render_template('analysis/correlation_result.html', 
                              result=result,
                              metrics=metrics,
                              form_data={
                                  'metric1_name': metric1_name,
                                  'metric1_source': metric1_source,
                                  'metric2_name': metric2_name,
                                  'metric2_source': metric2_source,
                                  'date_range': date_range,
                                  'method': method,
                                  'min_pairs': min_pairs,
                                  'handle_missing': handle_missing,
                                  'interpolate': interpolate,
                                  'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
                                  'end_date': end_date.strftime('%Y-%m-%d') if end_date else None
                              })
    
    # Group metrics by source for the form
    sources = {}
    for metric in metrics:
        if metric['source'] not in sources:
            sources[metric['source']] = []
        sources[metric['source']].append(metric)
    
    return render_template('analysis/correlation.html', sources=sources)

@analysis_bp.route('/dashboard')
def dashboard():
    """Interactive dashboard for analyzing and comparing health metrics"""
    # Get all available metrics for selection
    analyzer = HealthAnalyzer()
    available_metrics = analyzer.get_available_metrics()
    
    # Group metrics by source for easier selection in UI
    metrics_by_source = {}
    for metric in available_metrics:
        source = metric['source']
        if source not in metrics_by_source:
            metrics_by_source[source] = []
        metrics_by_source[source].append(metric)
    
    # Get date range
    date_range = request.args.get('date_range', '30')
    end_date = datetime.now().date()
    
    try:
        days = int(date_range)
    except ValueError:
        days = 30
    
    start_date = end_date - timedelta(days=days)
    
    # Get sample metrics for initial load (one from each source)
    sample_metrics = []
    visited_sources = set()
    
    for metric in available_metrics:
        if metric['source'] not in visited_sources and metric['count'] > 5:
            sample_metrics.append({
                'name': metric['metric_name'],
                'source': metric['source'],
                'color': f'#{hash(metric["metric_name"]) % 0xffffff:06x}'  # Generate a color based on name
            })
            visited_sources.add(metric['source'])
            if len(sample_metrics) >= 3:  # Limit to 3 initial metrics
                break
    
    # Load data for sample metrics
    dashboard_data = {}
    for metric in sample_metrics:
        data = analyzer.get_metric_data(
            metric['name'], metric['source'], start_date, end_date
        )
        
        if data:
            metric_key = f"{metric['source']}:{metric['name']}"
            dashboard_data[metric_key] = {
                'name': metric['name'],
                'source': metric['source'],
                'color': metric['color'],
                'data': [
                    {'date': d[0].strftime('%Y-%m-%d'), 'value': float(d[1])}
                    for d in data
                ],
                'units': data[0][2] if data else ''
            }
    
    return render_template('analysis/dashboard.html',
                          available_metrics=available_metrics,
                          metrics_by_source=metrics_by_source,
                          dashboard_data=dashboard_data,
                          date_range=date_range,
                          start_date=start_date,
                          current_date=end_date)

@analysis_bp.route('/api/metric_data')
def metric_data():
    """API endpoint for getting data for specific metrics"""
    metric_name = request.args.get('metric_name')
    source = request.args.get('source')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not metric_name or not source:
        return jsonify({
            'success': False,
            'message': 'Metric name and source are required',
            'data': []
        })
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid date format. Use YYYY-MM-DD',
            'data': []
        })
    
    analyzer = HealthAnalyzer()
    data = analyzer.get_metric_data(metric_name, source, start_date, end_date)
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data found for the specified metric and date range',
            'data': []
        })
    
    processed_data = [{
        'date': d[0].strftime('%Y-%m-%d'),
        'value': float(d[1]),
        'units': d[2]
    } for d in data]
    
    return jsonify({
        'success': True,
        'message': 'Data retrieved successfully',
        'data': processed_data,
        'units': data[0][2] if data else ''
    })

@analysis_bp.route('/data')
def data():
    """API endpoint for returning health data for visualization."""
    # For testing purposes, return a simple JSON response
    return jsonify({
        'success': True,
        'message': 'Data retrieved successfully.',
        'data': []
    })

@analysis_bp.route('/api/dashboard-correlation', methods=['POST'])
def api_dashboard_correlation():
    """API endpoint to calculate correlation between metrics for the dashboard
    
    Handles two scenarios:
    1. When multiple metrics are selected: calculates correlation between metrics and returns paired data for scatter plot
    2. When one metric is selected: calculates correlation with the date (time trend)
    """
    try:
        data = request.json
        metrics = data.get('metrics', [])
        start_date = end_date = None
        
        # Parse dates if provided
        if 'start_date' in data:
            try:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid start_date format, use YYYY-MM-DD'}), 400
        
        if 'end_date' in data:
            try:
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid end_date format, use YYYY-MM-DD'}), 400
                
        method = data.get('method', 'pearson')
        min_pairs = int(data.get('min_pairs', 5))
        handle_missing = data.get('handle_missing', 'drop')
        
        analyzer = HealthAnalyzer()
        
        # If we have fewer than 2 metrics, we'll calculate correlation with date
        if len(metrics) < 2:
            if len(metrics) == 0:
                return jsonify({'error': 'No metrics provided'}), 400
                
            # For a single metric, calculate correlation with date
            metric = metrics[0]
            metric_data = analyzer.get_metric_data(
                metric['name'], metric['source'], start_date, end_date
            )
            
            if not metric_data or len(metric_data) < min_pairs:
                return jsonify({
                    'error': f'Insufficient data points ({len(metric_data) if metric_data else 0}). Need at least {min_pairs}.'
                }), 400
                
            # Convert to numeric data for correlation
            dates = [(d[0] - metric_data[0][0]).days for d in metric_data]  # Convert to days since first date
            values = [float(d[1]) for d in metric_data]
            
            # Calculate correlation with date
            if method == 'pearson':
                corr, p_value = stats.pearsonr(dates, values)
            elif method == 'spearman':
                corr, p_value = stats.spearmanr(dates, values)
            elif method == 'kendall':
                corr, p_value = stats.kendalltau(dates, values)
            else:
                return jsonify({'error': f'Unknown correlation method: {method}'}), 400
                
            # Prepare data points for time series chart
            data_points = [
                {'date': d[0].strftime('%Y-%m-%d'), 'value': float(d[1])}
                for d in metric_data
            ]
                
            return jsonify({
                'metric1': {
                    'name': metric['name'],
                    'source': metric['source'],
                    'display': f"{metric['name']} ({metric['source']})"
                },
                'metric2': {
                    'name': 'Date',
                    'source': 'system',
                    'display': 'Date (Time Trend)'
                },
                'correlation': {
                    'coefficient': float(corr),
                    'p_value': float(p_value),
                    'method': method,
                    'interpretation': analyzer._interpret_correlation(corr, p_value),
                    'valid_pairs': len(dates),
                    'data_points': len(dates)
                },
                'data_points': data_points,
                'is_time_trend': True
            })
        else:
            # For multiple metrics, calculate correlation between them
            metric1 = metrics[0]
            metric2 = metrics[1]
            
            # Get data for both metrics
            df = analyzer.get_metric_dataframe(start_date, end_date)
            
            # Extract the columns for our metrics
            col1 = f"{metric1['source']}:{metric1['name']}"
            col2 = f"{metric2['source']}:{metric2['name']}"
            
            if col1 not in df.columns or col2 not in df.columns:
                return jsonify({'error': 'One or both metrics not found in data'}), 400
            
            # Extract the series
            series1 = df[col1].copy()
            series2 = df[col2].copy()
            
            # Create a dataframe with the series
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
                return jsonify({
                    'error': f'Insufficient data points ({valid_pairs}). Need at least {min_pairs}.',
                    'valid_pairs': valid_pairs,
                    'min_pairs': min_pairs,
                    'total_rows': total_rows,
                    'missing_metric1': missing_metric1,
                    'missing_metric2': missing_metric2
                }), 400
            
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
                return jsonify({'error': f'Unknown correlation method: {method}'}), 400
            
            # Prepare paired data points for scatter plot
            paired_data = []
            for idx, row in corr_df.iterrows():
                if not pd.isna(row['metric1']) and not pd.isna(row['metric2']):
                    paired_data.append({
                        'date': idx.strftime('%Y-%m-%d'),
                        'x': float(row['metric1']),
                        'y': float(row['metric2'])
                    })
            
            return jsonify({
                'metric1': {
                    'name': metric1['name'],
                    'source': metric1['source'],
                    'display': f"{metric1['name']} ({metric1['source']})"
                },
                'metric2': {
                    'name': metric2['name'],
                    'source': metric2['source'],
                    'display': f"{metric2['name']} ({metric2['source']})"
                },
                'correlation': {
                    'coefficient': float(corr),
                    'p_value': float(p_value),
                    'method': method,
                    'interpretation': analyzer._interpret_correlation(corr, p_value),
                    'valid_pairs': valid_pairs,
                    'data_info': {
                        'total_dates': total_rows,
                        'missing_metric1': missing_metric1,
                        'missing_metric2': missing_metric2,
                        'common_dates': valid_pairs,
                        'handling_method': handle_missing
                    }
                },
                'paired_data': paired_data,
                'is_time_trend': False
            })
            
    except Exception as e:
        return jsonify({
            'error': f'Error calculating correlation: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500 

@analysis_bp.route('/correlation_table', methods=['GET', 'POST'])
def correlation_table():
    """Correlation table analysis page"""
    analyzer = HealthAnalyzer()
    metrics = analyzer.get_available_metrics()
    
    # Group metrics by source
    sources = {}
    for metric in metrics:
        source = metric['source']
        if source not in sources:
            sources[source] = []
        sources[source].append(metric)
    
    if request.method == 'POST':
        try:
            # Get form data
            x_metrics = request.form.getlist('x_metrics')
            y_metrics = request.form.getlist('y_metrics')
            date_range = request.form.get('date_range', '1year')
            method = request.form.get('method', 'pearson')
            min_pairs = int(request.form.get('min_pairs', 10))
            handle_missing = request.form.get('handle_missing', 'drop')
            pvalue_threshold = float(request.form.get('pvalue_threshold', 0.05))
            time_shift_oura = request.form.get('time_shift_oura', 'no') == 'yes'
            use_density = request.form.get('use_density', 'no') == 'yes'
            
            # Calculate date range
            end_date = datetime.now().date()
            if date_range == '1month':
                start_date = end_date - relativedelta(months=1)
            elif date_range == '3months':
                start_date = end_date - relativedelta(months=3)
            elif date_range == '6months':
                start_date = end_date - relativedelta(months=6)
            elif date_range == '1year':
                start_date = end_date - relativedelta(years=1)
            else:
                start_date = None
            
            # Set up time shift if needed
            time_shift = None
            if time_shift_oura:
                time_shift = {'oura': -1}
            
            # Parse metrics
            x_metric_details = []
            for metric_str in x_metrics:
                source, name = metric_str.split(':', 1)
                x_metric_details.append({
                    'source': source,
                    'name': name,
                    'full_name': metric_str
                })
            
            # Define Oura sleep metrics locally for time shifting logic
            OURA_SLEEP_METRICS = [
                'sleep_score', 'rem_sleep', 'deep_sleep', 'light_sleep', 
                'total_sleep', 'sleep_latency', 'awake_time', 'rem_sleep_score',
                'deep_sleep_score', 'sleep_efficiency', 'avg_hr', 'avg_hrv',
                'avg_resp', 'long_hr', 'long_hrv', 'long_resp', 'long_efficiency',
                'total_sleep_score', 'sleep_latency_score', 'sleep_efficiency_score',
                'sleep_restfulness_score', 'sleep_timing_score'
            ]

            # --- Optimization Start ---
            # 1. Fetch all potentially relevant data once
            df = analyzer.get_metric_dataframe(start_date, end_date, include_derived=use_density)

            # 2. Prepare metric details and determine actual column names
            x_metric_details = []
            for metric_str in x_metrics:
                source, name = metric_str.split(':', 1)
                col_name = f"{source}:{name}"
                # Adjust name if using density and it exists
                if use_density and source == 'chronometer' and 'energy' not in name and 'calories' not in name:
                    density_col = f"{source}:density_{name}"
                    if density_col in df.columns:
                        col_name = density_col
                        name = f"density_{name}" # Update name for consistency if needed later
                
                x_metric_details.append({
                    'source': source,
                    'name': name,
                    'full_name': metric_str, # Original identifier from form
                    'col_name': col_name      # Actual column name in DataFrame
                })

            y_metric_details = []
            for metric_str in y_metrics:
                source, name = metric_str.split(':', 1)
                col_name = f"{source}:{name}"
                if use_density and source == 'chronometer' and 'energy' not in name and 'calories' not in name:
                    density_col = f"{source}:density_{name}"
                    if density_col in df.columns:
                        col_name = density_col
                        name = f"density_{name}"
                        
                y_metric_details.append({
                    'source': source,
                    'name': name,
                    'full_name': metric_str,
                    'col_name': col_name
                })

            # 3. Calculate correlations by iterating through pairs
            correlation_matrix = []
            for y_metric in y_metric_details:
                row = {
                    'metric': y_metric, # Use the detailed dict
                    'correlations': []
                }
                
                for x_metric in x_metric_details:
                    corr_result = {} # Initialize result for this pair

                    # Skip self-correlation
                    if y_metric['full_name'] == x_metric['full_name']:
                        corr_result = {
                            'correlation': 1.0,
                            'p_value': 0.0,
                            'significant': True,
                            'self': True,
                            'valid_pairs': df[y_metric['col_name']].count() if y_metric['col_name'] in df.columns else 0
                        }
                    else:
                        x_col = x_metric['col_name']
                        y_col = y_metric['col_name']

                        # Check if columns exist in the DataFrame
                        if x_col not in df.columns or y_col not in df.columns:
                            corr_result = {
                                'error': f"Metric data not found ({x_col if x_col not in df.columns else y_col})",
                                'valid_pairs': 0,
                                'significant': False
                            }
                        else:
                            # Extract series
                            series_x = df[x_col].copy()
                            series_y = df[y_col].copy()

                            # Apply time shift if needed
                            shifted = False
                            if time_shift_oura:
                                if x_metric['source'] == 'oura' and x_metric['name'] in OURA_SLEEP_METRICS:
                                    series_x = series_x.shift(-1)
                                    shifted = True
                                if y_metric['source'] == 'oura' and y_metric['name'] in OURA_SLEEP_METRICS:
                                    series_y = series_y.shift(-1)
                                    shifted = True
                            
                            # Combine into a temporary DataFrame for pairwise analysis
                            pair_df = pd.DataFrame({'x': series_x, 'y': series_y})

                            # Count valid pairs *before* interpolation/ffill
                            valid_pair_df = pair_df.dropna()
                            valid_pairs = len(valid_pair_df)

                            if valid_pairs < min_pairs:
                                corr_result = {
                                    'error': f'Insufficient pairs ({valid_pairs} < {min_pairs})',
                                    'valid_pairs': valid_pairs,
                                    'significant': False
                                }
                            else:
                                # Select data based on handle_missing strategy for calculation
                                calc_df = None
                                if handle_missing == 'drop':
                                    calc_df = valid_pair_df
                                elif handle_missing == 'interpolate':
                                    # Interpolate original pair_df then drop NaNs that might remain at ends
                                    calc_df = pair_df.interpolate(method='linear').dropna()
                                elif handle_missing == 'ffill':
                                    # Forward fill original pair_df then drop NaNs
                                    calc_df = pair_df.ffill().dropna()
                                else: # Default to drop
                                    calc_df = valid_pair_df

                                # Recalculate valid pairs if interpolation/ffill changed the count
                                final_calc_pairs = len(calc_df)
                                if final_calc_pairs < min_pairs:
                                     corr_result = {
                                        'error': f'Insufficient pairs after {handle_missing} ({final_calc_pairs} < {min_pairs})',
                                        'valid_pairs': final_calc_pairs,
                                        'significant': False
                                    }
                                else:
                                    # Calculate correlation
                                    try:
                                        if method == 'pearson':
                                            corr, p_value = stats.pearsonr(calc_df['x'], calc_df['y'])
                                        elif method == 'spearman':
                                            corr, p_value = stats.spearmanr(calc_df['x'], calc_df['y'])
                                        elif method == 'kendall':
                                            corr, p_value = stats.kendalltau(calc_df['x'], calc_df['y'])
                                        else:
                                            raise ValueError(f"Unknown correlation method: {method}")
                                        
                                        # Check for NaN results (can happen with constant data)
                                        if pd.isna(corr) or pd.isna(p_value):
                                             corr_result = {
                                                'error': 'Calculation resulted in NaN (constant data?)',
                                                'valid_pairs': final_calc_pairs,
                                                'significant': False
                                            }
                                        else:
                                            corr_result = {
                                                'correlation': float(corr),
                                                'p_value': float(p_value),
                                                'significant': float(p_value) < pvalue_threshold,
                                                'valid_pairs': final_calc_pairs,
                                                'shifted': shifted,
                                                'interpretation': analyzer._interpret_correlation(corr, p_value) # Use existing interpretation method
                                            }
                                    except Exception as calc_e:
                                        corr_result = {
                                            'error': f'Calculation error: {str(calc_e)}',
                                            'valid_pairs': final_calc_pairs,
                                            'significant': False
                                        }
                    
                    row['correlations'].append(corr_result)
                
                correlation_matrix.append(row)
            # --- Optimization End ---

            # Get available metrics for display (using original metric list)
            all_metrics = {f"{metric['source']}:{metric['metric_name']}": metric['display_name'] for metric in metrics}
            
            return render_template('analysis/correlation_table.html', 
                                  sources=sources, 
                                  metrics=metrics,
                                  correlation_matrix=correlation_matrix,
                                  x_metrics=x_metrics,
                                  y_metrics=y_metrics,
                                  all_metrics=all_metrics,
                                  date_range=date_range,
                                  method=method,
                                  min_pairs=min_pairs,
                                  handle_missing=handle_missing,
                                  pvalue_threshold=pvalue_threshold,
                                  time_shift_oura=time_shift_oura,
                                  use_density=use_density)
        
        except Exception as e:
            error_message = f"Error: {str(e)}"
            traceback.print_exc()
            return render_template('analysis/correlation_table.html', 
                                  sources=sources, 
                                  metrics=metrics,
                                  error_message=error_message)
    
    return render_template('analysis/correlation_table.html', 
                          sources=sources, 
                          metrics=metrics)
