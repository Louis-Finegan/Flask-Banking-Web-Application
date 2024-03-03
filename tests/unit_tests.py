
import sys

sys.path.insert(1, '../')

import unittest
import main as app
    

class TestFlaskApp(unittest.TestCase):

    def setUp(self):
        # Set up test environment, if needed
        pass

    def tearDown(self):
        # Clean up test environment, if needed
        pass

    def test_home_route(self):
        # Test the home route of the Flask app
        with app.test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Hello, World!', response.data)

    # Add more unit tests for other routes and functions of your Flask app as needed

if __name__ == '__main__':
    unittest.main()
