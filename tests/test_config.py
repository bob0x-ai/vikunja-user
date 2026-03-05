#!/usr/bin/env python3
"""Tests for config module."""

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import Config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / 'config.yaml'
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_content = """
vikunja:
  base_url: http://localhost:3456/api/v1

paths:
  credentials: ~/.test/credentials
  token_refresh: ~/scripts/refresh.sh

default_format: json
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
        
        config = Config(str(self.config_path))
        
        self.assertEqual(config.base_url, 'http://localhost:3456/api/v1')
        self.assertEqual(config.default_format, 'json')
        self.assertEqual(config.credentials_path, Path.home() / '.test/credentials')
        self.assertEqual(config.token_refresh_path, Path.home() / 'scripts/refresh.sh')
    
    def test_load_default_values(self):
        """Test that default values are used when not specified."""
        config_content = """
vikunja:
  base_url: http://example.com/api
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
        
        config = Config(str(self.config_path))
        
        self.assertEqual(config.base_url, 'http://example.com/api')
        self.assertEqual(config.default_format, 'human')
        self.assertEqual(config.credentials_path, Path.home() / '.openclaw/credentials/vikunja')
        self.assertIsNone(config.token_refresh_path)
    
    def test_missing_config_file(self):
        """Test that FileNotFoundError is raised for missing config."""
        with self.assertRaises(FileNotFoundError):
            Config('/nonexistent/config.yaml')
    
    def test_get_method(self):
        """Test the get method for arbitrary config values."""
        config_content = """
vikunja:
  base_url: http://localhost:3456/api/v1
  timeout: 30

paths:
  credentials: ~/.test/credentials
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
        
        config = Config(str(self.config_path))
        
        self.assertEqual(config.get('vikunja.base_url'), 'http://localhost:3456/api/v1')
        self.assertEqual(config.get('vikunja.timeout'), 30)
        self.assertEqual(config.get('paths.credentials'), '~/.test/credentials')
        self.assertIsNone(config.get('nonexistent.key'))
        self.assertEqual(config.get('nonexistent.key', 'default'), 'default')


if __name__ == '__main__':
    unittest.main()
