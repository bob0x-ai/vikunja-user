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

**Default behavior**: Shows only tasks assigned to you with status "open" (not done).

```bash
./scripts/vikunja.sh task list [options]

Options:
  --all            Show all tasks (overrides default filters)
  --project, -p    Filter by project name or ID
  --status, -s     Filter by status (open|done)
  --filter         Filter by text in title/description
  --user           Filter by assignee username
```

**Examples:**
```bash
# Default: Show your open tasks
./scripts/vikunja.sh task list

# Show all tasks (for team leads/managers)
./scripts/vikunja.sh task list --all

# Show all open tasks across team
./scripts/vikunja.sh task list --all --status open

# Show your tasks in a specific project
./scripts/vikunja.sh task list --project "Work"

# Show tasks assigned to another user
./scripts/vikunja.sh task list --all --user "john"

# Filter by text
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
  --project, -p    Project name or ID (required on local Vikunja)
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
  --progress       Set progress percentage (0-100)
```

**Examples:**
```bash
./scripts/vikunja.sh task update 123 --title "Updated title"
./scripts/vikunja.sh task update 123 --done
./scripts/vikunja.sh task update 123 --due 2026-04-01 --assignee "john"
./scripts/vikunja.sh task update 123 --progress 50
```

#### Start Task
Start working on a task. Automatically assigns it to you and sets progress to 10%.

```bash
./scripts/vikunja.sh task start <task_id> [--assignee <username>]
```

**Examples:**
```bash
# Start task and assign to yourself
./scripts/vikunja.sh task start 123

# Start task and assign to another user
./scripts/vikunja.sh task start 123 --assignee "john"
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
2. **`AGENT_ID` environment variable**
3. **`agent_id` environment variable**
4. **`OPENCLAW_AGENT_ID` environment variable** (legacy fallback)
5. **System username** (fallback) - Current OS user from `getpass.getuser()`

### Examples

```bash
# Let the skill auto-detect (uses AGENT_ID / agent_id / OPENCLAW_AGENT_ID or system user)
./scripts/vikunja.sh task list

# Explicitly specify username
./scripts/vikunja.sh --username agent_01 task list

# Set environment variable manually (for testing)
export AGENT_ID=agent_01
./scripts/vikunja.sh task list
```

The skill uses this username to look up credentials in `users.yaml` and authenticate with the Vikunja API.

## Global Options

```bash
./scripts/vikunja.sh [global-options] <command>

Options:
  --config, -c     Path to config.yaml
  --format, -f     Output format: json (default) or human
  --username, -u   Username for authentication (overrides auto-detection)
```

**Examples:**
```bash
./scripts/vikunja.sh --format json task list
./scripts/vikunja.sh --username agent_01 project list
./scripts/vikunja.sh --config /path/to/config.yaml task show 123
```

## Output Formats

### JSON (Default)
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

### Human-Readable
```
ID: 123
Title: Buy milk
Project: Shopping
Assignee: Agent_01
Due: 2026-03-05
Status: Open
```

## Error Handling

### Authentication and Access Errors
The skill may return clear auth/access messages (for example invalid/expired token, missing permission, or access denied).  
When this happens, stop and escalate to the administrator instead of attempting in-session troubleshooting.

### Not Found and Validation Errors
For missing resources or invalid input, return the error and correct command arguments (ID/name/date format).

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

# Auth diagnostics behavior for repeated 401s
auth:
  diagnostics_cache_seconds: 60

# Default output format
default_format: json
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
    token_id: 456
    token_last_eight: 12ab34cd
    scope: worker
```

`token_id` and `token_last_eight` are optional but recommended. They allow exact token matching during 401 diagnostics when users have multiple API tokens.

**Note:** This skill only reads credentials. It never writes to this file.

## Authentication Flow

1. Skill reads token from `users.yaml`
2. API calls include token in Authorization header
3. If API returns 401 Unauthorized:
   - If `token_refresh.sh` is configured, it's called automatically
   - If refresh succeeds, the original API call is retried
   - If refresh fails or isn't configured, an error is returned and execution stops

## Security

- Tokens are never logged
- All API calls use HTTPS when base_url uses https://
- Config file should have 600 permissions
- No hardcoded credentials

## Escalation

Escalate to administrator when:
- Auth/access errors occur
- User credentials are missing
- Endpoint permissions appear insufficient for requested action

## References

- [Vikunja API Documentation](https://try.vikunja.io/api/v1/docs)
- Admin Skill: `~/skills-dev/vikunja-admin/`
- Architecture: See `references/AGENTS.md`
