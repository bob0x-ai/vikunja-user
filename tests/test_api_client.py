#!/usr/bin/env python3
"""Tests for api_client module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

auth:
  diagnostics_cache_seconds: 60
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)

        # Create refresh script path so _refresh_token existence check passes
        refresh_script = Path(self.temp_dir) / 'refresh.sh'
        refresh_script.write_text("#!/bin/sh\nexit 0\n")
        refresh_script.chmod(0o755)
        
        # Create test credentials
        creds_content = """
users:
  testuser:
    user: testuser
    id: 123
    password: testpass
    token: test_token_123
    token_id: 555
    token_last_eight: oken_123
    scope: worker
"""
        with open(self.creds_path, 'w') as f:
            f.write(creds_content)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _mock_response(status_code=200, ok=True, json_body=None, text=''):
        resp = Mock()
        resp.status_code = status_code
        resp.ok = ok
        if json_body is None:
            resp.json.side_effect = json.JSONDecodeError("no json", "", 0)
        else:
            resp.json.return_value = json_body
        resp.text = text
        return resp
    
    def test_load_credentials_success(self):
        """Test successful credential loading."""
        client = VikunjaClient('testuser', str(self.config_path))
        self.assertEqual(client._token, 'test_token_123')
        self.assertEqual(client._user_id, 123)
        self.assertEqual(client._token_id, 555)
        self.assertEqual(client._token_last_eight, 'oken_123')

    def test_load_credentials_invalid_token_last_eight(self):
        """Test AuthError when token_last_eight does not match token value."""
        creds_content = """
users:
  testuser:
    user: testuser
    id: 123
    password: testpass
    token: test_token_123
    token_last_eight: mismatch8
