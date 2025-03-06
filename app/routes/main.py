from flask import Blueprint, render_template
from ..models.base import DataSource

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page"""
    # Get all data sources
    data_sources = DataSource.query.order_by(DataSource.name).all()
    
    return render_template('index.html', data_sources=data_sources)

@main_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')
