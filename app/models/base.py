from .. import db
from datetime import datetime

class HealthData(db.Model):
    """Base model for all health data types"""
    __tablename__ = 'health_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    source = db.Column(db.String(50), nullable=False)  # 'oura', 'chronometer', 'custom', etc.
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    metric_units = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'source', 'metric_name', name='unique_metric_per_day'),
    )
    
    def __repr__(self):
        return f"<HealthData {self.source}:{self.metric_name}={self.metric_value} on {self.date}>"

class DataSource(db.Model):
    """Model to track imported data sources"""
    __tablename__ = 'data_sources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    type = db.Column(db.String(50), nullable=False)  # 'api', 'csv', 'manual'
    last_import = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DataSource {self.name} ({self.type})>"

class UserDefinedMetric(db.Model):
    """Model for user-defined custom metrics"""
    __tablename__ = 'user_defined_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    units = db.Column(db.String(50))
    description = db.Column(db.Text)
    frequency = db.Column(db.String(50))  # 'daily', 'weekly', 'monthly', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserDefinedMetric {self.name} ({self.units})>"

class ImportRecord(db.Model):
    """Model to track import operations"""
    __tablename__ = 'import_records'
    
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False)  # e.g., 'oura_sleep', 'chronometer_csv'
    date_imported = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_range_start = db.Column(db.Date)
    date_range_end = db.Column(db.Date)
    record_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), nullable=False)  # 'success', 'failed', 'partial'
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ImportRecord {self.source} - {self.date_range_start} to {self.date_range_end} ({self.record_count} records)>" 