from .. import db
from datetime import datetime

class DataType(db.Model):
    """Model for storing metadata about health data types and sources"""
    __tablename__ = 'data_types'
    
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # 'oura', 'chronometer', 'custom', etc.
    metric_name = db.Column(db.String(100), nullable=False)
    metric_units = db.Column(db.String(50))
    source_type = db.Column(db.String(50), nullable=True)  # 'api', 'csv', 'manual'
    description = db.Column(db.Text)
    last_import = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ensure unique combinations of source and metric_name
    __table_args__ = (
        db.UniqueConstraint('source', 'metric_name', name='unique_metric_type'),
    )
    
    # Relationship to HealthData
    health_data = db.relationship('HealthData', backref='data_type', lazy='dynamic')
    
    def __repr__(self):
        return f"<DataType {self.source}:{self.metric_name} ({self.metric_units})>"
    
    @classmethod
    def get_data_source(cls, source_name):
        """Get DataType records that serve as a data source (for compatibility with old DataSource usage)"""
        # First try to get the source_info record for this exact source
        source = cls.query.filter_by(source=source_name, metric_name='source_info').first()
        
        # If not found, try with the base source name (without suffixes)
        if not source and '_' in source_name:
            base_source = source_name.split('_')[0]
            source = cls.query.filter_by(source=base_source, metric_name='source_info').first()
            
        # If still not found, get any record for this source
        if not source:
            source = cls.query.filter_by(source=source_name).first()
            
        return source
    
    @classmethod
    def update_last_import(cls, source_name):
        """Update the last_import timestamp for all DataType records with the given source"""
        # Update timestamps for all records with this source
        source_records = cls.query.filter_by(source=source_name).all()
        
        now = datetime.utcnow()
        for record in source_records:
            record.last_import = now
        
        # Check if we already have a source_info record for this source
        source_info = cls.query.filter_by(source=source_name, metric_name='source_info').first()
        
        if source_info:
            # Update the existing source_info record
            source_info.last_import = now
            if not source_info.source_type or source_info.source_type == 'unknown':
                # Update source_type if it's not set or unknown
                if 'oura' in source_name:
                    source_info.source_type = 'api'
                elif 'chronometer' in source_name:
                    source_info.source_type = 'csv'
                elif 'custom' in source_name:
                    source_info.source_type = 'manual'
        else:
            # Determine the source_type based on the source_name
            source_type = 'unknown'
            if 'oura' in source_name:
                source_type = 'api'
            elif 'chronometer' in source_name:
                source_type = 'csv'
            elif 'custom' in source_name:
                source_type = 'manual'
            
            # Create a placeholder record for this source
            source_info = cls(
                source=source_name,  # Use the exact source name
                metric_name='source_info',
                source_type=source_type,
                last_import=now
            )
            db.session.add(source_info)
        
        db.session.commit()
        return source_info

class HealthData(db.Model):
    """Base model for all health data types"""
    __tablename__ = 'health_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    data_type_id = db.Column(db.Integer, db.ForeignKey('data_types.id'), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'data_type_id', name='unique_metric_per_day'),
    )
    
    def __repr__(self):
        if self.data_type:
            return f"<HealthData {self.data_type.source}:{self.data_type.metric_name}={self.metric_value} on {self.date}>"
        return f"<HealthData {self.id}={self.metric_value} on {self.date}>"
    
    @classmethod
    def create(cls, date, source, metric_name, metric_value, metric_units=None, notes=None):
        """
        Factory method to create a HealthData record with the associated DataType.
        This simplifies the migration from the old model to the new model.
        """
        data_type = DataType.query.filter_by(source=source, metric_name=metric_name).first()
        
        if not data_type:
            data_type = DataType(source=source, metric_name=metric_name, metric_units=metric_units)
            db.session.add(data_type)
        
        health_data = cls(
            date=date,
            data_type=data_type,
            metric_value=metric_value,
            notes=notes
        )
        
        return health_data

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