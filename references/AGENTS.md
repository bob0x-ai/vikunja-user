# AGENTS.md - Vikunja User Skill

## Project Overview

A user-facing skill for OpenClaw agents to interact with Vikunja tasks and projects through a clean command-line interface. This skill provides task and project management capabilities for day-to-day operations.

**Key Design Principles:**
- Simple, intuitive commands for common operations
- Automatic token refresh when authentication fails
- Clear error messages with escalation instructions when needed
- No exposure of API complexity to end users

## Architecture

### Structure
```
vikunja-user/
├── scripts/
│   ├── vikunja.sh         # Main controller script (bash)
│   └── setup.sh           # One-time setup (creates venv, installs deps)
├── src/
│   ├── __init__.py
│   ├── vikunja.py         # Main CLI entry point (Python)
│   ├── tasks.py           # Task operations
│   ├── projects.py        # Project operations
│   ├── api_client.py      # HTTP client with auth handling
│   └── config.py          # Configuration management
├── references/
│   └── AGENTS.md          # This file
├── github/
│   └── README.md          # Human-facing documentation
├── SKILL.md               # Agent-facing documentation
├── config.yaml            # Skill configuration
└── .venv/                 # Python virtual environment (created by setup)
```

### Controller Pattern

**vikunja.sh** (bash wrapper):
- Activates Python virtual environment
- Dispatches to Python modules
- Handles venv path resolution
- Returns exit codes for agent consumption

**Python modules**:
- `vikunja.py`: Main CLI using Click or argparse
- `tasks.py`: Task-related API operations
- `projects.py`: Project-related API operations
- `api_client.py`: Shared HTTP client with automatic token refresh

### Authentication Flow

```
User Command
    ↓
vikunja.sh (bash)
    ↓
vikunja.py (Python)
    ↓
api_client.py
    ↓
Check users.yaml for token
    ↓
API Call with token
    ↓
If 401 Unauthorized:
    → Check for token_refresh.sh
    → If exists: silent refresh → retry
    → If not exists: return error with escalation instructions
```

## Supported Commands

### Task Commands

```bash
# List tasks (with optional filters)
vikunja task list [--project <name>] [--status open|done] [--filter <name>] [--user <vikunja username>]

# Create a new task
vikunja task create --title "Task title" [--project <name>] [--description <text>] [--due <date>]

# Show task details
vikunja task show <task_id>

# Update a task
vikunja task update <task_id> [--title <text>] [--description <text>] [--due <date>] [--done|--undone] [--assignee <vikunja username>]

# Delete a task
vikunja task delete <task_id>

# Add comment to task
vikunja task comment <task_id> "Comment text"
```

### Project Commands

```bash
# List all projects
vikunja project list

# Show project details
vikunja project show <project_id>

# List tasks in a project
vikunja project tasks <project_id> [--status open|done]
```

## Configuration

**config.yaml** (skill-level):
```yaml
vikunja:
  base_url: http://127.0.0.1:3456/api/v1
  
paths:
  # Path to admin skill's users.yaml
  credentials: ~/.openclaw/credentials/vikunja
  
  # Path to token refresh script (optional)
  token_refresh: ../vikunja-admin/scripts/token_refresh.sh
```

**users.yaml** (managed by admin skill):
```yaml
users:
  agent_name:
    user: vikunja_username
    id: 123
    password: secret
    token: api_token_here
    scope: worker
```

## Token Management

### Automatic Token Refresh

When an API call returns 401 Unauthorized:

1. Check if `token_refresh.sh` exists at configured path
2. If exists:
   - Call `./token_refresh.sh <username>`
   - If success (exit 0): retry original API call with new token
   - If failure (exit 1): return error
3. If refresh script not found:
   - Return error: "Token expired. Please contact an administrator to refresh your access."

### Token Storage

- Tokens are READ-ONLY from `users.yaml`
- This skill NEVER writes to users.yaml
- Token refresh is delegated to admin skill

## Error Handling

### Success Response
```
OK: <message>
```
Exit code: 0

### Error Types

**Authentication Error (refresh available):**
```
ERROR: Token expired, attempting refresh...
OK: Token refreshed successfully
<normal output>
```

**Authentication Error (no refresh):**
```
ERROR: Authentication failed. Your access token has expired.
Please contact an administrator to refresh your Vikunja access.
```
Exit code: 1

**User Not Found:**
```
ERROR: User '<username>' not found in configuration.
Please ensure your Vikunja account is properly set up.
```
Exit code: 1

**API Error:**
```
ERROR: Vikunja API error: <error_message>
```
Exit code: 1

**Validation Error:**
```
ERROR: Invalid input: <field> - <reason>
```
Exit code: 2

## Implementation Details

### Python Dependencies

**requirements.txt:**
```
requests>=2.28.0
pyyaml>=6.0
```
**Python version:** 3.14

### API Client Design

**api_client.py** key features:
- Session management with automatic retries
- Token injection from users.yaml
- 401 handling with automatic refresh
- Consistent error formatting
- JSON parsing

**Example flow:**
```python
def api_call(method, endpoint, data=None):
    token = get_token_from_yaml()
    response = requests.request(method, url, headers={'Authorization': f'Bearer {token}'})
    
    if response.status_code == 401:
        if refresh_token():
            token = get_token_from_yaml()  # Re-read after refresh
            response = requests.request(method, url, headers={'Authorization': f'Bearer {token}'})
        else:
            raise AuthError("Token refresh failed")
    
    return response.json()
```

### Date/Time Handling

- Due dates: Accept ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- Relative dates: "today", "tomorrow", "next week" (optional feature)
- Timezone: Use server timezone (assume UTC if not specified)

### Output Formats

**Default (human-readable):**
```
ID: 123
Title: Buy milk
Project: Shopping
Assignee: Agent_01
Due: 2026-03-05
Status: Open
```

**JSON (for programmatic use):**
```bash
vikunja --format json task show 123
```

## Testing Requirements

### Unit Tests
- API client authentication
- Token refresh logic
- Command parsing
- Error handling

### Integration Tests
- End-to-end task lifecycle
- Project operations
- Token refresh flow
- Error scenarios

### Test Data
- Use dedicated test project in Vikunja
- Clean up test tasks after each test run
- Mock external API calls where possible

## Security Considerations

- Never log tokens or passwords
- Tokens are read-only from users.yaml
- All API calls use HTTPS (when base_url uses https://)
- No hardcoded credentials
- Config file permissions should be 600

## Future Extensions (v2+)

**Tier 2 features (to consider later):**
- Label management
- Task assignment
- Filter management
- Bulk operations
- Attachments
- Comments management

**Not in scope:**
- User management (admin skill territory)
- Team management (admin skill territory)
- Webhooks
- System administration

## References

- Vikunja API Docs: https://try.vikunja.io/api/v1/docs
- Admin Skill: `~/skills-dev/vikunja-admin/`
- Token Refresh: `~/skills-dev/vikunja-admin/scripts/token_refresh.sh`

## Development Notes

### Adding New Commands

1. Add command to `vikunja.py` CLI
2. Implement logic in appropriate module (tasks.py/projects.py)
3. Update SKILL.md documentation
4. Add tests
5. Update this AGENTS.md if architecture changes

### Code Style

- Follow PEP 8 for Python code
- Use type hints where practical
- Document all public functions
- Keep functions focused and small

## Questions?

See SKILL.md for user-facing documentation.
