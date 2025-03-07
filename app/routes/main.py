from flask import Blueprint, render_template
from ..models.base import DataType
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page"""
    # Get all data sources (unique sources from DataType)
    data_sources = DataType.query.with_entities(
        DataType.source, 
        func.max(DataType.last_import).label('last_import')
    ).group_by(DataType.source).order_by(DataType.source).all()
    
    return render_template('index.html', data_sources=data_sources)

@main_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')
