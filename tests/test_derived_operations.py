import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.utils.derived_operations import (
    TimeShiftOperation, MultiplyOperation, DivideOperation,
    MovingAverageOperation, OperationRegistry
)

class TestDerivedOperations(unittest.TestCase):
    def setUp(self):
        # Create test data with dates and values
        self.dates = [datetime.now().date() - timedelta(days=i) for i in range(10)]
        self.values = [float(i) for i in range(10)]
        self.test_data = pd.DataFrame({
            'date': self.dates,
            'value': self.values
        })
        
        # Secondary data with different values but same dates
        self.secondary_data = pd.DataFrame({
            'date': self.dates,
            'value': [float(i * 2) for i in range(10)]
        })
        
    def test_time_shift_operation(self):
        """Test time shift operation works correctly"""
        op = TimeShiftOperation()
        
        # Test shifting forward
        result = op.apply(self.test_data, {'days': 3})
        self.assertEqual(len(result), len(self.test_data))
        self.assertEqual(result['date'][0], self.test_data['date'][0] + timedelta(days=3))
        
        # Test shifting backward
        result = op.apply(self.test_data, {'days': -2})
        self.assertEqual(len(result), len(self.test_data))
        self.assertEqual(result['date'][0], self.test_data['date'][0] - timedelta(days=2))
        
    def test_multiply_operation_scalar(self):
        """Test multiply operation with scalar value"""
        op = MultiplyOperation()
        
        # Test multiplying by 2
        result = op.apply(self.test_data, {'value_type': 'scalar', 'scalar': 2})
        self.assertEqual(len(result), len(self.test_data))
        
        for i in range(len(self.test_data)):
            self.assertAlmostEqual(result['value'].iloc[i], self.test_data['value'].iloc[i] * 2)
    
    def test_multiply_operation_data_type(self):
        """Test multiply operation with another data type"""
        op = MultiplyOperation()
        
        # Mock implementation of get_data_for_derivation
        def mock_get_data(*args, **kwargs):
            return self.secondary_data
            
        # Replace the function temporarily
        import app.utils.derived_operations
        original_func = app.utils.derived_operations.get_data_for_derivation
        app.utils.derived_operations.get_data_for_derivation = mock_get_data
        
        try:
            # Test multiplying by another data type
            result = op.apply(self.test_data, {'value_type': 'data_type', 'data_type_id': 1})
            
            # After join, we should have same number of rows (for matching dates)
            self.assertEqual(len(result), len(self.test_data))
            
            # Check a few values
            # test_data values: [0, 1, 2, 3, ...]
            # secondary_data values: [0, 2, 4, 6, ...]
            # so result should be [0, 2, 8, 18, ...]
            for i in range(len(self.test_data)):
                expected = self.test_data['value'].iloc[i] * self.secondary_data['value'].iloc[i]
                self.assertAlmostEqual(result['value'].iloc[i], expected)
        finally:
            # Restore the original function
            app.utils.derived_operations.get_data_for_derivation = original_func
    
    def test_divide_operation_scalar(self):
        """Test divide operation with scalar value"""
        op = DivideOperation()
        
        # Test dividing by 2
        result = op.apply(self.test_data, {'value_type': 'scalar', 'scalar': 2})
        self.assertEqual(len(result), len(self.test_data))
        
        for i in range(len(self.test_data)):
            self.assertAlmostEqual(result['value'].iloc[i], self.test_data['value'].iloc[i] / 2)
        
        # Test dividing by zero - should raise ValueError
        with self.assertRaises(ValueError):
            op.apply(self.test_data, {'value_type': 'scalar', 'scalar': 0})
    
    def test_divide_operation_data_type(self):
        """Test divide operation with another data type"""
        op = DivideOperation()
        
        # Mock implementation of get_data_for_derivation
        def mock_get_data(*args, **kwargs):
            return self.secondary_data
            
        # Replace the function temporarily
        import app.utils.derived_operations
        original_func = app.utils.derived_operations.get_data_for_derivation
        app.utils.derived_operations.get_data_for_derivation = mock_get_data
        
        try:
            # Test dividing by another data type
            result = op.apply(self.test_data, {'value_type': 'data_type', 'data_type_id': 1})
            
            # After join, we should have same number of rows (for matching dates)
            self.assertEqual(len(result), len(self.test_data))
            
            # Check values - note that first value will be NaN due to 0/0
            for i in range(1, len(self.test_data)):
                expected = self.test_data['value'].iloc[i] / self.secondary_data['value'].iloc[i]
                self.assertAlmostEqual(result['value'].iloc[i], expected)
        finally:
            # Restore the original function
            app.utils.derived_operations.get_data_for_derivation = original_func
    
    def test_moving_average_operation(self):
        """Test moving average operation with different window sizes"""
        op = MovingAverageOperation()
        
        # Test with window size 3
        result = op.apply(self.test_data, {'window': 3})
        self.assertEqual(len(result), len(self.test_data))
        
        # First value should remain the same (window size 1)
        self.assertAlmostEqual(result['value'].iloc[0], self.test_data['value'].iloc[0])
        
        # Second value should be average of first two
        expected_second = (self.test_data['value'].iloc[0] + self.test_data['value'].iloc[1]) / 2
        self.assertAlmostEqual(result['value'].iloc[1], expected_second)
        
        # Third value and beyond should be average of three values
        for i in range(2, len(self.test_data)):
            expected = (self.test_data['value'].iloc[i-2] + 
                        self.test_data['value'].iloc[i-1] + 
                        self.test_data['value'].iloc[i]) / 3
            self.assertAlmostEqual(result['value'].iloc[i], expected)
        
        # Test with window size 1 (should be same as original)
        result = op.apply(self.test_data, {'window': 1})
        for i in range(len(self.test_data)):
            self.assertAlmostEqual(result['value'].iloc[i], self.test_data['value'].iloc[i])
        
        # Test with invalid window size
        with self.assertRaises(ValueError):
            op.apply(self.test_data, {'window': 0})
    
    def test_operation_registry(self):
        """Test operation registry functionality"""
        registry = OperationRegistry()
        
        # Clear existing operations for clean test
        registry._operations = {}
        
        # Register operations
        registry.register(TimeShiftOperation())
        registry.register(MultiplyOperation())
        
        # Test getting operations
        self.assertIsInstance(registry.get_operation('time_shift'), TimeShiftOperation)
        self.assertIsInstance(registry.get_operation('multiply'), MultiplyOperation)
        self.assertIsNone(registry.get_operation('non_existent_op'))
        
        # Test getting all operations
        all_ops = registry.get_all_operations()
        
        # Note: We expect 4 operations to be registered by default
        # (TimeShift, Multiply, Divide, MovingAverage)
        self.assertEqual(len(all_ops), 4)
        
        # Verify all expected operation types are present
        self.assertTrue(any(isinstance(op, TimeShiftOperation) for op in all_ops))
        self.assertTrue(any(isinstance(op, MultiplyOperation) for op in all_ops))
        self.assertTrue(any(isinstance(op, DivideOperation) for op in all_ops))
        self.assertTrue(any(isinstance(op, MovingAverageOperation) for op in all_ops))

    def test_operation_parameter_validation(self):
        """Test parameter validation for operations"""
        time_shift = TimeShiftOperation()
        
        # Valid parameters
        valid, errors = time_shift.validate_params({'days': 5})
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
        
        # Missing required parameter
        valid, errors = time_shift.validate_params({})
        self.assertFalse(valid)
        self.assertIn('days', errors)
        
        # Test conditional validation with MultiplyOperation
        multiply = MultiplyOperation()
        
        # Valid scalar parameters
        valid, errors = multiply.validate_params({
            'value_type': 'scalar',
            'scalar': 2.5
        })
        self.assertTrue(valid)
        
        # Missing conditional parameter
        valid, errors = multiply.validate_params({
            'value_type': 'scalar'
        })
        self.assertFalse(valid)
        self.assertIn('scalar', errors)

if __name__ == '__main__':
    unittest.main()