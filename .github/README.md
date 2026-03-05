# Vikunja User Skill

CLI wrapper for working with a local Vikunja instance using scoped API tokens.

## Installation

### Prerequisites

- Python 3.10+
- Local Vikunja reachable at configured `base_url`
- Credentials managed by `vikunja-admin` in `~/.openclaw/credentials/vikunja/users.yaml`

### Run Setup

```bash
cd ~/skills-dev/vikunja-user
./scripts/setup.sh
```

## Configuration

Edit `config.yaml`:

```yaml
vikunja:
  base_url: http://127.0.0.1:3456/api/v1

paths:
  credentials: ~/.openclaw/credentials/vikunja
  token_refresh: ../vikunja-admin/scripts/token_refresh.sh

auth:
  diagnostics_cache_seconds: 60

default_format: json
```

`credentials` can be either:
- a directory containing `users.yaml`, or
- a direct path to `users.yaml`.

`users.yaml` entries may include token identity metadata for deterministic diagnostics:

```yaml
users:
  bob:
    user: bob
    id: 1
    password: secret
    token: vkp_...
    token_id: 123
    token_last_eight: abcdef12
    scope: worker
```

## Authentication Username Resolution

Priority order:
1. `--username`
2. `$AGENT_ID`
3. `$agent_id`
4. `$OPENCLAW_AGENT_ID` (legacy fallback)
5. system username

## Usage

```bash
./scripts/vikunja.sh task list
./scripts/vikunja.sh project list
./scripts/vikunja.sh task create --title "Review PR" --project 1
./scripts/vikunja.sh --format human task show 123
```

## Global Options

```text
--config, -c   Path to config.yaml
--format, -f   json (default) or human
--username, -u Username override
```
