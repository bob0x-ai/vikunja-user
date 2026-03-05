#!/usr/bin/env python3
"""Configuration management for Vikunja skill."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Manages skill configuration from config.yaml file."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to config.yaml. If None, uses default location.
        """
        if config_path is None:
            # Default to config.yaml in skill root
            script_dir = Path(__file__).parent.parent
            config_path = script_dir / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}
    
    @property
    def base_url(self) -> str:
        """Get Vikunja API base URL."""
        return self._config.get('vikunja', {}).get('base_url', 'http://127.0.0.1:3456/api/v1')
    
    @property
    def credentials_path(self) -> Path:
        """Get path to credentials file (users.yaml).

        Supports both:
        - A direct file path to users.yaml
        - A directory containing users.yaml
        """
        path = self._config.get('paths', {}).get('credentials', '~/.openclaw/credentials/vikunja')
        candidate = Path(path).expanduser()
        if candidate.is_dir() or candidate.suffix == '':
            return candidate / 'users.yaml'
        return candidate
    
    @property
    def token_refresh_path(self) -> Optional[Path]:
        """Get path to token refresh script, if configured."""
        path = self._config.get('paths', {}).get('token_refresh')
        if path:
            p = Path(path).expanduser()
            if not p.is_absolute():
                p = (self.config_path.parent / p).resolve()
            return p
        return None
    
    @property
    def default_format(self) -> str:
        """Get default output format."""
        return self._config.get('default_format', 'json')
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get arbitrary config value by key path (e.g., 'vikunja.base_url')."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get or create global config instance.
    
    Args:
        config_path: Path to config.yaml. Uses default if not specified.
        
    Returns:
        Config instance.
    """
    global _config
    if _config is None or config_path is not None:
        _config = Config(config_path)
    return _config
