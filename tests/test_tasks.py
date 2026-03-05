#!/usr/bin/env python3
"""Tests for tasks module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api_client import VikunjaClient, NotFoundError
from tasks import TaskManager


class TestTaskManager(unittest.TestCase):
    """Test cases for TaskManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=VikunjaClient)
        self.task_manager = TaskManager(self.mock_client)
    
    def test_list_tasks_no_filters(self):
        """Test listing tasks without filters."""
        self.mock_client.get.return_value = [
            {'id': 1, 'title': 'Task 1'},
            {'id': 2, 'title': 'Task 2'}
        ]
        
        tasks = self.task_manager.list_tasks()
        
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]['id'], 1)
        self.mock_client.get.assert_called_once_with('/tasks', params={})
    
    def test_list_tasks_with_filters(self):
        """Test listing tasks with filters."""
        self.mock_client.get.return_value = [{'id': 1, 'title': 'Task 1'}]
        
        tasks = self.task_manager.list_tasks(
            project_id=5,
            status='open',
            filter_text='important',
            assignee_id=10
        )
        
        expected_params = {
            'project': 5,
            'status': 'open',
            'search': 'important',
            'assignees': 10
        }
        self.mock_client.get.assert_called_once_with('/tasks', params=expected_params)
    
    def test_get_task(self):
        """Test getting a specific task."""
        self.mock_client.get.return_value = {
            'id': 1,
            'title': 'Test Task',
            'description': 'Description here',
            'done': False
        }
        
        task = self.task_manager.get_task(1)
        
        self.assertEqual(task['id'], 1)
        self.assertEqual(task['title'], 'Test Task')
        self.mock_client.get.assert_called_once_with('/tasks/1')
    
    def test_create_task_requires_project(self):
        """Test creating a task requires project_id on this API version."""
        with self.assertRaises(ValueError):
            self.task_manager.create_task('New Task')
    
    def test_create_task_full(self):
        """Test creating a task with all fields."""
        self.mock_client.put.return_value = {
            'id': 1,
            'title': 'New Task'
        }
        
        task = self.task_manager.create_task(
            title='New Task',
            project_id=5,
            description='Task description',
            due_date='2026-03-10',
            assignee_id=10
        )
        
        expected_data = {
            'title': 'New Task',
            'description': 'Task description',
            'due_date': '2026-03-10',
            'assignees': [{'id': 10}]
        }
        self.mock_client.put.assert_called_once_with('/projects/5/tasks', data=expected_data)
    
    def test_update_task(self):
        """Test updating a task."""
        # Mock the get call for current state
        self.mock_client.get.return_value = {
            'id': 1,
            'title': 'Old Title',
            'description': 'Old Description',
            'due_date': '2026-03-01',
            'done': False,
            'assignees': [{'id': 5}]
        }
        
        self.mock_client.post.return_value = {
            'id': 1,
            'title': 'New Title',
            'done': True
        }
        
        task = self.task_manager.update_task(1, title='New Title', done=True)
        
        self.assertEqual(task['title'], 'New Title')
        
        # Verify the put call includes all fields
        call_args = self.mock_client.post.call_args
        self.assertEqual(call_args[0][0], '/tasks/1')
        self.assertEqual(call_args[1]['data']['title'], 'New Title')
        self.assertEqual(call_args[1]['data']['done'], True)
    
    def test_delete_task(self):
        """Test deleting a task."""
        self.mock_client.delete.return_value = {}
        
        result = self.task_manager.delete_task(1)
        
        self.assertTrue(result)
        self.mock_client.delete.assert_called_once_with('/tasks/1')
    
    def test_add_comment(self):
        """Test adding a comment to a task."""
        self.mock_client.put.return_value = {
            'id': 1,
            'comment': 'Test comment',
            'task_id': 5
        }
        
        comment = self.task_manager.add_comment(5, 'Test comment')
        
        self.assertEqual(comment['comment'], 'Test comment')
        self.mock_client.put.assert_called_once_with(
            '/tasks/5/comments',
            data={'comment': 'Test comment'}
        )
    
    def test_get_comments(self):
        """Test getting comments for a task."""
        self.mock_client.get.return_value = [
            {'id': 1, 'comment': 'First comment'},
            {'id': 2, 'comment': 'Second comment'}
        ]
        
        comments = self.task_manager.get_comments(5)
        
        self.assertEqual(len(comments), 2)
        self.mock_client.get.assert_called_once_with('/tasks/5/comments')
    
    def test_mark_done(self):
        """Test marking a task as done."""
        self.mock_client.get.return_value = {
            'id': 1,
            'title': 'Task',
            'done': False
        }
        
        self.mock_client.post.return_value = {
            'id': 1,
            'title': 'Task',
            'done': True
        }
        
        task = self.task_manager.mark_done(1)
        
        self.assertTrue(task['done'])
    
    def test_mark_undone(self):
        """Test marking a task as not done."""
        self.mock_client.get.return_value = {
            'id': 1,
            'title': 'Task',
            'done': True
        }
        
        self.mock_client.post.return_value = {
            'id': 1,
            'title': 'Task',
            'done': False
        }
        
        task = self.task_manager.mark_undone(1)
        
        self.assertFalse(task['done'])


if __name__ == '__main__':
    unittest.main()
