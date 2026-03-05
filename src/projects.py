#!/usr/bin/env python3
"""Project operations for Vikunja API."""

from typing import Any, Dict, List, Optional
from api_client import VikunjaClient, NotFoundError


class ProjectManager:
    """Manages project-related operations."""
    
    def __init__(self, client: VikunjaClient):
        """Initialize with API client.
        
        Args:
            client: Authenticated VikunjaClient instance
        """
        self.client = client
    
    def list_projects(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all projects accessible to the user.
        
        Args:
            search: Optional search text to filter projects
            
        Returns:
            List of project dictionaries
        """
        params: Dict[str, Any] = {}
        
        if search:
            params['search'] = search
        
        response = self.client.get('/projects', params=params)
        return response.get('data', [])
    
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific project.
        
        Args:
            project_id: The project ID
            
        Returns:
            Project dictionary with full details
            
        Raises:
            NotFoundError: If project doesn't exist
        """
        return self.client.get(f'/projects/{project_id}')
    
    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a project by its title/name.
        
        Args:
            name: Project name to search for
            
        Returns:
            Project dictionary if found, None otherwise
        """
        projects = self.list_projects(search=name)
        
        # Look for exact match first, then partial match
        exact_match = None
        partial_match = None
        
        name_lower = name.lower()
        
        for project in projects:
            project_title = project.get('title', '').lower()
            
            if project_title == name_lower:
                exact_match = project
                break
            elif name_lower in project_title and partial_match is None:
                partial_match = project
        
        return exact_match or partial_match
    
    def get_project_tasks(
        self,
        project_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all tasks in a project.
        
        Args:
            project_id: The project ID
            status: Filter by status ('open' or 'done')
            
        Returns:
            List of task dictionaries
            
        Raises:
            NotFoundError: If project doesn't exist
        """
        params: Dict[str, Any] = {'project': project_id}
        
        if status:
            params['status'] = status
        
        response = self.client.get('/tasks', params=params)
        return response.get('data', [])
    
    def get_task_buckets(self, project_id: int) -> List[Dict[str, Any]]:
        """Get kanban buckets for a project.
        
        Args:
            project_id: The project ID
            
        Returns:
            List of bucket dictionaries
            
        Raises:
            NotFoundError: If project doesn't exist
        """
        response = self.client.get(f'/projects/{project_id}/buckets')
        return response.get('data', [])
    
    def get_labels(self, project_id: int) -> List[Dict[str, Any]]:
        """Get labels available in a project.
        
        Args:
            project_id: The project ID
            
        Returns:
            List of label dictionaries
            
        Raises:
            NotFoundError: If project doesn't exist
        """
        response = self.client.get(f'/projects/{project_id}/labels')
        return response.get('data', [])
