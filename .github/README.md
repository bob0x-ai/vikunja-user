# Vikunja User Skill

A command-line interface for managing tasks and projects in a Vikunja instance. Designed for OpenClaw agents to interact with Vikunja through a clean, intuitive interface.

## Features

- **Task Management**: Create, update, delete, and list tasks
- **Project Operations**: View projects and their associated tasks
- **Smart Filtering**: Filter tasks by project, status, assignee, or text
- **Comments**: Add and view comments on tasks
- **Auto-Refresh**: Automatic token refresh when authentication expires
- **Multiple Output Formats**: Human-readable and JSON output

## Prerequisites

- Python 3.8 or higher
- Access to a Vikunja instance
- Credentials configured by the admin skill

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd vikunja-user
   ```

2. **Run setup** (one-time):
   ```bash
./scripts/setup.sh
   ```
   This creates a Python virtual environment and installs dependencies.

3. **Configure the skill**:
   Edit `config.yaml`:
   ```yaml
   vikunja:
     base_url: http://your-vikunja-instance:3456/api/v1
   
   paths:
     credentials: ~/.openclaw/credentials/vikunja
  token_refresh: ../vikunja-admin/scripts/token_refresh.sh
   ```

4. **Ensure credentials are configured**:
   The admin skill should have created your credentials in `~/.openclaw/credentials/vikunja`

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

## Usage

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

**Example:**
```bash
./scripts/vikunja.sh task update 123 --done
```

#### Delete Task
```bash
./scripts/vikunja.sh task delete <task_id>
```

#### Add Comment
```bash
./scripts/vikunja.sh task comment <task_id> "Comment text"
```

### Project Commands

```bash
# List all projects
./scripts/vikunja.sh project list

# Show project details
./scripts/vikunja.sh project show <project_id_or_name>

# List tasks in a project
./scripts/vikunja.sh project tasks <project_id_or_name> [--status open|done]
```

## Global Options

```bash
./scripts/vikunja.sh [options] <command>

Options:
  --config, -c     Path to config.yaml
  --format, -f     Output format: human (default) or json
  --username, -u   Username for authentication
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

## Configuration

The skill is configured via `config.yaml`:

```yaml
vikunja:
  base_url: http://127.0.0.1:3456/api/v1

paths:
  credentials: ~/.openclaw/credentials/vikunja
  token_refresh: ../vikunja-admin/scripts/token_refresh.sh

default_format: human
```

### Configuration Options

- **base_url**: URL of your Vikunja API instance
- **credentials**: Path to the users.yaml file containing tokens
- **token_refresh**: Path to the token refresh script (optional)
- **default_format**: Default output format (human or json)

## Authentication

The skill automatically determines which user credentials to use through the following priority:

1. **`--username` flag** - Explicitly specify the username
2. **`OPENCLAW_AGENT_ID` environment variable** - Set by the OpenClaw framework
3. **System username** - Falls back to current OS user

### Username Resolution

```bash
# Auto-detect (recommended for OpenClaw agents)
./scripts/vikunja.sh task list

# Explicit username
./scripts/vikunja.sh --username agent_01 task list

# Manual testing with environment variable
export OPENCLAW_AGENT_ID=agent_01
./scripts/vikunja.sh task list
```

### Credentials Storage

Credentials are stored in `~/.openclaw/credentials/vikunja` (managed by the admin skill):

```yaml
users:
  agent_01:
    user: vikunja_username
    id: 123
    password: secret
    token: api_token_here
    scope: worker
```

This skill only **reads** credentials. Token management is handled by the admin skill.

### Automatic Token Refresh

When an API call returns 401 Unauthorized:
1. If `token_refresh.sh` is configured, it's called automatically
2. If refresh succeeds, the original API call is retried
3. If refresh fails, an error is returned with instructions to contact an administrator

## Error Handling

Exit codes:
- `0` - Success
- `1` - General error (API, auth, not found)
- `2` - Validation error (invalid input)

## Development

### Running Tests

```bash
# Run all tests
./.venv/bin/python -m pytest tests/

# Run specific test file
./.venv/bin/python -m pytest tests/test_tasks.py
```

### Project Structure

```
vikunja-user/
├── scripts/           # Executable scripts
│   ├── vikunja.sh    # Main bash wrapper script
│   └── setup.sh      # One-time setup script
├── src/              # Python source code
│   ├── __init__.py
│   ├── vikunja.py    # Main CLI entry point
│   ├── api_client.py # HTTP client with auth
│   ├── tasks.py      # Task operations
│   ├── projects.py   # Project operations
│   └── config.py     # Configuration management
├── tests/            # Unit tests
│   ├── test_api_client.py
│   ├── test_config.py
│   ├── test_projects.py
│   └── test_tasks.py
├── .github/          # GitHub documentation
│   └── README.md     # Human-facing documentation
├── references/       # Architecture documentation
│   └── AGENTS.md     # Implementation specification
├── scripts/          # Executable scripts and dependencies
│   ├── setup.sh
│   ├── vikunja.sh
│   └── requirements.txt  # Python dependencies
├── config.yaml       # Configuration file
└── SKILL.md          # Agent-facing documentation
```

## Troubleshooting

### "Virtual environment not found"
Run `./scripts/setup.sh` to create the virtual environment.

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

## Security

- Tokens are never logged
- All API calls use HTTPS when base_url uses https://
- Config file should have restricted permissions (600)
- No hardcoded credentials in source code

## Related Projects

- **vikunja-admin**: Admin skill for user and token management
- **OpenClaw**: The agent framework this skill integrates with

## License

[Your License Here]

## References

- [Vikunja API Documentation](https://try.vikunja.io/api/v1/docs)
- [Vikunja Project](https://vikunja.io/)
