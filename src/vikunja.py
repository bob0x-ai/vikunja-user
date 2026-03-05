#!/usr/bin/env python3
"""Main CLI entry point for Vikunja skill."""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

# Add src to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from api_client import VikunjaClient, AuthError, APIError, NotFoundError
from tasks import TaskManager
from projects import ProjectManager
from config import get_config


class OutputFormatter:
    """Handles output formatting (human-readable or JSON)."""
    
    def __init__(self, format_type: str = 'human'):
        """Initialize formatter.
        
        Args:
            format_type: 'human' or 'json'
        """
        self.format_type = format_type
    
    def print_success(self, message: str) -> None:
        """Print success message."""
        if self.format_type == 'json':
            print(json.dumps({'status': 'success', 'message': message}))
        else:
            print(f"OK: {message}")
    
    def print_error(self, message: str) -> None:
        """Print error message."""
        if self.format_type == 'json':
            print(json.dumps({'status': 'error', 'message': message}))
        else:
            print(f"ERROR: {message}", file=sys.stderr)
    
    def print_data(self, data: Any) -> None:
        """Print data (list or dict)."""
        if self.format_type == 'json':
            print(json.dumps(data, indent=2, default=str))
        else:
            self._print_human(data)
    
    def _print_human(self, data: Any, indent: int = 0) -> None:
        """Print data in human-readable format."""
        if isinstance(data, list):
            for item in data:
                self._print_human(item, indent)
                print()
        elif isinstance(data, dict):
            # Format specific data types
            if 'id' in data and 'title' in data:
                # Likely a task or project
                self._print_task_or_project(data)
            elif 'comment' in data:
                # Likely a comment
                self._print_comment(data)
            else:
                # Generic dict
                for key, value in data.items():
                    if value is not None and value != '':
                        print(f"{'  ' * indent}{key.replace('_', ' ').title()}: {value}")
        else:
            print(f"{'  ' * indent}{data}")
    
    def _print_task_or_project(self, data: Dict[str, Any]) -> None:
        """Print task or project in human-readable format."""
        # Determine if it's a task or project
        is_task = 'project_id' in data or 'assignees' in data
        
        if is_task:
            print(f"ID: {data.get('id', 'N/A')}")
            print(f"Title: {data.get('title', 'N/A')}")
            
            if data.get('project'):
                print(f"Project: {data['project'].get('title', data.get('project_id', 'N/A'))}")
            
            if data.get('assignees'):
                assignees = ', '.join(a.get('username', 'N/A') for a in data['assignees'])
                print(f"Assignee: {assignees}")
            
            if data.get('due_date'):
                print(f"Due: {data['due_date']}")
            
            print(f"Status: {'Done' if data.get('done') else 'Open'}")
            
            if data.get('description'):
                print(f"Description: {data['description']}")
        else:
            # Project
            print(f"ID: {data.get('id', 'N/A')}")
            print(f"Title: {data.get('title', 'N/A')}")
            if data.get('description'):
                print(f"Description: {data.get('description')}")
    
    def _print_comment(self, data: Dict[str, Any]) -> None:
        """Print comment in human-readable format."""
        author = data.get('author', {}).get('username', 'Unknown')
        print(f"[{data.get('created', 'Unknown')}] {author}:")
        print(f"  {data.get('comment', '')}")


def parse_date(date_str: str) -> str:
    """Parse and validate date string.
    
    Currently supports ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
    Future: Will support relative dates via dateparser.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Normalized date string
        
    Raises:
        ValueError: If date format is invalid
    """
    # For now, just validate basic ISO format
    # Accept: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    
    if len(date_str) == 10:  # YYYY-MM-DD
        parts = date_str.split('-')
        if len(parts) != 3:
            raise ValueError(f"Invalid date format: {date_str}. Expected: YYYY-MM-DD")
        return date_str
    elif len(date_str) == 19:  # YYYY-MM-DDTHH:MM:SS
        if 'T' not in date_str:
            raise ValueError(f"Invalid date format: {date_str}. Expected: YYYY-MM-DDTHH:MM:SS")
        return date_str
    else:
        raise ValueError(f"Invalid date format: {date_str}. Expected: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")


def resolve_project_id(project_manager: ProjectManager, project_name: str) -> int:
    """Resolve project name to project ID.
    
    Args:
        project_manager: ProjectManager instance
        project_name: Project name or ID
        
    Returns:
        Project ID
        
    Raises:
        ValueError: If project not found
    """
    # Try to parse as ID first
    try:
        return int(project_name)
    except ValueError:
        pass
    
    # Look up by name
    project = project_manager.get_project_by_name(project_name)
    if project:
        return project['id']
    
    raise ValueError(f"Project not found: {project_name}")


