# EasyBeans Quickstart Guide

Welcome to EasyBeans! This guide will get you up and running in minutes.

## Prerequisites

- Python 3.12+
- `uv` package manager

## Setup

### 1. Install uv (if not already installed)

```bash
pip install uv
```

### 2. Sync the project

From the project root directory:

```bash
uv sync
```

This sets up the virtual environment and installs EasyBeans as a command-line tool.

## Basic Usage

All commands start with `uv run eb`:

### Create an Issue

```bash
uv run eb add "Fix the login bug"
```

Add more details:

```bash
uv run eb add "Fix the login bug" \
  -d "Users can't log in with Google OAuth" \
  -t issue \
  -p 10
```

Options:
- `-d, --description` - Detailed description
- `-t, --type` - Type: `issue`, `feature`, or `epic` (default: issue)
- `-p, --priority` - Priority level 0-10 (higher = more urgent)
- `--parent` - Parent item ID (optional)

### Create a Feature

```bash
uv run eb add "Dark mode support" -t feature -p 5
```

### Create an Epic

```bash
uv run eb add "Accessibility overhaul" -t epic -p 5
```

### Link an item to a parent

```bash
uv run eb add "Color contrast fixes" -t issue --parent 3
uv run eb parent 5 3
uv run eb parent 5 --clear
```

### View Your Items

List all items:

```bash
uv run eb list
```

Filter by status:

```bash
uv run eb list --status "in progress"
```

Filter by type:

```bash
uv run eb list --type feature
```

### Check Item Details

```bash
uv run eb show 1
```

Replace `1` with the item ID.

## Status Workflow

Items move through this workflow as you work:

1. **proposed** - Initial state (automatic when created)
2. **ready** - Prepared to start
3. **in progress** - Currently being worked on
4. **completed** - Work finished, awaiting review
5. **done** - Released/finalized

### Update Status

```bash
uv run eb status 1 "ready"
uv run eb status 1 "in progress"
uv run eb status 1 "completed"
uv run eb status 1 "done"
```

You can jump to any status at any time—the workflow is flexible!

### Delete an Item

```bash
uv run eb delete 1
```

## Export for Git Tracking

EasyBeans stores items in SQLite, but you can export to JSON for version control:

```bash
uv run eb export
```

This creates:
- `eb/exports/items.json`

Commit this file to git to track your issues over time!

## Common Workflows

### Start Working on an Issue

```bash
# Find your issue
uv run eb list --status ready

# Start work
uv run eb status 1 "in progress"

# Do your work...

# Mark as complete
uv run eb status 1 "completed"
```

### Review and Release

```bash
# See completed items
uv run eb list --status completed

# Review details
uv run eb show 1

# Mark as done
uv run eb status 1 "done"

# Export for version control
uv run eb export
```

### Prioritize Your Backlog

```bash
# See all items sorted by priority
uv run eb list

# Add high-priority items
uv run eb add "Critical fix" -p 100

# Low-priority items get lower priority
uv run eb add "Nice-to-have improvement" -p 1
```

## Tips

- **Item IDs** are auto-incrementing. You'll see them when you create or list items.
- **Priority levels** are integers. Use 0-10 for most work, higher for critical items.
- **Descriptions** are optional but recommended for complex items.
- **Export regularly** to have a git-tracked history of your board state.
- **Status is flexible** - move items backward if needed, there are no restrictions.

## Next Steps

- Check [eb/README.md](../eb/README.md) for detailed documentation
- Review [start-here.md](../start-here.md) for an overview
- Explore the SQLite database at `eb/issues.db` directly if needed

Happy tracking!
