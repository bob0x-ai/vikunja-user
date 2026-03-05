#!/usr/bin/env python3
"""Tests for api_client module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api_client import VikunjaClient, AuthError, APIError, NotFoundError


class TestVikunjaClient(unittest.TestCase):
    """Test cases for VikunjaClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / 'config.yaml'
        self.creds_path = Path(self.temp_dir) / 'users.yaml'
        
        # Create test config
        config_content = f"""
vikunja:
  base_url: http://localhost:3456/api/v1

paths:
  credentials: {self.creds_path}
  token_refresh: {self.temp_dir}/refresh.sh
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
        
        # Create test credentials
        creds_content = """
users:
  testuser:
    user: testuser
    id: 123
    password: testpass
    token: test_token_123
    scope: worker
"""
        with open(self.creds_path, 'w') as f:
            f.write(creds_content)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_credentials_success(self):
        """Test successful credential loading."""
        client = VikunjaClient('testuser', str(self.config_path))
        self.assertEqual(client._token, 'test_token_123')
        self.assertEqual(client._user_id, 123)
    
    def test_load_credentials_missing_file(self):
        """Test AuthError when credentials file doesn't exist."""
        # Delete the credentials file
        self.creds_path.unlink()
        
        with self.assertRaises(AuthError) as context:
            VikunjaClient('testuser', str(self.config_path))
        
        self.assertIn('not found in configuration', str(context.exception))
    
    def test_load_credentials_user_not_found(self):
        """Test AuthError when user doesn't exist in credentials."""
        with self.assertRaises(AuthError) as context:
            VikunjaClient('nonexistent', str(self.config_path))
        
        self.assertIn('nonexistent', str(context.exception))
    
    @patch('api_client.requests.Session.request')
    def test_successful_request(self, mock_request):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 1, 'title': 'Test Task'}
        mock_request.return_value = mock_response
        
        client = VikunjaClient('testuser', str(self.config_path))
        result = client.get('/tasks/1')
        
        self.assertEqual(result['id'], 1)
        self.assertEqual(result['title'], 'Test Task')
        
        # Verify request was made with correct headers
        call_args = mock_request.call_args
        self.assertEqual(call_args[1]['headers']['Authorization'], 'Bearer test_token_123')
    
    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_token_refresh_on_401(self, mock_subprocess, mock_request):
        """Test automatic token refresh on 401 response."""
        # First call returns 401, second call succeeds
        mock_response_401 = Mock()
        mock_response_401.status_code = 401
        mock_response_401.ok = False
        
        mock_response_200 = Mock()
        mock_response_200.ok = True
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'id': 1, 'title': 'Test Task'}
        
        mock_request.side_effect = [mock_response_401, mock_response_200]
        
        # Mock successful token refresh
        mock_subprocess.return_value = Mock(returncode=0, stdout='', stderr='')
        
        client = VikunjaClient('testuser', str(self.config_path))
        
        # Update the token to simulate refresh
        with patch.object(client, '_load_credentials') as mock_load:
            client._token = 'new_token_456'
            mock_load.side_effect = None
            
            result = client.get('/tasks/1')
            
            # Should have called refresh script
            mock_subprocess.assert_called_once()
            self.assertEqual(result['id'], 1)
    
    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_when_refresh_fails(self, mock_subprocess, mock_request):
        """Test AuthError when token refresh fails."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.ok = False
        mock_request.return_value = mock_response
        
        # Mock failed token refresh
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        
        client = VikunjaClient('testuser', str(self.config_path))
        
        with self.assertRaises(AuthError) as context:
            client.get('/tasks/1')
        
        self.assertIn('expired', str(context.exception))
    
    @patch('api_client.requests.Session.request')
    def test_not_found_error(self, mock_request):
        """Test NotFoundError on 404 response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_request.return_value = mock_response
        
        client = VikunjaClient('testuser', str(self.config_path))
        
        with self.assertRaises(NotFoundError):
            client.get('/tasks/999')
    
    @patch('api_client.requests.Session.request')
    def test_api_error_with_message(self, mock_request):
        """Test APIError with error message from response."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.ok = False
        mock_response.json.return_value = {'message': 'Invalid task data'}
        mock_response.text = ''
        mock_request.return_value = mock_response
        
        client = VikunjaClient('testuser', str(self.config_path))
        
        with self.assertRaises(APIError) as context:
            client.post('/tasks', data={'title': ''})
        
        self.assertIn('Invalid task data', str(context.exception))


if __name__ == '__main__':
    unittest.main()
