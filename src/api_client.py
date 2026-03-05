#!/usr/bin/env python3
"""API client for Vikunja with authentication and automatic token refresh."""

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
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
        self._password: Optional[str] = None
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
        self._password = user_data.get('password')
        
        if not self._token:
            raise AuthError(f"No API token found for user '{self.username}'")

    @staticmethod
    def _normalize_route_path(path: str) -> str:
        """Normalize API paths to a comparable '/foo/bar' form."""
        if not path:
            return '/'
        clean = path.split('?', 1)[0]
        if clean.startswith('/api/v1'):
            clean = clean[len('/api/v1'):]
        if not clean.startswith('/'):
            clean = '/' + clean
        return clean or '/'

    @staticmethod
    def _route_template_matches(template: str, path: str) -> bool:
        """Match Vikunja route templates like '/tasks/:id' to concrete paths."""
        t = VikunjaClient._normalize_route_path(template)
        p = VikunjaClient._normalize_route_path(path)
        pattern = '^' + re.sub(r':[A-Za-z0-9_]+', r'[^/]+', t) + '$'
        return re.match(pattern, p) is not None

    def _session_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a raw request against the configured Vikunja base URL."""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        return self._session.request(method=method, url=url, timeout=30, **kwargs)

    def _check_token_validity(self) -> bool:
        """Check if current bearer token is valid (independent from route scope)."""
        if not self._token:
            return False
        headers = {
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/json',
        }
        try:
            resp = self._session_request('GET', '/token/test', headers=headers)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _login_for_diagnostics(self) -> Optional[str]:
        """Login with username/password to fetch permission diagnostics."""
        if not self._password:
            return None
        payload = {'username': self.username, 'password': self._password}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        try:
            resp = self._session_request('POST', '/login', headers=headers, json=payload)
        except requests.RequestException:
            return None
        if not resp.ok:
            return None
        try:
            body = resp.json()
        except json.JSONDecodeError:
            return None
        token = body.get('token')
        return token if isinstance(token, str) and token else None

    def _get_routes_with_jwt(self, jwt_token: str) -> Optional[Dict[str, Any]]:
        headers = {'Authorization': f'Bearer {jwt_token}', 'Accept': 'application/json'}
        try:
            resp = self._session_request('GET', '/routes', headers=headers)
        except requests.RequestException:
            return None
        if not resp.ok:
            return None
        try:
            body = resp.json()
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

    def _find_required_permission(
        self, routes: Dict[str, Any], method: str, endpoint: str
    ) -> Optional[Tuple[str, str]]:
        """Find required <group, permission> for the requested endpoint."""
        for group, permission_map in routes.items():
            if not isinstance(permission_map, dict):
                continue
            for permission, detail in permission_map.items():
                if not isinstance(detail, dict):
                    continue
                route_method = detail.get('method')
                route_path = detail.get('path')
                if route_method != method.upper() or not isinstance(route_path, str):
                    continue
                if self._route_template_matches(route_path, endpoint):
                    return group, permission
        return None

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime:
        if not isinstance(value, str):
            return datetime.min
        normalized = value.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.min

    def _select_current_token_candidate(self, tokens: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tokens:
            return None
        # Best match when backend exposes last-eight
        if self._token and len(self._token) >= 8:
            last8 = self._token[-8:]
            for t in tokens:
                if t.get('token_last_eight') == last8:
                    return t
        # Common naming convention from admin skill
        preferred_title = f"{self.username}-api-token"
        for t in tokens:
            if t.get('title') == preferred_title:
                return t
        # Fallback to newest token
        return sorted(tokens, key=lambda t: self._parse_iso_datetime(t.get('created')), reverse=True)[0]

    def _get_token_permissions_with_jwt(self, jwt_token: str) -> Optional[Dict[str, List[str]]]:
        headers = {'Authorization': f'Bearer {jwt_token}', 'Accept': 'application/json'}
        try:
            resp = self._session_request('GET', '/tokens', headers=headers)
        except requests.RequestException:
            return None
        if not resp.ok:
            return None
        try:
            body = resp.json()
        except json.JSONDecodeError:
            return None
        if not isinstance(body, list):
            return None
        tokens = [t for t in body if isinstance(t, dict)]
        token = self._select_current_token_candidate(tokens)
        if not token:
            return None
        perms = token.get('permissions')
        return perms if isinstance(perms, dict) else None

    def _diagnose_unauthorized(self, method: str, endpoint: str) -> str:
        """Build a human-meaningful auth error for misleading 401 responses."""
        token_valid = self._check_token_validity()
        if not token_valid:
            return (
                "Authentication failed: your API token is missing, invalid, or expired. "
                "Refresh or recreate the token."
            )

        # Token is valid, so likely route scope/permission mismatch.
        jwt = self._login_for_diagnostics()
        if not jwt:
            return (
                f"Access denied for {method.upper()} {self._normalize_route_path(endpoint)}. "
                "Your API token appears valid, but permission diagnostics could not run (login failed)."
            )

        routes = self._get_routes_with_jwt(jwt)
        required = self._find_required_permission(routes or {}, method, endpoint) if routes else None
        token_permissions = self._get_token_permissions_with_jwt(jwt)

        if required and token_permissions is not None:
            group, permission = required
            group_permissions = token_permissions.get(group, [])
            if permission not in group_permissions:
                return (
                    f"Access denied for {method.upper()} {self._normalize_route_path(endpoint)}: "
                    f"token is valid but missing permission '{group}.{permission}'."
                )
            return (
                f"Access denied for {method.upper()} {self._normalize_route_path(endpoint)}: "
                "token is valid and route permission exists, but the user likely lacks object-level access."
            )

        if required:
            group, permission = required
            return (
                f"Access denied for {method.upper()} {self._normalize_route_path(endpoint)}: "
                f"token is valid; required permission is '{group}.{permission}', but current token "
                "permissions could not be determined."
            )

        return (
            f"Access denied for {method.upper()} {self._normalize_route_path(endpoint)}: "
            "token is valid, but this endpoint is not available for your token scope."
        )
    
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
    ) -> Any:
        """Make an HTTP request to the Vikunja API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            retry_on_auth: Whether to retry on 401 Unauthorized
            
        Returns:
            Parsed JSON response (dict or list depending on endpoint)
            
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
        
        # Handle 401 Unauthorized.
        # First attempt token refresh once, then always run detailed diagnostics.
        if response.status_code == 401:
            if retry_on_auth and self._refresh_token():
                # Retry the request with a new token exactly once.
                return self._make_request(method, endpoint, data, params, retry_on_auth=False)
            raise AuthError(self._diagnose_unauthorized(method, endpoint))
        
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
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request."""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make a POST request."""
        return self._make_request('POST', endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make a PUT request."""
        return self._make_request('PUT', endpoint, data=data)
    
    def delete(self, endpoint: str) -> Any:
        """Make a DELETE request."""
        return self._make_request('DELETE', endpoint)
    
    @property
    def user_id(self) -> Optional[int]:
        """Get the user ID for the authenticated user."""
        return self._user_id
