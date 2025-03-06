import unittest
import os
import tempfile
from app import create_app, db

class BaseTestCase(unittest.TestCase):
    """Base test case for health tracker app tests."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temp file to use as the test database
        self.db_fd, db_path = tempfile.mkstemp()
        
        # Configure the app for testing
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            DEBUG=False,
            SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
            SERVER_NAME='localhost',
        )
        
        # Create an app context and a test client
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        
        # Create all database tables
        db.create_all()
    
    def tearDown(self):
        """Clean up after each test."""
        # Drop all tables
        db.session.remove()
        db.drop_all()
        
        # Close the app context
        self.app_context.pop()
        
        # Close and delete the temp database file
        os.close(self.db_fd)
        os.unlink(self.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')) 