# unit_tests.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join('..')))
import unittest
from flask import Flask
from Website import db, create_app
from Website.models import User

from werkzeug.security import generate_password_hash, check_password_hash

class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        # Create a test Flask application
        self.app = create_app()
        self.client = self.app.test_client()

        # Establish a context for the tests
        with self.app.app_context():
            # Create all tables in the test database
            db.create_all()

            # Add test data or perform any other setup required for your tests
            self.user = User(
                username='test user',
                password=generate_password_hash(
                    'Password/'),
                email='test@example.com',
                address='add1',
                country='Ireland',
                dob='01/01/2000'
            )
            db.session.add(self.user)
            db.session.commit()

    def tearDown(self):
        # Clean up after each test
        with self.app.app_context():
            # Drop all tables from the test database
            db.session.remove()
            db.drop_all()

    def test_dashboard_route(self):
        # Log in the test user
        response = self.client.post('/login', data=dict(
            username='test user',
            password='Password/'  # Replace with the actual password
        ), follow_redirects=True)

        # Make a GET request to the dashboard route
        response = self.client.get('/')

        # Assert that the response status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # You can add more assertions here based on the behavior of your dashboard route

if __name__ == '__main__':
    unittest.main()


