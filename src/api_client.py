#!/usr/bin/env python3
"""API client for Vikunja with authentication and automatic token refresh."""

import json
import re
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
        self._token_id: Optional[int] = None
        self._token_last_eight: Optional[str] = None
        self._session = requests.Session()
        self._diagnostic_cache_ttl_seconds = self._parse_positive_int(
            self.config.get('auth.diagnostics_cache_seconds', 60), 60
        )
        self._diagnostic_cache: Dict[str, Tuple[float, str]] = {}
        self._diagnostic_context_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._load_credentials()

    @staticmethod
    def _parse_positive_int(value: Any, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_last_eight(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        return candidate if candidate else None

    def _token_fingerprint(self) -> str:
        if self._token_id is not None:
            return f"id:{self._token_id}"
        if self._token_last_eight:
            return f"last8:{self._token_last_eight}"
        if self._token and len(self._token) >= 8:
            return f"last8:{self._token[-8:]}"
        return "unknown"

    def _clear_auth_diagnostics_cache(self) -> None:
        self._diagnostic_cache.clear()
        self._diagnostic_context_cache.clear()
    
    def _load_credentials(self) -> None:
        """Load credentials from users.yaml file."""
        previous_fingerprint = self._token_fingerprint()
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
        raw_token_id = user_data.get('token_id')
        raw_token_last_eight = user_data.get('token_last_eight')
        
        if not self._token:
            raise AuthError(f"No API token found for user '{self.username}'")

        self._token_id = None
        if raw_token_id is not None and raw_token_id != "":
            try:
                self._token_id = int(raw_token_id)
            except (TypeError, ValueError):
                raise AuthError(
                    f"Invalid token_id for user '{self.username}': {raw_token_id!r}. "
                    "Expected integer."
                )

        self._token_last_eight = self._normalize_last_eight(raw_token_last_eight)
        if not self._token_last_eight and len(self._token) >= 8:
            self._token_last_eight = self._token[-8:]
        if self._token_last_eight and not self._token.endswith(self._token_last_eight):
            raise AuthError(
                f"Credentials mismatch for user '{self.username}': token_last_eight "
                "does not match token value."
            )

        if previous_fingerprint != self._token_fingerprint():
            self._clear_auth_diagnostics_cache()

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

    def _select_current_token_candidate(
        self, tokens: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not tokens:
            return None, "no tokens were returned by /tokens for this user."

        # Exact match by token id when available.
        if self._token_id is not None:
            matches = [t for t in tokens if t.get('id') == self._token_id]
            if len(matches) == 1:
                return matches[0], None
            if len(matches) > 1:
                return None, (
                    f"multiple tokens matched configured token_id '{self._token_id}'."
                )
            return None, f"configured token_id '{self._token_id}' was not found in /tokens."

        # Deterministic match by token suffix when available.
        if self._token_last_eight:
            matches = [t for t in tokens if t.get('token_last_eight') == self._token_last_eight]
            if len(matches) == 1:
                return matches[0], None
            if len(matches) > 1:
                return None, (
                    f"multiple tokens matched configured token_last_eight '{self._token_last_eight}'. "
                    "Set token_id in users.yaml to disambiguate."
                )
            return None, (
                f"configured token_last_eight '{self._token_last_eight}' was not found in /tokens."
            )

        # Backward-compatibility fallback when metadata is missing.
        if self._token and len(self._token) >= 8:
            last8 = self._token[-8:]
            matches = [t for t in tokens if t.get('token_last_eight') == last8]
            if len(matches) == 1:
                return matches[0], (
                    "token metadata missing in users.yaml; matched by token suffix from token value."
                )
            if len(matches) > 1:
                return None, (
                    f"multiple tokens matched suffix '{last8}'. Add token_id/token_last_eight "
                    "to users.yaml."
                )
        # Common naming convention from admin skill
        preferred_title = f"{self.username}-api-token"
        title_matches = [t for t in tokens if t.get('title') == preferred_title]
        if len(title_matches) == 1:
            return title_matches[0], (
                "token metadata missing in users.yaml; matched by token title convention."
            )
        if len(title_matches) > 1:
            return sorted(
                title_matches, key=lambda t: self._parse_iso_datetime(t.get('created')), reverse=True
            )[0], (
                "multiple tokens matched title convention; selected newest candidate. "
                "Add token_id/token_last_eight to users.yaml for exact matching."
            )
        # Fallback to newest token
        return sorted(tokens, key=lambda t: self._parse_iso_datetime(t.get('created')), reverse=True)[0], (
            "token metadata missing in users.yaml; selected newest token as fallback."
        )

    def _get_token_permissions_with_jwt(
        self, jwt_token: str
    ) -> Tuple[Optional[Dict[str, List[str]]], Optional[str]]:
        headers = {'Authorization': f'Bearer {jwt_token}', 'Accept': 'application/json'}
        try:
            resp = self._session_request('GET', '/tokens', headers=headers)
        except requests.RequestException:
            return None, "failed to fetch /tokens (network error)."
        if not resp.ok:
            return None, f"failed to fetch /tokens (HTTP {resp.status_code})."
        try:
            body = resp.json()
        except json.JSONDecodeError:
            return None, "failed to parse /tokens response."
        if not isinstance(body, list):
            return None, "unexpected /tokens payload type."
        tokens = [t for t in body if isinstance(t, dict)]
        token, note = self._select_current_token_candidate(tokens)
        if not token:
            return None, note or "could not identify current API token in /tokens."
        perms = token.get('permissions')
        if isinstance(perms, dict):
            return perms, note
        return None, note or "selected token has no permissions payload."

    def _probe_endpoint_with_jwt(
        self, jwt_token: str, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Optional[int]:
        safe_probe_methods = {'GET', 'HEAD', 'OPTIONS'}
        probe_method = method.upper()
        if probe_method not in safe_probe_methods:
            return None
        headers = {'Authorization': f'Bearer {jwt_token}', 'Accept': 'application/json'}
        try:
            resp = self._session_request(probe_method, endpoint, headers=headers, params=params)
        except requests.RequestException:
            return None
        return resp.status_code

    @staticmethod
    def _extract_response_message(response: Optional[requests.Response]) -> Optional[str]:
        if response is None:
            return None
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            return response.text.strip() or None
        if isinstance(body, dict):
            message = body.get('message')
            if isinstance(message, str) and message.strip():
                return message.strip()
            return str(body)
        return str(body)

    def _diagnostic_cache_key(self, method: str, endpoint: str, params: Optional[Dict] = None) -> str:
        if params:
            serialized = json.dumps(params, sort_keys=True, default=str)
        else:
            serialized = ""
        return (
            f"{self._token_fingerprint()}|{method.upper()}|"
            f"{self._normalize_route_path(endpoint)}|{serialized}"
        )

    def _get_cached_diagnostic_message(self, cache_key: str) -> Optional[str]:
        cached = self._diagnostic_cache.get(cache_key)
        if not cached:
            return None
        expires_at, message = cached
        if expires_at <= time.monotonic():
            self._diagnostic_cache.pop(cache_key, None)
            return None
        return message

    def _set_cached_diagnostic_message(self, cache_key: str, message: str) -> None:
        expires_at = time.monotonic() + self._diagnostic_cache_ttl_seconds
        self._diagnostic_cache[cache_key] = (expires_at, message)

    def _get_diagnostic_context(self, jwt_token: str) -> Dict[str, Any]:
        cache_key = self._token_fingerprint()
        cached = self._diagnostic_context_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        routes = self._get_routes_with_jwt(jwt_token)
        token_permissions, token_note = self._get_token_permissions_with_jwt(jwt_token)
        context = {
            'routes': routes,
            'token_permissions': token_permissions,
            'token_selection_note': token_note,
        }
        expires_at = time.monotonic() + self._diagnostic_cache_ttl_seconds
        self._diagnostic_context_cache[cache_key] = (expires_at, context)
        return context

    def _diagnose_unauthorized(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        response: Optional[requests.Response] = None,
    ) -> str:
        """Build a human-meaningful auth error for misleading 401 responses."""
        cache_key = self._diagnostic_cache_key(method, endpoint, params)
        cached_message = self._get_cached_diagnostic_message(cache_key)
        if cached_message:
            return cached_message

        backend_message = self._extract_response_message(response)
        normalized_path = self._normalize_route_path(endpoint)

        token_valid = self._check_token_validity()
        if not token_valid:
            message = (
                "Authentication failed: your API token is missing, invalid, or expired. "
                "Refresh or recreate the token."
            )
            if backend_message:
                message += f" Backend response: {backend_message}"
            self._set_cached_diagnostic_message(cache_key, message)
            return message

        # Token is valid, so likely route scope/permission mismatch.
        jwt = self._login_for_diagnostics()
        if not jwt:
            message = (
                f"Access denied for {method.upper()} {normalized_path}. "
                "Your API token appears valid, but permission diagnostics could not run (login failed)."
            )
            if backend_message:
                message += f" Backend response: {backend_message}"
            self._set_cached_diagnostic_message(cache_key, message)
            return message

        context = self._get_diagnostic_context(jwt)
        routes = context.get('routes')
        token_selection_note = context.get('token_selection_note')
        required = self._find_required_permission(routes or {}, method, endpoint) if routes else None
        token_permissions = context.get('token_permissions')

        message = ""
        if required and token_permissions is not None:
            group, permission = required
            group_permissions = token_permissions.get(group, [])
            if permission not in group_permissions:
                message = (
                    f"Access denied for {method.upper()} {normalized_path}: "
                    f"token is valid but missing permission '{group}.{permission}'."
                )
            else:
                jwt_probe_status = self._probe_endpoint_with_jwt(jwt, method, endpoint, params=params)
                if jwt_probe_status is not None and 200 <= jwt_probe_status < 300:
                    message = (
                        f"Access denied for {method.upper()} {normalized_path}: token is valid and includes "
                        f"'{group}.{permission}', and the same request succeeds with username/password login. "
                        "This points to token-scope mismatch, stale token metadata, or backend scoped-token behavior."
                    )
                elif jwt_probe_status in (401, 403):
                    message = (
                        f"Access denied for {method.upper()} {normalized_path}: token includes "
                        f"'{group}.{permission}', but access is denied for this specific resource "
                        "(project/task ACL or ownership restriction)."
                    )
                elif jwt_probe_status == 404:
                    message = (
                        f"Access denied for {method.upper()} {normalized_path}: token includes "
                        f"'{group}.{permission}', but the resource is missing or hidden by access rules."
                    )
                else:
                    message = (
                        f"Access denied for {method.upper()} {normalized_path}: token includes "
                        f"'{group}.{permission}', but request is still denied (likely object-level ACL)."
                    )
        elif required:
            group, permission = required
            message = (
                f"Access denied for {method.upper()} {normalized_path}: "
                f"token is valid; required permission is '{group}.{permission}', but current token "
                "permissions could not be determined."
            )
        elif routes is not None:
            message = (
                f"Access denied for {method.upper()} {normalized_path}: token is valid, but this endpoint "
                "did not match any route permission from /routes."
            )
        else:
            message = (
                f"Access denied for {method.upper()} {normalized_path}: token is valid, but route "
                "information could not be retrieved."
            )

        if token_selection_note:
            message += f" Token selection note: {token_selection_note}"
        if backend_message:
            message += f" Backend response: {backend_message}"

        self._set_cached_diagnostic_message(cache_key, message)
        return message
    
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
            raise AuthError(self._diagnose_unauthorized(method, endpoint, params=params, response=response))
        
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
