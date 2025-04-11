import pandas as pd
import numpy as np
from datetime import datetime
from .. import db
from ..models.base import HealthData, DataType

class DerivedDataOperation:
    """Base class for operations that can be applied to create derived data"""
    
    @property
    def name(self):
        """The display name of this operation"""
        raise NotImplementedError("Subclasses must implement this property")
    
    @property
    def slug(self):
        """Unique identifier for this operation"""
        raise NotImplementedError("Subclasses must implement this property")
        
    def get_param_schema(self):
        """Get the schema for parameters this operation requires"""
        raise NotImplementedError("Subclasses must implement this method")
        
    def validate_params(self, params):
        """Validate the provided parameters against the schema"""
        schema = self.get_param_schema()
        errors = {}
        
        for param_name, param_schema in schema.items():
            if param_schema.get('required', False) and param_name not in params:
                errors[param_name] = f"{param_name} is required"
            
            # Check required_if conditions
            if 'required_if' in param_schema and param_name not in params:
                condition_met = True
                for cond_key, cond_value in param_schema['required_if'].items():
                    if params.get(cond_key) != cond_value:
                        condition_met = False
                        break
                
                if condition_met:
                    errors[param_name] = f"{param_name} is required when {list(param_schema['required_if'].keys())[0]} is {list(param_schema['required_if'].values())[0]}"
        
        return len(errors) == 0, errors
        
    def apply(self, source_data, params):
        """Apply the operation to source data"""
        raise NotImplementedError("Subclasses must implement this method")


class TimeShiftOperation(DerivedDataOperation):
    @property
    def name(self):
        return "Time Shift"
        
    @property
    def slug(self):
        return "time_shift"
        
    def get_param_schema(self):
        return {
            "days": {
                "type": "integer",
                "description": "Number of days to shift (positive = forward, negative = backward)",
                "required": True
            }
        }
        
    def apply(self, source_data, params):
        """Shift data by specified number of days"""
        days = int(params.get("days", 0))
        
        # Create a copy to not modify the original
        result_data = source_data.copy()
        
        # Apply the shift to the dates
        result_data['date'] = result_data['date'].apply(
            lambda d: d + pd.Timedelta(days=days))
            
        return result_data


class MultiplyOperation(DerivedDataOperation):
    @property
    def name(self):
        return "Multiply"
        
    @property
    def slug(self):
        return "multiply"
        
    def get_param_schema(self):
        return {
            "value_type": {
                "type": "string",
                "description": "Type of value to multiply by",
                "options": ["scalar", "data_type"],
                "required": True
            },
            "scalar": {
                "type": "float",
                "description": "Scalar value to multiply by",
                "required_if": {"value_type": "scalar"}
            },
            "data_type_id": {
                "type": "data_type",
                "description": "ID of the DataType to multiply by",
                "required_if": {"value_type": "data_type"}
            }
        }
        
    def apply(self, source_data, params):
        """Multiply data by scalar or another data type"""
        value_type = params.get("value_type")
        result_data = source_data.copy()
        
        if value_type == "scalar":
            scalar = float(params.get("scalar", 1.0))
            result_data['value'] = result_data['value'] * scalar
        elif value_type == "data_type":
            data_type_id = int(params.get("data_type_id"))
            
            # Get the secondary data
            secondary_data = get_data_for_derivation(data_type_id)
            
            # Create a date-indexed dataframe for easy alignment
            source_indexed = result_data.set_index('date')
            secondary_indexed = secondary_data.set_index('date')
            
            # Multiply aligned values
            merged = source_indexed.join(secondary_indexed, lsuffix='_source', rsuffix='_secondary')
            merged['value'] = merged['value_source'] * merged['value_secondary']
            
            # Keep only the date and value columns
            result_data = merged[['value']].reset_index()
            
        return result_data


class DivideOperation(DerivedDataOperation):
    @property
    def name(self):
        return "Divide"
        
    @property
    def slug(self):
        return "divide"
        
    def get_param_schema(self):
        return {
            "value_type": {
                "type": "string",
                "description": "Type of value to divide by",
                "options": ["scalar", "data_type"],
                "required": True
            },
            "scalar": {
                "type": "float",
                "description": "Scalar value to divide by",
                "required_if": {"value_type": "scalar"}
            },
            "data_type_id": {
                "type": "data_type",
                "description": "ID of the DataType to divide by",
                "required_if": {"value_type": "data_type"}
            }
        }
        
    def apply(self, source_data, params):
        """Divide data by scalar or another data type"""
        value_type = params.get("value_type")
        result_data = source_data.copy()
        
        if value_type == "scalar":
            scalar = float(params.get("scalar", 1.0))
            if scalar == 0:
                raise ValueError("Cannot divide by zero")
            result_data['value'] = result_data['value'] / scalar
        elif value_type == "data_type":
            data_type_id = int(params.get("data_type_id"))
            
            # Get the secondary data
            secondary_data = get_data_for_derivation(data_type_id)
            
            # Create a date-indexed dataframe for easy alignment
            source_indexed = result_data.set_index('date')
            secondary_indexed = secondary_data.set_index('date')
            
            # Merge the dataframes and divide aligned values
            merged = source_indexed.join(secondary_indexed, lsuffix='_source', rsuffix='_secondary')
            # Handle division by zero
            merged['value'] = merged.apply(
                lambda row: row['value_source'] / row['value_secondary'] 
                if row['value_secondary'] != 0 else None, axis=1)
            
            # Keep only the date and value columns
            result_data = merged[['value']].reset_index()
            
        return result_data


class MovingAverageOperation(DerivedDataOperation):
    @property
    def name(self):
        return "Moving Average"
        
    @property
    def slug(self):
        return "moving_average"
        
    def get_param_schema(self):
        return {
            "window": {
                "type": "integer",
                "description": "Window size in days",
                "required": True
            }
        }
        
    def apply(self, source_data, params):
        """Calculate moving average over specified window size"""
        window = int(params.get("window", 7))
        if window < 1:
            raise ValueError("Window size must be at least 1")
            
        result_data = source_data.copy()
        
        # Set date as index for rolling operation
        df_indexed = result_data.set_index('date')
        
        # Apply rolling average
        df_indexed['value'] = df_indexed['value'].rolling(window=window, min_periods=1).mean()
        
        # Reset index to get date column back
        result_data = df_indexed.reset_index()
        
        return result_data


# Helper function to get data for derivation
def get_data_for_derivation(data_type_id):
    """Fetch data for a specific DataType and convert to DataFrame for derivation operations"""
    data = db.session.query(
        HealthData.date,
        HealthData.metric_value.label('value')
    ).filter(
        HealthData.data_type_id == data_type_id
    ).order_by(
        HealthData.date
    ).all()
    
    # Convert to DataFrame
    return pd.DataFrame([(
        row.date,
        row.value
    ) for row in data], columns=['date', 'value'])


# Registry to keep track of available operations
class OperationRegistry:
    """Registry for available derived data operations"""
    
    _operations = {}
    
    @classmethod
    def register(cls, operation):
        """Register a new operation"""
        cls._operations[operation.slug] = operation
        
    @classmethod
    def get_operation(cls, slug):
        """Get an operation by slug"""
        return cls._operations.get(slug)
        
    @classmethod
    def get_all_operations(cls):
        """Get all registered operations"""
        return list(cls._operations.values())


# Register all built-in operations
registry = OperationRegistry()
registry.register(TimeShiftOperation())
registry.register(MultiplyOperation())
registry.register(DivideOperation())
registry.register(MovingAverageOperation())