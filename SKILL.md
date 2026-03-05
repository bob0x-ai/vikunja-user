---
name: vikunja-user
description: Interact with Vikunja task management via CLI. Use when user says "create task", "list my tasks", "show project", "update task", "delete task", "add comment", or needs project/task management operations.
---

# Vikunja User Skill

A command-line interface for managing tasks and projects in a Vikunja instance.

## Overview

This skill provides OpenClaw agents with the ability to:
- Create, update, and delete tasks
- List and filter tasks by project, status, or assignee
- View task details and comments
- Manage project information
- Automatically handle authentication token refresh

## Quick Start

```bash
# List your tasks
./scripts/vikunja.sh task list

# Create a new task
./scripts/vikunja.sh task create --title "Buy groceries" --due 2026-03-10

# Show task details
./scripts/vikunja.sh task show 123

# Mark task as done
./scripts/vikunja.sh task update 123 --done

# List projects
./scripts/vikunja.sh project list
```

## Commands

### Task Commands

#### List Tasks
```bash
./scripts/vikunja.sh task list [options]

Options:
  --project, -p    Filter by project name or ID
  --status, -s     Filter by status (open|done)
  --filter         Filter by text in title/description
  --user           Filter by assignee username
```

**Examples:**
```bash
./scripts/vikunja.sh task list --status open
./scripts/vikunja.sh task list --project "Work" --status open
./scripts/vikunja.sh task list --filter "urgent"
```

#### Show Task Details
```bash
./scripts/vikunja.sh task show <task_id>
```

**Example:**
```bash
./scripts/vikunja.sh task show 123
```

#### Create Task
```bash
./scripts/vikunja.sh task create --title "Task title" [options]

Options:
  --title, -t      Task title (required)
  --project, -p    Project name or ID
  --description    Task description
  --due            Due date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
  --assignee, -a   Assignee username
```

**Examples:**
```bash
./scripts/vikunja.sh task create --title "Review PR" --project "Development"
./scripts/vikunja.sh task create --title "Call client" --due 2026-03-15 --description "Discuss requirements"
```

#### Update Task
```bash
./scripts/vikunja.sh task update <task_id> [options]

Options:
  --title, -t      New title
  --description    New description
  --due            New due date
  --assignee, -a   New assignee username
  --done           Mark as done
  --undone         Mark as not done
```

**Examples:**
```bash
./scripts/vikunja.sh task update 123 --title "Updated title"
./scripts/vikunja.sh task update 123 --done
./scripts/vikunja.sh task update 123 --due 2026-04-01 --assignee "john"
```

#### Delete Task
```bash
./scripts/vikunja.sh task delete <task_id>
```

**Example:**
```bash
./scripts/vikunja.sh task delete 123
```

#### Add Comment
```bash
./scripts/vikunja.sh task comment <task_id> "Comment text"
```

**Example:**
```bash
./scripts/vikunja.sh task comment 123 "Waiting for feedback from team"
```

#### List Comments
```bash
./scripts/vikunja.sh task comments <task_id>
```

**Example:**
```bash
./scripts/vikunja.sh task comments 123
```

### Project Commands

#### List Projects
```bash
./scripts/vikunja.sh project list
```

#### Show Project Details
```bash
./scripts/vikunja.sh project show <project_id_or_name>
```

**Examples:**
```bash
./scripts/vikunja.sh project show 5
./scripts/vikunja.sh project show "Work Projects"
```

#### List Project Tasks
```bash
./scripts/vikunja.sh project tasks <project_id_or_name> [options]

Options:
  --status, -s  Filter by status (open|done)
```

**Examples:**
```bash
./scripts/vikunja.sh project tasks "Work Projects"
./scripts/vikunja.sh project tasks 5 --status open
```

## Authentication

The skill automatically determines the username to use for authentication with the following priority:

1. **`--username` flag** (highest priority) - Explicitly specify the username
2. **`OPENCLAW_AGENT_ID` environment variable** - Automatically set by OpenClaw framework
3. **System username** (fallback) - Current OS user from `getpass.getuser()`

