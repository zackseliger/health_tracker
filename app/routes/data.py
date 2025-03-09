from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from werkzeug.utils import secure_filename
import os
from datetime import datetime, date, timedelta
import traceback
from sqlalchemy import func

from .. import db
from ..models.base import HealthData, UserDefinedMetric, ImportRecord, DataType
from ..utils.oura_importer import OuraImporter
from ..utils.chronometer_importer import ChronometerImporter

data_bp = Blueprint('data', __name__)

@data_bp.route('/', strict_slashes=False)
def index():
    """Data home page"""
    # Get all data sources (unique sources from DataType)
    data_sources = db.session.query(DataType.source, db.func.max(DataType.last_import).label('last_import')) \
                       .group_by(DataType.source) \
                       .order_by(DataType.source) \
                       .all()
    
    # Get all user-defined metrics
    custom_metrics = UserDefinedMetric.query.order_by(UserDefinedMetric.name).all()
    
    # Get some stats
    data_count = HealthData.query.count()
    metric_count = db.session.query(DataType.metric_name, DataType.source).distinct().count()
    
    # Get the date range of data
    latest_date = db.session.query(db.func.max(HealthData.date)).scalar()
    earliest_date = db.session.query(db.func.min(HealthData.date)).scalar()
    
    # Query to get the last import date for Oura
    oura_last_import = db.session.query(db.func.max(DataType.last_import)).filter(
        DataType.source.in_(['oura_sleep', 'oura_activity', 'oura_api', 'oura'])
    ).scalar()
    
    # Get list of recent imports
    recent_imports = ImportRecord.query.order_by(ImportRecord.date_imported.desc()).limit(10).all()
    
    # Check if Oura is connected through the session
    oura_connected = session.get('oura_connected', False)
    
    # Format last import date for Oura
    oura_last_import_date = None
    if oura_last_import:
        if isinstance(oura_last_import, datetime):
            oura_last_import_date = oura_last_import.strftime("%Y-%m-%d")
        else:
            oura_last_import_date = datetime.fromtimestamp(oura_last_import).strftime("%Y-%m-%d")
    
    # Today's date for default end date
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Get custom metrics for the form
    custom_metrics = UserDefinedMetric.query.all()
    
    return render_template('data/index.html', 
                          data_sources=data_sources,
                          custom_metrics=custom_metrics,
                          data_count=data_count,
                          metric_count=metric_count,
                          latest_date=latest_date,
                          earliest_date=earliest_date,
                          oura_connected=oura_connected,
                          oura_last_import_date=oura_last_import_date,
                          today_date=today_date,
                          recent_imports=recent_imports)

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
    oura_last_import = db.session.query(DataType.last_import).filter(
        DataType.source.in_(['oura_sleep', 'oura_activity', 'oura_api'])
    ).order_by(DataType.last_import.desc()).first()
    
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
        
        # Log import parameters
        current_app.logger.info(f"Oura API import initiated: date range {start_date} to {end_date}")
        
        importer = OuraImporter(access_token=access_token if access_token else None)
        
        # Import sleep data
        try:
            current_app.logger.info(f"Starting sleep data import: {start_date} to {end_date}")
            sleep_data = importer.import_sleep_data(start_date, end_date)
            current_app.logger.info(f"Sleep data import completed: {len(sleep_data)} records")
            flash(f'Successfully imported {len(sleep_data)} Oura sleep data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error importing sleep data: {str(e)}")
            flash(f'Error importing sleep data: {str(e)}', 'error')
            sleep_data = []
        
        # Import activity data
        try:
            current_app.logger.info(f"Starting activity data import: {start_date} to {end_date}")
            activity_data = importer.import_activity_data(start_date, end_date)
            current_app.logger.info(f"Activity data import completed: {len(activity_data)} records")
            flash(f'Successfully imported {len(activity_data)} Oura activity data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error importing activity data: {str(e)}")
            flash(f'Error importing activity data: {str(e)}', 'error')
            activity_data = []
        
        # Import tags data
        try:
            current_app.logger.info(f"Starting tag data import: {start_date} to {end_date}")
            tags_data = importer.import_tags_data(start_date, end_date)
            current_app.logger.info(f"Tag data import completed: {len(tags_data)} records")
            flash(f'Successfully imported {len(tags_data)} Oura tag data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error importing tag data: {str(e)}")
            flash(f'Note: Tag data import failed, but sleep and activity data were imported: {str(e)}', 'warning')
            tags_data = []
        
        # Create import record
        import_record = ImportRecord(
            source='oura',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date(),
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date(),
            record_count=len(sleep_data) + len(activity_data) + len(tags_data),
            status='success'
        )
        db.session.add(import_record)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error importing Oura API data: {e}")
        flash(f'Error importing data: {str(e)}', 'error')
    
    return redirect(url_for('data.import_data'))

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
        
        # Get or create the DataType
        data_type = DataType.query.filter_by(
            source='custom',
            metric_name=metric_name
        ).first()
        
        if not data_type:
            data_type = DataType(
                source='custom',
                metric_name=metric_name,
                metric_units=metric_units
            )
            db.session.add(data_type)
            db.session.flush()  # Flush to get the ID
        
        # Check if a data point already exists for this date/metric
        existing = HealthData.query.join(
            DataType, HealthData.data_type_id == DataType.id
        ).filter(
            HealthData.date == date_obj,
            DataType.source == 'custom',
            DataType.metric_name == metric_name
        ).first()
        
        if existing:
            # Update existing data point
            existing.metric_value = metric_value
            existing.notes = notes
            flash(f'Updated existing data point for {metric_name} on {date_str}', 'success')
        else:
            # Create new data point
            data_point = HealthData(
                date=date_obj,
                data_type=data_type,
                metric_value=metric_value,
                notes=notes
            )
            db.session.add(data_point)
            flash(f'Added new data point for {metric_name} on {date_str}', 'success')
        
        # Make sure custom data source exists
        DataType.update_last_import('custom')
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding custom data: {e}")
        flash(f'Error adding data: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

@data_bp.route('/custom-metrics', methods=['GET', 'POST'])
def custom_metrics():
    """Manage user-defined custom metrics"""
    if request.method == 'POST':
        # Handle deletion
        if 'delete' in request.form:
            metric_id = request.form.get('metric_id')
            metric = UserDefinedMetric.query.get(metric_id)
            
            if metric:
                db.session.delete(metric)
                db.session.commit()
                
                flash(f'Deleted custom metric: {metric.name}', 'success')
            else:
                flash('Metric not found', 'error')
            
            return redirect(url_for('data.custom_metrics'))
    
    # Get all custom metrics
    metrics = UserDefinedMetric.query.order_by(UserDefinedMetric.name).all()
    
    return render_template('data/custom_metrics.html', metrics=metrics)

@data_bp.route('/custom-metrics/add', methods=['GET', 'POST'])
def add_custom_metric():
    """Add a new custom metric"""
    if request.method == 'POST':
        name = request.form.get('name')
        unit = request.form.get('unit')
        description = request.form.get('description')
        data_type = request.form.get('data_type', 'numeric')
        is_cumulative = 'is_cumulative' in request.form
        
        # Create new metric
        metric = UserDefinedMetric(
            name=name,
            unit=unit,
            description=description,
            data_type=data_type,
            is_cumulative=is_cumulative
        )
        
        db.session.add(metric)
        db.session.commit()
        
        # Create a DataType entry for this custom metric
        data_type_entry = DataType(
            source='custom',
            metric_name=name,
            metric_units=unit
        )
        db.session.add(data_type_entry)
        db.session.commit()
        
        flash(f'Added new custom metric: {name}', 'success')
        return redirect(url_for('data.custom_metrics'))
    
    # GET request - show the form
    return render_template('data/add_custom_metric.html')

@data_bp.route('/custom-metrics/view/<int:metric_id>', methods=['GET'])
def view_custom_metric(metric_id):
    """View details for a specific custom metric"""
    metric = UserDefinedMetric.query.get_or_404(metric_id)
    
    # Get data points for this metric
    data_points = HealthData.query.join(DataType).filter(
        DataType.source == 'custom',
        DataType.metric_name == metric.name
    ).order_by(HealthData.date.desc()).all()
    
    return render_template('data/view_custom_metric.html', metric=metric, data_points=data_points)

@data_bp.route('/custom-metrics/manual-entry/<int:metric_id>', methods=['GET', 'POST'])
def manual_entry(metric_id):
    """Manual data entry for a custom metric"""
    metric = UserDefinedMetric.query.get_or_404(metric_id)
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        value = request.form.get('value')
        notes = request.form.get('notes', '')
        
        try:
            # Parse date
            entry_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Parse value based on data type
            if metric.data_type == 'numeric':
                metric_value = float(value)
            elif metric.data_type == 'boolean':
                metric_value = 1 if value.lower() in ['true', 'yes', '1'] else 0
            elif metric.data_type == 'scale':
                metric_value = int(value)
            else:
                metric_value = float(value)
            
            # Get the data type
            data_type = DataType.query.filter_by(
                source='custom',
                metric_name=metric.name
            ).first()
            
            if not data_type:
                # Create data type if it doesn't exist
                data_type = DataType(
                    source='custom',
                    metric_name=metric.name,
                    metric_units=metric.unit
                )
                db.session.add(data_type)
                db.session.commit()
            
            # Check if an entry already exists for this date
            existing = HealthData.query.filter_by(
                date=entry_date,
                data_type_id=data_type.id
            ).first()
            
            if existing:
                # Update existing entry
                existing.metric_value = metric_value
                existing.notes = notes
                flash(f'Updated data for {metric.name} on {date_str}', 'success')
            else:
                # Create new entry
                new_entry = HealthData(
                    date=entry_date,
                    data_type_id=data_type.id,
                    metric_value=metric_value,
                    notes=notes
                )
                db.session.add(new_entry)
                flash(f'Added new data for {metric.name} on {date_str}', 'success')
            
            db.session.commit()
            return redirect(url_for('data.view_custom_metric', metric_id=metric.id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'danger')
            return render_template('data/manual_entry.html', metric=metric)
    
    # GET request - show the form
    return render_template('data/manual_entry.html', metric=metric)

@data_bp.route('/custom-metrics/delete', methods=['POST'])
def delete_custom_metric():
    """Delete a custom metric and all its data points"""
    metric_id = request.form.get('metric_id')
    if not metric_id:
        flash('No metric specified', 'danger')
        return redirect(url_for('data.custom_metrics'))
    
    metric = UserDefinedMetric.query.get_or_404(metric_id)
    
    # Delete all data points for this metric
    data_type = DataType.query.filter_by(source='custom', metric_name=metric.name).first()
    if data_type:
        HealthData.query.filter_by(data_type_id=data_type.id).delete()
        db.session.delete(data_type)
    
    # Delete the metric definition
    db.session.delete(metric)
    db.session.commit()
    
    flash(f'Custom metric "{metric.name}" has been deleted', 'success')
    return redirect(url_for('data.custom_metrics'))

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
    query = HealthData.query.join(DataType)
    
    if source:
        # Filter by source in DataType
        query = query.filter(DataType.source == source)
    
    if metric:
        query = query.filter(DataType.metric_name == metric)
    
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
            .join(DataType)\
            .filter(DataType.metric_name == 'Energy (kcal)')\
            .filter(HealthData.metric_value <= max_calories)\
            .distinct()
        
        # Then filter the main query to only include data from those dates
        query = query.filter(HealthData.date.in_(energy_subquery))
    
    # Get paginated results
    data = query.order_by(HealthData.date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Prepare data for the template
    for item in data.items:
        item.source = item.data_type.source
        item.metric_name = item.data_type.metric_name
        item.metric_units = item.data_type.metric_units
    
    # Get sources and metrics for filtering
    sources = db.session.query(DataType.source).distinct().all()
    metrics = db.session.query(DataType.metric_name).distinct().all()
    
    # Get min, max values for energy to set slider bounds
    energy_stats = db.session.query(
        func.min(HealthData.metric_value).label('min_value'),
        func.max(HealthData.metric_value).label('max_value')
    ).join(DataType).filter(DataType.metric_name == 'Energy (kcal)').first()
    
    min_calories = int(energy_stats.min_value) if energy_stats and energy_stats.min_value is not None else 0
    max_calories_bound = int(energy_stats.max_value) if energy_stats and energy_stats.max_value is not None else 4000
    
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
    
    query = db.session.query(DataType.metric_name).distinct()
    
    if source:
        query = query.filter(DataType.source == source)
    
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
        data_type = request.form.get('data_type', 'all')  # Default to all data
        
        if not start_date or not end_date:
            flash('Start date and end date are required', 'error')
            return redirect(url_for('data.import_data'))
            
        # Log import parameters
        current_app.logger.info(f"Oura import initiated: date range {start_date} to {end_date}, type: {data_type}")
        
        importer = OuraImporter(personal_token=personal_token)
        
        imported_data = []
        
        # Import sleep data
        if data_type == 'sleep' or data_type == 'all':
            try:
                current_app.logger.info(f"Starting sleep data import: {start_date} to {end_date}")
                sleep_data = importer.import_sleep_data(start_date, end_date)
                imported_data.extend(sleep_data)
                current_app.logger.info(f"Sleep data import completed: {len(sleep_data)} records")
                flash(f'Successfully imported {len(sleep_data)} Oura sleep data points', 'success')
            except Exception as e:
                current_app.logger.error(f"Error importing sleep data: {str(e)}")
                flash(f'Error importing sleep data: {str(e)}', 'error')
        
        # Import activity data
        if data_type == 'activity' or data_type == 'all':
            try:
                current_app.logger.info(f"Starting activity data import: {start_date} to {end_date}")
                activity_data = importer.import_activity_data(start_date, end_date)
                imported_data.extend(activity_data)
                current_app.logger.info(f"Activity data import completed: {len(activity_data)} records")
                flash(f'Successfully imported {len(activity_data)} Oura activity data points', 'success')
            except Exception as e:
                current_app.logger.error(f"Error importing activity data: {str(e)}")
                flash(f'Error importing activity data: {str(e)}', 'error')
        
        # Import tags data
        if data_type == 'tags' or data_type == 'all':
            try:
                current_app.logger.info(f"Starting tag data import: {start_date} to {end_date}")
                tags_data = importer.import_tags_data(start_date, end_date)
                imported_data.extend(tags_data)
                current_app.logger.info(f"Tag data import completed: {len(tags_data)} records")
                flash(f'Successfully imported {len(tags_data)} Oura tag data points', 'success')
            except Exception as e:
                current_app.logger.error(f"Error importing tag data: {str(e)}")
                flash(f'Note: Tag data import failed, but other data were imported if selected: {str(e)}', 'warning')
        
        # Create import record
        import_record = ImportRecord(
            source='oura',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date(),
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date(),
            record_count=len(imported_data),
            status='success'
        )
        db.session.add(import_record)
        db.session.commit()
        
        # Debug database counts
        if current_app.config.get('DEBUG', False):
            # Count sleep records
            sleep_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.in_(['sleep_score', 'rem_sleep', 'deep_sleep'])
            ).count()
            
            # Count activity records
            activity_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.in_(['activity_score', 'steps'])
            ).count()
            
            # Count tag records
            tag_count = db.session.query(HealthData).join(
                DataType, HealthData.data_type_id == DataType.id
            ).filter(
                DataType.source == 'oura',
                DataType.metric_name.like('tag_%')
            ).count()
            
            current_app.logger.info(f"Database counts - Sleep: {sleep_count}, Activity: {activity_count}, Tags: {tag_count}")
        
    except Exception as e:
        current_app.logger.error(f"Error importing Oura API data: {e}")
        flash(f'Error importing data: {str(e)}', 'error')
        
        # Create failed import record
        import_record = ImportRecord(
            source='oura',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None,
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None,
            record_count=0,
            status='failed',
            error_message=str(e)
        )
        db.session.add(import_record)
        db.session.commit()
    
    return redirect(url_for('data.import_data'))

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
    health_data = HealthData.query.join(DataType).filter(
        HealthData.date == selected_date
    ).order_by(
        DataType.source, DataType.metric_name
    ).all()
    
    # Group data by source for easier display
    data_by_source = {}
    for item in health_data:
        source = item.data_type.source
        if source not in data_by_source:
            data_by_source[source] = []
        data_by_source[source].append(item)
    
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

@data_bp.route('/diagnose/oura', methods=['GET', 'POST'])
def diagnose_oura():
    """Diagnostic page for Oura API connection issues"""
    if not session.get('oura_connected'):
        flash('You need to connect your Oura Ring first', 'error')
        return redirect(url_for('data.import_data'))
        
    personal_token = session.get('oura_personal_token')
    diagnostics = None
    
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Start date and end date are required', 'error')
        else:
            try:
                importer = OuraImporter(personal_token=personal_token)
                diagnostics = importer.diagnostic_check(start_date, end_date)
                flash('Diagnostic check completed! See results below.', 'success')
            except Exception as e:
                current_app.logger.error(f"Error running diagnostics: {e}")
                flash(f'Error running diagnostics: {str(e)}', 'error')
    
    # Get list of all metrics in the database
    metrics = db.session.query(
        DataType.metric_name, db.func.count(HealthData.id)
    ).join(
        HealthData, DataType.id == HealthData.data_type_id
    ).filter(
        DataType.source == 'oura'
    ).group_by(
        DataType.metric_name
    ).all()
    
    # Set default dates if not provided (last 30 days)
    today = date.today()
    default_end_date = today.strftime('%Y-%m-%d')
    default_start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    
    return render_template('data/diagnose_oura.html', 
                          diagnostics=diagnostics,
                          metrics=metrics,
                          default_start_date=default_start_date,
                          default_end_date=default_end_date)

@data_bp.route('/reset/oura', methods=['POST'])
def reset_oura_data():
    """Reset and re-import all Oura data"""
    if not session.get('oura_connected'):
        flash('You need to connect your Oura Ring first', 'error')
        return redirect(url_for('data.import_data'))
    
    try:
        personal_token = session.get('oura_personal_token')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Start date and end date are required', 'error')
            return redirect(url_for('data.diagnose_oura'))
        
        # Delete all existing Oura data
        current_app.logger.info(f"Deleting all Oura data before reimport")
        
        # 1. Find all Oura data types
        oura_data_types = DataType.query.filter_by(source='oura').all()
        data_type_ids = [dt.id for dt in oura_data_types]
        
        # 2. Delete all HealthData records with these data_type_ids
        if data_type_ids:
            delete_count = HealthData.query.filter(HealthData.data_type_id.in_(data_type_ids)).delete(synchronize_session=False)
            current_app.logger.info(f"Deleted {delete_count} Oura health data records")
            
            # 3. Delete the data types themselves
            for dt in oura_data_types:
                db.session.delete(dt)
                
            # 4. Delete Oura import records
            import_records = ImportRecord.query.filter(ImportRecord.source.like('oura%')).all()
            for record in import_records:
                db.session.delete(record)
                
            db.session.commit()
            flash(f'Successfully deleted {delete_count} existing Oura data records', 'info')
        
        # Re-import all data
        importer = OuraImporter(personal_token=personal_token)
        
        # Import all data types
        current_app.logger.info(f"Starting full Oura data re-import from {start_date} to {end_date}")
        
        # Import sleep data
        try:
            sleep_data = importer.import_sleep_data(start_date, end_date)
            flash(f'Successfully re-imported {len(sleep_data)} Oura sleep data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error re-importing sleep data: {str(e)}")
            flash(f'Error re-importing sleep data: {str(e)}', 'error')
        
        # Import activity data
        try:
            activity_data = importer.import_activity_data(start_date, end_date)
            flash(f'Successfully re-imported {len(activity_data)} Oura activity data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error re-importing activity data: {str(e)}")
            flash(f'Error re-importing activity data: {str(e)}', 'error')
        
        # Import tags data
        try:
            tags_data = importer.import_tags_data(start_date, end_date)
            flash(f'Successfully re-imported {len(tags_data)} Oura tag data points', 'success')
        except Exception as e:
            current_app.logger.error(f"Error re-importing tag data: {str(e)}")
            flash(f'Error re-importing tag data: {str(e)}', 'warning')
        
        # Create import record
        import_record = ImportRecord(
            source='oura',
            date_imported=datetime.now(),
            date_range_start=datetime.strptime(start_date, '%Y-%m-%d').date(),
            date_range_end=datetime.strptime(end_date, '%Y-%m-%d').date(),
            record_count=len(sleep_data) + len(activity_data) + len(tags_data) if 'sleep_data' in locals() and 'activity_data' in locals() and 'tags_data' in locals() else 0,
            status='success'
        )
        db.session.add(import_record)
        db.session.commit()
        
        flash('Complete re-import of Oura data finished!', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error during Oura data reset/reimport: {e}")
        flash(f'Error during reset/reimport process: {str(e)}', 'error')
    
    return redirect(url_for('data.diagnose_oura'))

@data_bp.route('/data-types', methods=['GET'])
def data_types():
    """View all data types in the system"""
    data_types = DataType.query.order_by(DataType.source, DataType.metric_name).all()
    return render_template('data/data_types.html', data_types=data_types)

@data_bp.route('/data-types/edit/<int:type_id>', methods=['GET', 'POST'])
def edit_data_type(type_id):
    """Edit a specific data type"""
    data_type = DataType.query.get_or_404(type_id)
    
    if request.method == 'POST':
        try:
            data_type.source = request.form['source']
            data_type.metric_name = request.form['metric_name']
            data_type.metric_units = request.form['metric_units']
            data_type.source_type = request.form['source_type']
            
            db.session.commit()
            flash(f'Successfully updated data type: {data_type.source}:{data_type.metric_name}', 'success')
            return redirect(url_for('data.data_types'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating data type: {e}")
            flash(f'Error updating data type: {str(e)}', 'error')
    
    return render_template('data/edit_data_type.html', data_type=data_type)

@data_bp.route('/data-types/delete/<int:type_id>', methods=['POST'])
def delete_data_type(type_id):
    """Delete a data type (with confirmation)"""
    data_type = DataType.query.get_or_404(type_id)
    
    try:
        # Check if there's any health data using this data type
        if data_type.health_data.count() > 0:
            flash(f'Cannot delete data type that has {data_type.health_data.count()} data points. Delete the data first.', 'error')
            return redirect(url_for('data.data_types'))
        
        source = data_type.source
        metric = data_type.metric_name
        
        db.session.delete(data_type)
        db.session.commit()
        
        flash(f'Successfully deleted data type: {source}:{metric}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting data type: {e}")
        flash(f'Error deleting data type: {str(e)}', 'error')
    
    return redirect(url_for('data.data_types')) 