"""
        self.creds_path.write_text(creds_content)

        with self.assertRaises(AuthError) as context:
            VikunjaClient('testuser', str(self.config_path))

        self.assertIn('token_last_eight', str(context.exception))
    
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
        
        self.assertIn('token', str(context.exception).lower())

    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_reports_missing_permission(self, mock_subprocess, mock_request):
        """Test detailed 401 message when token is valid but missing route permission."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')

        # 1) original request -> 401
        # 2) token/test -> 200 (token valid)
        # 3) login -> 200 + jwt
        # 4) routes -> includes tasks.update
        # 5) tokens -> current token missing tasks.update
        mock_request.side_effect = [
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
            self._mock_response(status_code=200, ok=True, json_body={'message': 'ok'}),
            self._mock_response(status_code=200, ok=True, json_body={'token': 'jwt_123'}),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body={
                    'tasks': {
                        'update': {'path': '/api/v1/tasks/:projecttask', 'method': 'GET'}
                    }
                },
            ),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body=[
                    {
                        'id': 555,
                        'token_last_eight': 'oken_123',
                        'title': 'testuser-api-token',
                        'created': '2026-03-05T00:00:00Z',
                        'permissions': {'tasks': ['read_all']}
                    }
                ],
            ),
        ]

        client = VikunjaClient('testuser', str(self.config_path))
        with self.assertRaises(AuthError) as context:
            client.get('/tasks/1')

        msg = str(context.exception)
        self.assertIn("missing permission 'tasks.update'", msg)

    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_reports_invalid_token(self, mock_subprocess, mock_request):
        """Test detailed 401 message when token itself is invalid/expired."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        mock_request.side_effect = [
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
        ]

        client = VikunjaClient('testuser', str(self.config_path))
        with self.assertRaises(AuthError) as context:
            client.get('/tasks/1')

        msg = str(context.exception).lower()
        self.assertIn('invalid', msg)
        self.assertIn('expired', msg)

    @patch('api_client.requests.Session.request')
    def test_token_selection_prefers_token_id(self, mock_request):
        """Token permission lookup should use configured token_id over title/fallback heuristics."""
        mock_request.return_value = self._mock_response(
            status_code=200,
            ok=True,
            json_body=[
                {
                    'id': 111,
                    'token_last_eight': 'oken_123',
                    'title': 'testuser-api-token',
                    'created': '2026-03-05T00:00:00Z',
                    'permissions': {'tasks': ['read_all']},
                },
                {
                    'id': 555,
                    'token_last_eight': 'oken_123',
                    'title': 'other-token',
                    'created': '2026-03-01T00:00:00Z',
                    'permissions': {'tasks': ['update']},
                },
            ],
        )
        client = VikunjaClient('testuser', str(self.config_path))
        permissions, note = client._get_token_permissions_with_jwt('jwt_123')
        self.assertEqual(permissions, {'tasks': ['update']})
        self.assertIsNone(note)

    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_uses_cached_diagnostics(self, mock_subprocess, mock_request):
        """Second identical 401 should reuse cached diagnosis and skip extra diagnostic requests."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        mock_request.side_effect = [
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
            self._mock_response(status_code=200, ok=True, json_body={'message': 'ok'}),
            self._mock_response(status_code=200, ok=True, json_body={'token': 'jwt_123'}),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body={'tasks': {'update': {'path': '/api/v1/tasks/:projecttask', 'method': 'GET'}}},
            ),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body=[{
                    'id': 555,
                    'token_last_eight': 'oken_123',
                    'title': 'testuser-api-token',
                    'permissions': {'tasks': ['read_all']},
                }],
            ),
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
        ]

        client = VikunjaClient('testuser', str(self.config_path))
        with self.assertRaises(AuthError):
            client.get('/tasks/1')
        with self.assertRaises(AuthError):
            client.get('/tasks/1')

        self.assertEqual(mock_request.call_count, 6)

    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_reports_object_level_denial(self, mock_subprocess, mock_request):
        """If token has route permission but JWT is also denied, report object-level denial."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        mock_request.side_effect = [
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
            self._mock_response(status_code=200, ok=True, json_body={'message': 'ok'}),
            self._mock_response(status_code=200, ok=True, json_body={'token': 'jwt_123'}),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body={'tasks': {'update': {'path': '/api/v1/tasks/:projecttask', 'method': 'GET'}}},
            ),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body=[{
                    'id': 555,
                    'token_last_eight': 'oken_123',
                    'title': 'testuser-api-token',
                    'permissions': {'tasks': ['update']},
                }],
            ),
            self._mock_response(status_code=403, ok=False, json_body={'message': 'forbidden'}),
        ]

        client = VikunjaClient('testuser', str(self.config_path))
        with self.assertRaises(AuthError) as context:
            client.get('/tasks/1')

        self.assertIn('specific resource', str(context.exception))

    @patch('api_client.requests.Session.request')
    @patch('api_client.subprocess.run')
    def test_auth_error_reports_scope_mismatch_when_jwt_probe_succeeds(self, mock_subprocess, mock_request):
        """If JWT succeeds but scoped token fails, report likely scope mismatch/back-end behavior."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        mock_request.side_effect = [
            self._mock_response(status_code=401, ok=False, json_body={'message': 'invalid token'}),
            self._mock_response(status_code=200, ok=True, json_body={'message': 'ok'}),
            self._mock_response(status_code=200, ok=True, json_body={'token': 'jwt_123'}),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body={'tasks': {'update': {'path': '/api/v1/tasks/:projecttask', 'method': 'GET'}}},
            ),
            self._mock_response(
                status_code=200,
                ok=True,
                json_body=[{
                    'id': 555,
                    'token_last_eight': 'oken_123',
                    'title': 'testuser-api-token',
                    'permissions': {'tasks': ['update']},
                }],
            ),
            self._mock_response(status_code=200, ok=True, json_body={'id': 1, 'title': 'ok'}),
        ]

        client = VikunjaClient('testuser', str(self.config_path))
        with self.assertRaises(AuthError) as context:
            client.get('/tasks/1')

        msg = str(context.exception).lower()
        self.assertIn('succeeds with username/password login', msg)
        self.assertIn('scope', msg)
    
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
