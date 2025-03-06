from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from werkzeug.utils import secure_filename
import os
from datetime import datetime, date
import traceback
import requests
from sqlalchemy import func

from .. import db
from ..models.base import HealthData, UserDefinedMetric, DataSource, ImportRecord
from ..utils.oura_importer import OuraImporter
from ..utils.chronometer_importer import ChronometerImporter

data_bp = Blueprint('data', __name__)

@data_bp.route('/', strict_slashes=False)
def index():
    """Data management home page"""
    # Get all data sources
    data_sources = DataSource.query.order_by(DataSource.name).all()
    
    # Get all user-defined metrics
    custom_metrics = UserDefinedMetric.query.order_by(UserDefinedMetric.name).all()
    
    # Get some stats
    data_count = HealthData.query.count()
    metric_count = db.session.query(HealthData.metric_name, HealthData.source).distinct().count()
    
    # Get the date range of data
    latest_date = db.session.query(db.func.max(HealthData.date)).scalar()
    earliest_date = db.session.query(db.func.min(HealthData.date)).scalar()
    
    return render_template('data/index.html', 
                          data_sources=data_sources,
                          custom_metrics=custom_metrics,
                          data_count=data_count,
                          metric_count=metric_count,
                          latest_date=latest_date,
                          earliest_date=earliest_date)

@data_bp.route('/import', methods=['GET', 'POST'])
def import_data():
    """Import health data"""
    if request.method == 'POST':
        data_source = request.form.get('data_source')
        
        if data_source == 'oura_api':
            return _import_oura_api()
        elif data_source == 'oura_csv':
            return _import_oura_csv()
        elif data_source == 'chronometer_csv':
            return _import_chronometer_csv()
        elif data_source == 'custom':
            return _import_custom_data()
        else:
            flash('Unknown data source', 'error')
    
    # Query to get the last import date for Oura
    oura_last_import = db.session.query(DataSource.last_import).filter(
        DataSource.name.in_(['oura_sleep', 'oura_activity', 'oura_api'])
    ).order_by(DataSource.last_import.desc()).first()
    
    # Get list of recent imports
    recent_imports = ImportRecord.query.order_by(ImportRecord.date_imported.desc()).limit(10).all()
    
    # Check if Oura is connected through the session
    oura_connected = session.get('oura_connected', False)
    
    # Format last import date for Oura
    oura_last_import_date = None
    if oura_last_import and oura_last_import[0]:
        oura_last_import_date = oura_last_import[0].strftime("%Y-%m-%d")
    
    # Today's date for default end date
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Get custom metrics for the form
    custom_metrics = UserDefinedMetric.query.all()
    
    return render_template('data/import.html', 
                           oura_connected=oura_connected,
                           oura_last_import_date=oura_last_import_date,
                           today_date=today_date,
                           custom_metrics=custom_metrics,
                           recent_imports=recent_imports)

