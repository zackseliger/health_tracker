from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load configuration from config.py
    from .config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    from .routes.main import main_bp
    from .routes.data import data_bp
    from .routes.analysis import analysis_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(data_bp, url_prefix='/data')
    app.register_blueprint(analysis_bp, url_prefix='/analysis')
    
    # Register Jinja2 context processors
    @app.context_processor
    def utility_processor():
        return {
            'now': datetime.now
        }
    
    # Create database tables if they don't exist
    # Only create tables in development or production, not during testing
    if config_name != 'testing':
        with app.app_context():
            db.create_all()
    
    return app 

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) 
