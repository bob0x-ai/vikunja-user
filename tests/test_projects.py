#!/usr/bin/env python3
"""Tests for projects module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api_client import VikunjaClient, NotFoundError
from projects import ProjectManager


class TestProjectManager(unittest.TestCase):
    """Test cases for ProjectManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=VikunjaClient)
        self.project_manager = ProjectManager(self.mock_client)
    
    def test_list_projects(self):
        """Test listing all projects."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'Project 1'},
                {'id': 2, 'title': 'Project 2'}
            ]
        }
        
        projects = self.project_manager.list_projects()
        
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]['id'], 1)
        self.mock_client.get.assert_called_once_with('/projects', params={})
    
    def test_list_projects_with_search(self):
        """Test listing projects with search filter."""
        self.mock_client.get.return_value = {
            'data': [{'id': 1, 'title': 'Test Project'}]
        }
        
        projects = self.project_manager.list_projects(search='test')
        
        self.assertEqual(len(projects), 1)
        self.mock_client.get.assert_called_once_with('/projects', params={'search': 'test'})
    
    def test_get_project(self):
        """Test getting a specific project."""
        self.mock_client.get.return_value = {
            'id': 5,
            'title': 'My Project',
            'description': 'Project description'
        }
        
        project = self.project_manager.get_project(5)
        
        self.assertEqual(project['id'], 5)
        self.assertEqual(project['title'], 'My Project')
        self.mock_client.get.assert_called_once_with('/projects/5')
    
    def test_get_project_by_name_exact_match(self):
        """Test finding project by exact name match."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'Work Project'},
                {'id': 2, 'title': 'Personal Project'}
            ]
        }
        
        project = self.project_manager.get_project_by_name('Work Project')
        
        self.assertIsNotNone(project)
        self.assertEqual(project['id'], 1)
    
    def test_get_project_by_name_partial_match(self):
        """Test finding project by partial name match."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'My Work Project'},
                {'id': 2, 'title': 'Another Project'}
            ]
        }
        
        project = self.project_manager.get_project_by_name('Work')
        
        self.assertIsNotNone(project)
        self.assertEqual(project['id'], 1)
    
    def test_get_project_by_name_not_found(self):
        """Test when project name is not found."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'Project A'}
            ]
        }
        
        project = self.project_manager.get_project_by_name('Nonexistent')
        
        self.assertIsNone(project)
    
    def test_get_project_tasks(self):
        """Test getting tasks in a project."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'Task 1', 'project_id': 5},
                {'id': 2, 'title': 'Task 2', 'project_id': 5}
            ]
        }
        
        tasks = self.project_manager.get_project_tasks(5)
        
        self.assertEqual(len(tasks), 2)
        self.mock_client.get.assert_called_once_with('/tasks', params={'project': 5})
    
    def test_get_project_tasks_with_status_filter(self):
        """Test getting tasks with status filter."""
        self.mock_client.get.return_value = {
            'data': [{'id': 1, 'title': 'Open Task', 'done': False}]
        }
        
        tasks = self.project_manager.get_project_tasks(5, status='open')
        
        self.assertEqual(len(tasks), 1)
        self.mock_client.get.assert_called_once_with(
            '/tasks',
            params={'project': 5, 'status': 'open'}
        )
    
    def test_get_task_buckets(self):
        """Test getting kanban buckets for a project."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'To Do'},
                {'id': 2, 'title': 'In Progress'},
                {'id': 3, 'title': 'Done'}
            ]
        }
        
        buckets = self.project_manager.get_task_buckets(5)
        
        self.assertEqual(len(buckets), 3)
        self.mock_client.get.assert_called_once_with('/projects/5/buckets')
    
    def test_get_labels(self):
        """Test getting labels for a project."""
        self.mock_client.get.return_value = {
            'data': [
                {'id': 1, 'title': 'Bug', 'color': '#ff0000'},
                {'id': 2, 'title': 'Feature', 'color': '#00ff00'}
            ]
        }
        
        labels = self.project_manager.get_labels(5)
        
        self.assertEqual(len(labels), 2)
        self.mock_client.get.assert_called_once_with('/projects/5/labels')


if __name__ == '__main__':
    unittest.main()