def _import_oura_api():
    """Import data from Oura API"""
    try:
        access_token = request.form.get('access_token')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Start date and end date are required', 'error')
            return redirect(url_for('data.import_data'))
        
        importer = OuraImporter(access_token=access_token if access_token else None)
        data = importer.import_sleep_data(start_date, end_date)
        
        flash(f'Successfully imported {len(data)} Oura sleep data points', 'success')
    except Exception as e:
        current_app.logger.error(f"Error importing Oura API data: {e}")
        flash(f'Error importing data: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

def _import_oura_csv():
    """Import data from Oura CSV file"""
    try:
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('data.import_data'))
            
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('data.import_data'))
            
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            importer = OuraImporter()
            data = importer.import_from_csv(file_path)
            
            # Clean up the temp file
            os.remove(file_path)
            
            flash(f'Successfully imported {len(data)} Oura data points from CSV', 'success')
    except Exception as e:
        current_app.logger.error(f"Error importing Oura CSV data: {e}")
        flash(f'Error importing data: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

def _import_chronometer_csv():
    """Import data from Chronometer CSV file"""
    try:
        if 'chronometer_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('data.import_data'))
            
        file = request.files['chronometer_file']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('data.import_data'))
            
        if file and file.filename.endswith('.csv'):
            # Create upload folder if it doesn't exist
            upload_folder = os.path.join(current_app.instance_path, 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Import the data
            importer = ChronometerImporter()
            data = importer.import_from_csv(file_path)
            
            # Process food categories if requested
            if request.form.get('process_categories') == 'yes':
                import pandas as pd
                df = pd.read_csv(file_path)
                importer.process_food_categories(df)
            
            # Clean up the temp file
            os.remove(file_path)
            
            imported_count = len(data)
            flash(f'Successfully imported {imported_count} Chronometer nutrition data points', 'success')
        else:
            flash('Invalid file format. Please upload a CSV file.', 'error')
            return redirect(url_for('data.import_data'))
    except Exception as e:
        current_app.logger.error(f"Error importing Chronometer CSV data: {e}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error importing data: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

def _import_custom_data():
    """Import custom data"""
    try:
        date_str = request.form.get('date')
        metric_name = request.form.get('metric_name')
        metric_value = request.form.get('metric_value')
        metric_units = request.form.get('metric_units')
        notes = request.form.get('notes', '')
        
        if not date_str or not metric_name or metric_value is None:
            flash('Date, metric name, and value are required', 'error')
            return redirect(url_for('data.import_data'))
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            metric_value = float(metric_value)
        except ValueError:
            flash('Invalid date or value format', 'error')
            return redirect(url_for('data.import_data'))
        
        # Check if this metric exists as a user-defined metric
        udm = UserDefinedMetric.query.filter_by(name=metric_name).first()
        if not udm:
            # Create a new user-defined metric
            udm = UserDefinedMetric(
                name=metric_name,
                units=metric_units,
                description=f"Custom metric added on {datetime.now().strftime('%Y-%m-%d')}",
                frequency='custom'
            )
            db.session.add(udm)
        
        # Check if a data point already exists for this date/metric
        existing = HealthData.query.filter_by(
            date=date_obj,
            source='custom',
            metric_name=metric_name
        ).first()
        
        if existing:
            # Update existing data point
            existing.metric_value = metric_value
            existing.metric_units = metric_units
            existing.notes = notes
            flash(f'Updated existing data point for {metric_name} on {date_str}', 'success')
        else:
            # Create new data point
            data_point = HealthData(
                date=date_obj,
                source='custom',
                metric_name=metric_name,
                metric_value=metric_value,
                metric_units=metric_units,
                notes=notes
            )
            db.session.add(data_point)
            flash(f'Added new data point for {metric_name} on {date_str}', 'success')
        
        # Make sure custom data source exists
        custom_source = DataSource.query.filter_by(name='custom').first()
        if not custom_source:
            custom_source = DataSource(
                name='custom',
                type='manual',
                last_import=datetime.utcnow()
            )
            db.session.add(custom_source)
        else:
            custom_source.last_import = datetime.utcnow()
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding custom data: {e}")
        flash(f'Error adding data: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

@data_bp.route('/custom-metrics', methods=['GET', 'POST'])
def custom_metrics():
    """Manage custom metrics"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            name = request.form.get('name')
            units = request.form.get('units')
            description = request.form.get('description')
            frequency = request.form.get('frequency')
            
            if not name:
                flash('Metric name is required', 'error')
                return redirect(url_for('data.custom_metrics'))
            
            # Check if metric already exists
            existing = UserDefinedMetric.query.filter_by(name=name).first()
            if existing:
                flash(f'A metric with name "{name}" already exists', 'error')
                return redirect(url_for('data.custom_metrics'))
            
            # Create new metric
            metric = UserDefinedMetric(
                name=name,
                units=units,
                description=description,
                frequency=frequency
            )
            db.session.add(metric)
            db.session.commit()
            
            flash(f'Created new custom metric: {name}', 'success')
            return redirect(url_for('data.custom_metrics'))
        
        elif action == 'delete':
            metric_id = request.form.get('metric_id')
            
            if not metric_id:
                flash('Metric ID is required', 'error')
                return redirect(url_for('data.custom_metrics'))
            
            # Delete the metric
            metric = UserDefinedMetric.query.get(metric_id)
            if metric:
                # Also delete all data points for this metric
                HealthData.query.filter_by(
                    source='custom',
                    metric_name=metric.name
                ).delete()
                
                db.session.delete(metric)
                db.session.commit()
                
                flash(f'Deleted custom metric: {metric.name}', 'success')
            else:
                flash('Metric not found', 'error')
            
            return redirect(url_for('data.custom_metrics'))
    
    # Get all custom metrics
    metrics = UserDefinedMetric.query.order_by(UserDefinedMetric.name).all()
    
    return render_template('data/custom_metrics.html', metrics=metrics)

@data_bp.route('/browse', methods=['GET', 'POST'])
def browse():
    """Browse all data with filtering and bulk deletion"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    source = request.args.get('source', None)
    metric = request.args.get('metric', None)
    max_calories = request.args.get('max_calories', None, type=float)
    date_filter = request.args.get('date', None)
    
    # Handle bulk deletion
    if request.method == 'POST' and 'delete_selected' in request.form:
        selected_ids = request.form.getlist('selected_data')
        if selected_ids:
            try:
                # Convert string IDs to integers
                ids_to_delete = [int(id) for id in selected_ids]
                
                # Delete the selected records
                deleted_count = HealthData.query.filter(HealthData.id.in_(ids_to_delete)).delete(synchronize_session=False)
                db.session.commit()
                
                flash(f'Successfully deleted {deleted_count} data points.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting data: {str(e)}', 'error')
        else:
            flash('No data points selected for deletion.', 'warning')
        
        # Redirect to refresh the page
        return redirect(url_for('data.browse', page=page, per_page=per_page, source=source, 
                               metric=metric, max_calories=max_calories, date=date_filter))
    
    # Build query
    query = HealthData.query
    
    if source:
        query = query.filter(HealthData.source == source)
    
    if metric:
        query = query.filter(HealthData.metric_name == metric)
    
    # Add date filtering
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(HealthData.date == filter_date)
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD format.', 'error')
    
    # Add calories filtering
    if max_calories is not None:
        # First, get all dates where there's an "Energy (kcal)" entry below the threshold
        energy_subquery = db.session.query(HealthData.date)\
            .filter(HealthData.metric_name == 'Energy (kcal)')\
            .filter(HealthData.metric_value <= max_calories)\
            .distinct()
        
        # Then filter the main query to only include data from those dates
        query = query.filter(HealthData.date.in_(energy_subquery))
    
    # Get paginated results
    data = query.order_by(HealthData.date.desc(), HealthData.source, HealthData.metric_name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get sources and metrics for filtering
    sources = db.session.query(HealthData.source).distinct().all()
    metrics = db.session.query(HealthData.metric_name).distinct().all()
    
    # Get min, max values for energy to set slider bounds
    energy_stats = db.session.query(
        func.min(HealthData.metric_value).label('min_value'),
        func.max(HealthData.metric_value).label('max_value')
    ).filter(HealthData.metric_name == 'Energy (kcal)').first()
    
    min_calories = int(energy_stats.min_value) if energy_stats.min_value is not None else 0
    max_calories_bound = int(energy_stats.max_value) if energy_stats.max_value is not None else 4000
    
    return render_template('data/browse.html', 
                          data=data,
                          sources=[s[0] for s in sources],
                          metrics=[m[0] for m in metrics],
                          current_source=source,
                          current_metric=metric,
                          current_max_calories=max_calories,
                          min_calories=min_calories,
                          max_calories_bound=max_calories_bound,
                          current_date=date_filter)

@data_bp.route('/delete-data', methods=['POST'])
def delete_data():
    """Delete a health data point"""
    data_id = request.form.get('data_id')
    redirect_url = request.form.get('redirect_url', url_for('data.browse'))
    
    if data_id:
        try:
            # Find the data point
            data_point = HealthData.query.get_or_404(data_id)
            
            # Delete it
            db.session.delete(data_point)
            db.session.commit()
            
            flash('Data point deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting data: {str(e)}', 'error')
    
    return redirect(redirect_url)

@data_bp.route('/api/metrics')
def api_metrics():
    """API to get available metrics"""
    source = request.args.get('source')
    
    query = db.session.query(HealthData.metric_name).distinct()
    
    if source:
        query = query.filter(HealthData.source == source)
    
    metrics = [m[0] for m in query.all()]
    
    return jsonify(metrics)

@data_bp.route('/connect/oura')
def connect_oura():
    """Connect to Oura Ring using personal token"""
    # This is now a placeholder for a form to enter a personal token
    return render_template('data/connect_oura.html')

@data_bp.route('/connect/oura', methods=['POST'])
def submit_oura_token():
    """Save the submitted Oura personal token"""
    personal_token = request.form.get('personal_token')

    if not personal_token:
        flash('Please provide a personal access token', 'error')
        return redirect(url_for('data.connect_oura'))

    # In a real application, store this securely in a database
    # Here we just store it in the session for simplicity
    session['oura_personal_token'] = personal_token
    session['oura_connected'] = True

    flash('Successfully saved Oura personal token!', 'success')
    return redirect(url_for('data.import_data'))

@data_bp.route('/import/oura', methods=['POST'])
def import_oura():
    """Import data from Oura API using personal token"""
    if not session.get('oura_connected'):
        flash('You need to connect your Oura Ring first', 'error')
        return redirect(url_for('data.import_data'))
    
    try:
        personal_token = session.get('oura_personal_token')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        data_type = request.form.get('data_type', 'sleep')  # Default to sleep data
        
        if not start_date or not end_date:
            flash('Start date and end date are required', 'error')
            return redirect(url_for('data.import_data'))
        
        importer = OuraImporter(personal_token=personal_token)
        
        imported_data = []
        if data_type == 'sleep' or data_type == 'all':
            sleep_data = importer.import_sleep_data(start_date, end_date)
            imported_data.extend(sleep_data)
            flash(f'Successfully imported {len(sleep_data)} Oura sleep data points', 'success')
        
        if data_type == 'activity' or data_type == 'all':
            activity_data = importer.import_activity_data(start_date, end_date)
            imported_data.extend(activity_data)
            flash(f'Successfully imported {len(activity_data)} Oura activity data points', 'success')
        
        if data_type == 'tags' or data_type == 'all':
            tags_data = importer.import_tags_data(start_date, end_date)
            imported_data.extend(tags_data)
            flash(f'Successfully imported {len(tags_data)} Oura tag data points', 'success')
        
        # Create import record
        import_record = ImportRecord(
            source=f'oura_{data_type}',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date(),
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date(),
            record_count=len(imported_data),
            status='success'
        )
        db.session.add(import_record)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error importing Oura API data: {e}")
        flash(f'Error importing data: {str(e)}', 'error')
        
        # Create failed import record
        import_record = ImportRecord(
            source=f'oura_{data_type}',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None,
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None,
            record_count=0,
            status='failed',
            error_message=str(e)
        )
        db.session.add(import_record)
        db.session.commit()
    
    return redirect(url_for('data.index'))

@data_bp.route('/date/<date_str>', methods=['GET'])
@data_bp.route('/date', methods=['GET', 'POST'])
def date_view(date_str=None):
    """View all health data for a specific date"""
    if request.method == 'POST':
        # If form was submitted, redirect to the date URL
        date_input = request.form.get('date')
        if date_input:
            return redirect(url_for('data.date_view', date_str=date_input))
    
    # Get the date from the URL or use today's date
    selected_date = None
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD format.', 'error')
            selected_date = date.today()
    else:
        selected_date = date.today()
    
    # Format for display
    formatted_date = selected_date.strftime('%B %d, %Y')  # e.g., "January 01, 2023"
    today_str = date.today().strftime('%Y-%m-%d')  # For the "Today" button
    
    # Query all health data for the selected date
    health_data = HealthData.query.filter_by(date=selected_date).order_by(
        HealthData.source, HealthData.metric_name
    ).all()
    
    # Group data by source for easier display
    data_by_source = {}
    for item in health_data:
        if item.source not in data_by_source:
            data_by_source[item.source] = []
        data_by_source[item.source].append(item)
    
    # Get the next and previous dates that have data
    next_date = HealthData.query.filter(
        HealthData.date > selected_date
    ).order_by(HealthData.date.asc()).first()
    
    prev_date = HealthData.query.filter(
        HealthData.date < selected_date
    ).order_by(HealthData.date.desc()).first()
    
    # Check if there's any data for the selected date
    has_data = len(health_data) > 0
    
    return render_template(
        'data/date_view.html',
        selected_date=selected_date,
        formatted_date=formatted_date,
        data_by_source=data_by_source,
        has_data=has_data,
        next_date=next_date.date if next_date else None,
        prev_date=prev_date.date if prev_date else None,
        today_str=today_str
    ) 