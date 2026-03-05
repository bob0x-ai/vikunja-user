#!/usr/bin/env python3
"""Task operations for Vikunja API."""

from typing import Any, Dict, List, Optional
from .api_client import VikunjaClient, NotFoundError


class TaskManager:
    """Manages task-related operations."""
    
    def __init__(self, client: VikunjaClient):
        """Initialize with API client.
        
        Args:
            client: Authenticated VikunjaClient instance
        """
        self.client = client
    
    def list_tasks(
        self,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        filter_text: Optional[str] = None,
        assignee_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filters.
        
        Args:
            project_id: Filter by project ID
            status: Filter by status ('open' or 'done')
            filter_text: Filter by task title/description
            assignee_id: Filter by assignee user ID
            
        Returns:
            List of task dictionaries
        """
        params: Dict[str, Any] = {}
        
        if project_id:
            params['project'] = project_id
        
        if status:
            params['status'] = status
        
        if filter_text:
            params['search'] = filter_text
        
        if assignee_id:
            params['assignees'] = assignee_id
        
        response = self.client.get('/tasks', params=params)
        return response.get('data', [])
    
    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific task.
        
        Args:
            task_id: The task ID
            
        Returns:
            Task dictionary with full details
            
        Raises:
            NotFoundError: If task doesn't exist
        """
        return self.client.get(f'/tasks/{task_id}')
    
    def create_task(
        self,
        title: str,
        project_id: Optional[int] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        assignee_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new task.
        
        Args:
            title: Task title (required)
            project_id: Project ID to create task in
            description: Task description
            due_date: Due date in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            assignee_id: User ID to assign the task to
            
        Returns:
            Created task dictionary
        """
        data: Dict[str, Any] = {'title': title}
        
        if project_id:
            data['project_id'] = project_id
        
        if description:
            data['description'] = description
        
        if due_date:
            data['due_date'] = due_date
        
        if assignee_id:
            data['assignees'] = [{'id': assignee_id}]
        
        return self.client.post('/tasks', data=data)
    
    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        done: Optional[bool] = None,
        assignee_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update an existing task.
        
        Args:
            task_id: The task ID to update
            title: New title
            description: New description
            due_date: New due date in ISO 8601 format
            done: Mark as done (True) or undone (False)
            assignee_id: New assignee user ID (or None to remove assignee)
            
        Returns:
            Updated task dictionary
            
        Raises:
            NotFoundError: If task doesn't exist
        """
        # First get current task state
        task = self.get_task(task_id)
        
        data: Dict[str, Any] = {}
        
        if title is not None:
            data['title'] = title
        else:
            data['title'] = task.get('title', '')
        
        if description is not None:
            data['description'] = description
        else:
            data['description'] = task.get('description', '')
        
        if due_date is not None:
            data['due_date'] = due_date
        else:
            data['due_date'] = task.get('due_date')
        
        if done is not None:
            data['done'] = done
        else:
            data['done'] = task.get('done', False)
        
        if assignee_id is not None:
            data['assignees'] = [{'id': assignee_id}]
        else:
            # Keep existing assignees if not specified
            current_assignees = task.get('assignees', [])
            if current_assignees:
                data['assignees'] = [{'id': a['id']} for a in current_assignees]
        
        return self.client.put(f'/tasks/{task_id}', data=data)
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task.
        
        Args:
            task_id: The task ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If task doesn't exist
        """
        self.client.delete(f'/tasks/{task_id}')
        return True
    
    def add_comment(self, task_id: int, comment: str) -> Dict[str, Any]:
        """Add a comment to a task.
        
        Args:
            task_id: The task ID
            comment: Comment text
            
        Returns:
            Created comment dictionary
            
        Raises:
            NotFoundError: If task doesn't exist
        """
        data = {'comment': comment}
        return self.client.post(f'/tasks/{task_id}/comments', data=data)
    
    def get_comments(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all comments for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of comment dictionaries
            
        Raises:
            NotFoundError: If task doesn't exist
        """
        response = self.client.get(f'/tasks/{task_id}/comments')
        return response.get('data', [])
    
    def mark_done(self, task_id: int) -> Dict[str, Any]:
        """Mark a task as done.
        
        Args:
            task_id: The task ID
            
        Returns:
            Updated task dictionary
        """
        return self.update_task(task_id, done=True)
    
    def mark_undone(self, task_id: int) -> Dict[str, Any]:
        """Mark a task as not done.
        
        Args:
            task_id: The task ID
            
        Returns:
            Updated task dictionary
        """
        return self.update_task(task_id, done=False)
