#!/usr/bin/env python3
"""
Test runner for the Health Tracker application.
Discovers and runs all tests in the tests directory.
"""

import unittest
import sys
import os

def run_tests():
    """Run all the tests."""
    # Set environment to testing to ensure we never use production settings
    os.environ['FLASK_ENV'] = 'testing'
    
    # Get the tests directory
    tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')
    
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Discover tests in the test directory
    suite = loader.discover(tests_dir, pattern='test_*.py')
    
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    result = runner.run(suite)
    
    # Return a non-zero exit code if there were any errors or failures
    return not result.wasSuccessful()

if __name__ == '__main__':
    sys.exit(run_tests()) 