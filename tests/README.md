# Health Tracker Tests

This directory contains the test suite for the Health Tracker application. The tests are organized by functionality and use the Python `unittest` framework.

## Running Tests

You can run all the tests using the `run_tests.py` script in the root directory:

```bash
python run_tests.py
```

Or you can run individual test files:

```bash
python -m unittest tests/test_models.py
```

## Test Structure

The tests are organized into the following files:

- `test_base.py`: Base test case with common setup and teardown logic
- `test_models.py`: Tests for the database models
- `test_routes.py`: Tests for the Flask routes
- `test_importers.py`: Tests for the data import functionality (using mocks)
- `test_analyzer.py`: Tests for the correlation analysis functionality (using mocks)

## Mock Implementation

Since the actual service implementations may depend on external APIs or complex dependencies, we use mock implementations for testing:

- `MockOuraImporter`: Simulates the Oura API importer
- `MockChronometerImporter`: Simulates the Chronometer CSV importer
- `MockHealthAnalyzer`: Simulates the health data analyzer

These mocks allow us to test the functionality without requiring the actual external dependencies.

## Writing New Tests

When adding new functionality to the application, please add corresponding tests. Each test should:

1. Inherit from `BaseTestCase` to get the common setup and teardown logic
2. Have clear, descriptive test method names
3. Include docstrings explaining what is being tested
4. Use assertions to verify expected behavior

Example:

```python
from tests.test_base import BaseTestCase

class MyNewTestCase(BaseTestCase):
    """Test case for my new functionality."""
    
    def test_new_feature(self):
        """Test that my new feature works correctly."""
        # Test code here
        result = my_function()
        self.assertEqual(result, expected_value)
```

## Test Environment

The tests use a temporary SQLite database that is created for each test and deleted afterward. This ensures that tests don't interfere with each other and don't modify your development database.

The `BaseTestCase` class sets up the Flask application in test mode and provides a test client that you can use to make requests to the application.

## Troubleshooting

If you encounter import errors, make sure that:

1. The parent directory is in the Python path (we add it in each test file)
2. You're using the correct import paths (from the root of the project)
3. You're running the tests from the root directory of the project 