def resolve_user_id(client: VikunjaClient, username: str, project_manager: ProjectManager) -> int:
    """Resolve username to user ID.
    
    For now, this is simplified - in a real implementation, we might
    need to query the API for user lookup. Currently assumes the
    username maps to the user's own ID or uses the current user's ID.
    
    Args:
        client: VikunjaClient instance
        username: Username to resolve
        project_manager: ProjectManager instance
        
    Returns:
        User ID
        
    Raises:
        ValueError: If user not found
    """
    # If username matches the current user, return their ID
    if username == client.username:
        if client.user_id:
            return client.user_id
    
    # For now, we can't easily look up other users by username
    # This would require additional API endpoints
    raise ValueError(
        f"Cannot resolve user '{username}'. "
        "Please use the numeric user ID directly."
    )


def handle_task_command(args: argparse.Namespace, formatter: OutputFormatter) -> int:
    """Handle task subcommands.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    client = VikunjaClient(args.username, args.config)
    task_manager = TaskManager(client)
    project_manager = ProjectManager(client)
    
    try:
        if args.task_command == 'list':
            # Resolve filters
            project_id = None
            if args.project:
                project_id = resolve_project_id(project_manager, args.project)
            
            assignee_id = None
            if args.user:
                assignee_id = resolve_user_id(client, args.user, project_manager)
            
            tasks = task_manager.list_tasks(
                project_id=project_id,
                status=args.status,
                filter_text=args.filter,
                assignee_id=assignee_id
            )
            
            if not tasks:
                formatter.print_success("No tasks found matching the criteria")
            else:
                formatter.print_data(tasks)
        
        elif args.task_command == 'show':
            task = task_manager.get_task(args.task_id)
            formatter.print_data(task)
        
        elif args.task_command == 'create':
            # Resolve project
            project_id = None
            if args.project:
                project_id = resolve_project_id(project_manager, args.project)
            
            # Parse due date if provided
            due_date = None
            if args.due:
                due_date = parse_date(args.due)
            
            # Resolve assignee
            assignee_id = None
            if args.assignee:
                assignee_id = resolve_user_id(client, args.assignee, project_manager)
            
            task = task_manager.create_task(
                title=args.title,
                project_id=project_id,
                description=args.description,
                due_date=due_date,
                assignee_id=assignee_id
            )
            
            formatter.print_success(f"Task created with ID {task['id']}")
            formatter.print_data(task)
        
        elif args.task_command == 'update':
            # Parse flags
            done = None
            if args.done:
                done = True
            elif args.undone:
                done = False
            
            # Parse due date if provided
            due_date = None
            if args.due:
                due_date = parse_date(args.due)
            
            # Resolve assignee
            assignee_id = None
            if args.assignee:
                assignee_id = resolve_user_id(client, args.assignee, project_manager)
            
            task = task_manager.update_task(
                task_id=args.task_id,
                title=args.title,
                description=args.description,
                due_date=due_date,
                done=done,
                assignee_id=assignee_id
            )
            
            formatter.print_success(f"Task {args.task_id} updated")
            formatter.print_data(task)
        
        elif args.task_command == 'delete':
            task_manager.delete_task(args.task_id)
            formatter.print_success(f"Task {args.task_id} deleted")
        
        elif args.task_command == 'comment':
            comment = task_manager.add_comment(args.task_id, args.comment)
            formatter.print_success("Comment added")
            formatter.print_data(comment)
        
        elif args.task_command == 'comments':
            comments = task_manager.get_comments(args.task_id)
            if not comments:
                formatter.print_success("No comments on this task")
            else:
                formatter.print_data(comments)
        
        else:
            formatter.print_error(f"Unknown task command: {args.task_command}")
            return 1
    
    except ValueError as e:
        formatter.print_error(f"Invalid input: {str(e)}")
        return 2
    except NotFoundError as e:
        formatter.print_error(f"Not found: {str(e)}")
        return 1
    except AuthError as e:
        formatter.print_error(str(e))
        return 1
    except APIError as e:
        formatter.print_error(str(e))
        return 1
    
    return 0


def handle_project_command(args: argparse.Namespace, formatter: OutputFormatter) -> int:
    """Handle project subcommands.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    client = VikunjaClient(args.username, args.config)
    project_manager = ProjectManager(client)
    
    try:
        if args.project_command == 'list':
            projects = project_manager.list_projects()
            
            if not projects:
                formatter.print_success("No projects found")
            else:
                formatter.print_data(projects)
        
        elif args.project_command == 'show':
            # Try to resolve as ID first, then name
            try:
                project_id = int(args.project_id)
            except ValueError:
                project = project_manager.get_project_by_name(args.project_id)
                if project:
                    project_id = project['id']
                else:
                    raise ValueError(f"Project not found: {args.project_id}")
            
            project = project_manager.get_project(project_id)
            formatter.print_data(project)
        
        elif args.project_command == 'tasks':
            # Try to resolve as ID first, then name
            try:
                project_id = int(args.project_id)
            except ValueError:
                project = project_manager.get_project_by_name(args.project_id)
                if project:
                    project_id = project['id']
                else:
                    raise ValueError(f"Project not found: {args.project_id}")
            
            tasks = project_manager.get_project_tasks(project_id, status=args.status)
            
            if not tasks:
                formatter.print_success("No tasks in this project")
            else:
                formatter.print_data(tasks)
        
        else:
            formatter.print_error(f"Unknown project command: {args.project_command}")
            return 1
    
    except ValueError as e:
        formatter.print_error(f"Invalid input: {str(e)}")
        return 2
    except NotFoundError as e:
        formatter.print_error(f"Not found: {str(e)}")
        return 1
    except AuthError as e:
        formatter.print_error(str(e))
        return 1
    except APIError as e:
        formatter.print_error(str(e))
        return 1
    
    return 0


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog='vikunja',
        description='CLI for Vikunja task management'
    )
    
    parser.add_argument(
        '--config', '-c',
        help='Path to config.yaml (default: ./config.yaml)',
        default=None
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['human', 'json'],
        help='Output format (default: from config or human)',
        default=None
    )
    
    parser.add_argument(
        '--username', '-u',
        help='Username for authentication (default: current user)',
        default=None
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Task commands
    task_parser = subparsers.add_parser('task', help='Task operations')
    task_subparsers = task_parser.add_subparsers(dest='task_command', help='Task commands')
    
    # task list
    task_list = task_subparsers.add_parser('list', help='List tasks')
    task_list.add_argument('--project', '-p', help='Filter by project name or ID')
    task_list.add_argument('--status', '-s', choices=['open', 'done'], help='Filter by status')
    task_list.add_argument('--filter', help='Filter by text in title/description')
    task_list.add_argument('--user', help='Filter by assignee username')
    
    # task show
    task_show = task_subparsers.add_parser('show', help='Show task details')
    task_show.add_argument('task_id', type=int, help='Task ID')
    
    # task create
    task_create = task_subparsers.add_parser('create', help='Create a new task')
    task_create.add_argument('--title', '-t', required=True, help='Task title')
    task_create.add_argument('--project', '-p', help='Project name or ID')
    task_create.add_argument('--description', '-d', help='Task description')
    task_create.add_argument('--due', help='Due date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')
    task_create.add_argument('--assignee', '-a', help='Assignee username')
    
    # task update
    task_update = task_subparsers.add_parser('update', help='Update a task')
    task_update.add_argument('task_id', type=int, help='Task ID')
    task_update.add_argument('--title', '-t', help='New title')
    task_update.add_argument('--description', '-d', help='New description')
    task_update.add_argument('--due', help='New due date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')
    task_update.add_argument('--assignee', '-a', help='New assignee username')
    task_update.add_argument('--done', action='store_true', help='Mark as done')
    task_update.add_argument('--undone', action='store_true', help='Mark as not done')
    
    # task delete
    task_delete = task_subparsers.add_parser('delete', help='Delete a task')
    task_delete.add_argument('task_id', type=int, help='Task ID')
    
    # task comment
    task_comment = task_subparsers.add_parser('comment', help='Add comment to task')
    task_comment.add_argument('task_id', type=int, help='Task ID')
    task_comment.add_argument('comment', help='Comment text')
    
    # task comments (list)
    task_comments = task_subparsers.add_parser('comments', help='List task comments')
    task_comments.add_argument('task_id', type=int, help='Task ID')
    
    # Project commands
    project_parser = subparsers.add_parser('project', help='Project operations')
    project_subparsers = project_parser.add_subparsers(dest='project_command', help='Project commands')
    
    # project list
    project_list = project_subparsers.add_parser('list', help='List projects')
    
    # project show
    project_show = project_subparsers.add_parser('show', help='Show project details')
    project_show.add_argument('project_id', help='Project ID or name')
    
    # project tasks
    project_tasks = project_subparsers.add_parser('tasks', help='List tasks in project')
    project_tasks.add_argument('project_id', help='Project ID or name')
    project_tasks.add_argument('--status', '-s', choices=['open', 'done'], help='Filter by status')
    
    args = parser.parse_args()
    
    # Determine username
    # Priority: 1) --username flag, 2) OPENCLAW_AGENT_ID env var, 3) system username
    if args.username is None:
        # Check for OpenClaw agent ID in environment
        args.username = os.environ.get('OPENCLAW_AGENT_ID')
        
        if args.username is None:
            # Fall back to system username
            import getpass
            args.username = getpass.getuser()
    
    # Determine format
    format_type = args.format
    if format_type is None:
        try:
            config = get_config(args.config)
            format_type = config.default_format
        except:
            format_type = 'human'
    
    formatter = OutputFormatter(format_type)
    
    # Handle commands
    if args.command == 'task':
        if args.task_command is None:
            task_parser.print_help()
            return 1
        return handle_task_command(args, formatter)
    elif args.command == 'project':
        if args.project_command is None:
            project_parser.print_help()
            return 1
        return handle_project_command(args, formatter)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
