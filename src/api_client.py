#!/usr/bin/env python3
"""API client for Vikunja with authentication and automatic token refresh."""

import json
import subprocess
import sys
from typing import Any, Dict, Optional
from pathlib import Path

import requests
import yaml

from config import get_config


class AuthError(Exception):
    """Raised when authentication fails and cannot be recovered."""
    pass


class APIError(Exception):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NotFoundError(APIError):
    """Raised when a requested resource is not found (404)."""
    pass


class VikunjaClient:
    """HTTP client for Vikunja API with automatic token refresh."""
    
    def __init__(self, username: str, config_path: Optional[str] = None):
        """Initialize API client.
        
        Args:
            username: The agent/username to authenticate as
            config_path: Optional path to config.yaml
        """
        self.config = get_config(config_path)
        self.username = username
        self._token: Optional[str] = None
        self._user_id: Optional[int] = None
        self._session = requests.Session()
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """Load credentials from users.yaml file."""
        creds_path = self.config.credentials_path
        
        if not creds_path.exists():
            raise AuthError(
                f"User '{self.username}' not found in configuration. "
                "Please ensure your Vikunja account is properly set up."
            )
        
        with open(creds_path, 'r') as f:
            data = yaml.safe_load(f)
        
        users = data.get('users', {})
        user_data = users.get(self.username)
        
        if not user_data:
            raise AuthError(
                f"User '{self.username}' not found in configuration. "
                "Please ensure your Vikunja account is properly set up."
            )
        
        self._token = user_data.get('token')
        self._user_id = user_data.get('id')
        
        if not self._token:
            raise AuthError(f"No API token found for user '{self.username}'")
    
    def _refresh_token(self) -> bool:
        """Attempt to refresh the authentication token.
        
        Returns:
            True if refresh succeeded, False otherwise.
        """
        refresh_script = self.config.token_refresh_path
        
        if not refresh_script or not refresh_script.exists():
            return False
        
        try:
            result = subprocess.run(
                [str(refresh_script), self.username],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Re-load credentials after successful refresh
                self._load_credentials()
                return True
            else:
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return False
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_on_auth: bool = True
    ) -> Dict[str, Any]:
        """Make an HTTP request to the Vikunja API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            retry_on_auth: Whether to retry on 401 Unauthorized
            
        Returns:
            Parsed JSON response
            
        Raises:
            AuthError: If authentication fails and cannot be refreshed
            NotFoundError: If resource returns 404
            APIError: For other API errors
        """
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30
            )
        except requests.RequestException as e:
            raise APIError(f"Network error: {str(e)}")
        
        # Handle 401 Unauthorized - try token refresh
        if response.status_code == 401 and retry_on_auth:
            if self._refresh_token():
                # Retry the request with new token
                return self._make_request(method, endpoint, data, params, retry_on_auth=False)
            else:
                raise AuthError(
                    "Authentication failed. Your access token has expired. "
                    "Please contact an administrator to refresh your Vikunja access."
                )
        
        # Handle 404 Not Found
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {endpoint}", status_code=404)
        
        # Handle other error status codes
        if not response.ok:
            try:
                error_body = response.json()
                message = error_body.get('message', str(error_body))
            except json.JSONDecodeError:
                message = response.text or f"HTTP {response.status_code}"
            
            raise APIError(
                f"Vikunja API error: {message}",
                status_code=response.status_code,
                response_body=error_body if 'error_body' in locals() else None
            )
        
        # Parse successful response
        try:
            if response.status_code == 204:  # No content
                return {}
            return response.json()
        except json.JSONDecodeError:
            return {}
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a POST request."""
        return self._make_request('POST', endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        return self._make_request('PUT', endpoint, data=data)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        return self._make_request('DELETE', endpoint)
    
    @property
    def user_id(self) -> Optional[int]:
        """Get the user ID for the authenticated user."""
        return self._user_id
