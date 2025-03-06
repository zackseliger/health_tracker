#!/usr/bin/env python3
"""
Test runner for the Health Tracker application.
Discovers and runs all tests in the tests directory.
"""

import unittest
import sys
import os

# Add the parent directory to the path so that we can import the application
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if __name__ == '__main__':
    # Discover and run all tests
    test_suite = unittest.defaultTestLoader.discover('.', pattern='test_*.py')
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return a non-zero exit code if there were any errors or failures
    sys.exit(not result.wasSuccessful()) 