# Gravel Pit - Simple Issue Tracker

A lightweight SQLite-based issue tracker with git-friendly exports. Items progress through a workflow: **proposed** → **ready** → **in progress** → **completed** → **done**.

## Quick Start

```bash
# Add an issue or feature
uv run eb add "Fix login bug" -d "Users can't log in with Google" -t issue -p 10
uv run eb add "Dark mode" -t feature -p 5

# List all items
uv run eb list

# Update status
uv run eb status 1 "ready"
uv run eb status 1 "in progress"

# Export for git tracking (creates JSON)
uv run eb export
```

## Features

- **Track issues & features** with 5-stage workflow
- **Priority levels** for organizing work
- **SQLite backend** for persistent storage
- **Git-friendly exports** to JSON (stored in `eb/exports/`)
- **Simple CLI** with intuitive commands

## Available Commands

- `uv run eb add <title>` - Create new issue/feature
  - `-d, --description` - Add description
  - `-t, --type` - Set type: issue or feature (default: issue)
  - `-p, --priority` - Set priority level (default: 0)
- `uv run eb list` - Show all items
  - `--status <status>` - Filter by status
  - `--type <type>` - Filter by type
- `uv run eb show <id>` - Show item details
- `uv run eb status <id> <status>` - Update item status
- `uv run eb delete <id>` - Delete item
- `uv run eb export` - Export to JSON

## Status Workflow

1. **proposed** - Initial state when created
2. **ready** - Prepared to work on
3. **in progress** - Currently being worked on
4. **completed** - Work finished, pending release
5. **done** - Released/finalized

For detailed documentation, see [eb/README.md](eb/README.md).