### Examples

```bash
# Let the skill auto-detect (uses OPENCLAW_AGENT_ID or system user)
./scripts/vikunja.sh task list

# Explicitly specify username
./scripts/vikunja.sh --username agent_01 task list

# Set environment variable manually (for testing)
export OPENCLAW_AGENT_ID=agent_01
./scripts/vikunja.sh task list
```

The skill uses this username to look up credentials in `users.yaml` and authenticate with the Vikunja API.

## Global Options

```bash
./scripts/vikunja.sh [global-options] <command>

Options:
  --config, -c     Path to config.yaml
  --format, -f     Output format: human (default) or json
  --username, -u   Username for authentication (overrides auto-detection)
```

**Examples:**
```bash
./scripts/vikunja.sh --format json task list
./scripts/vikunja.sh --username agent_01 project list
./scripts/vikunja.sh --config /path/to/config.yaml task show 123
```

## Output Formats

### Human-Readable (Default)
```
ID: 123
Title: Buy milk
Project: Shopping
Assignee: Agent_01
Due: 2026-03-05
Status: Open
```

### JSON
```bash
./scripts/vikunja.sh --format json task show 123
```

Output:
```json
{
  "id": 123,
  "title": "Buy milk",
  "project_id": 5,
  "assignees": [{"id": 1, "username": "Agent_01"}],
  "due_date": "2026-03-05T00:00:00Z",
  "done": false
}
```

## Error Handling

### Authentication Errors
If your token has expired and automatic refresh fails:
```
ERROR: Authentication failed. Your access token has expired.
Please contact an administrator to refresh your Vikunja access.
```

**Resolution:** Contact your administrator to refresh your access token.

### Not Found Errors
```
ERROR: Not found: Resource not found: /tasks/999
```

**Resolution:** Verify the task/project ID exists.

### Validation Errors
```
ERROR: Invalid input: Project not found: MyProject
```

**Resolution:** Check the project name or use the project ID.

### Exit Codes
- `0` - Success
- `1` - General error (API, auth, not found)
- `2` - Validation error (invalid input)

## Configuration

### config.yaml

```yaml
vikunja:
  base_url: http://127.0.0.1:3456/api/v1

paths:
  # Path to admin skill's users.yaml
  credentials: ~/.openclaw/credentials/vikunja
  
  # Path to token refresh script (optional)
  # Relative path works in both dev and production:
  # - dev: ~/skills-dev/vikunja-user/../vikunja-admin/scripts/
  # - prod: ~/.openclaw/skills/vikunja-user/../vikunja-admin/scripts/
  token_refresh: ../vikunja-admin/scripts/token_refresh.sh

# Default output format
default_format: human
```

### Credentials

Credentials are managed by the admin skill in `users.yaml`:

```yaml
users:
  agent_01:
    user: vikunja_username
    id: 123
    password: secret
    token: api_token_here
    scope: worker
```

**Note:** This skill only reads credentials. It never writes to this file.

## Authentication Flow

1. Skill reads token from `users.yaml`
2. API calls include token in Authorization header
3. If API returns 401 Unauthorized:
   - If `token_refresh.sh` is configured, it's called automatically
   - If refresh succeeds, the original API call is retried
   - If refresh fails or isn't configured, an error is returned

## Security

- Tokens are never logged
- All API calls use HTTPS when base_url uses https://
- Config file should have 600 permissions
- No hardcoded credentials

## Troubleshooting

### "User not found in configuration"
Contact your administrator to set up your Vikunja credentials.

### "Project not found"
Use project ID instead of name, or verify the project name:
```bash
./scripts/vikunja.sh project list
```

### Date Format Issues
Dates must be in ISO 8601 format:
- `YYYY-MM-DD` (e.g., `2026-03-05`)
- `YYYY-MM-DDTHH:MM:SS` (e.g., `2026-03-05T14:30:00`)

## References

- [Vikunja API Documentation](https://try.vikunja.io/api/v1/docs)
- Admin Skill: `~/skills-dev/vikunja-admin/`
- Architecture: See `references/AGENTS.md`
