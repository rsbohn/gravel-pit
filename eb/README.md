# EasyBeans (eb) - Simple Issue Tracker

A lightweight SQLite-based issue tracker with git-friendly exports.

## Features

- **Track issues, features, and epics** with status workflow: proposed → ready → in progress → completed → done
- **Parent/child relationships** to group items (epics contain features/issues; features contain issues)
- **Priority levels** for organizing work
- **SQLite backend** for persistent storage
- **Git-friendly exports** to JSON and CSV for version control
- **Simple CLI** interface

## Installation

Make sure you have `uv` installed:

```bash
pip install uv
```

Run `uv sync` in the project root to set up the environment:

```bash
cd /path/to/gravel-pit
uv sync
```

Now you can use `uv run eb` from anywhere in the project.

## Usage

### Add an issue, feature, or epic

```bash
uv run eb add "Fix login bug" -d "Users can't log in with Google" -t issue -p 10
uv run eb add "Dark mode" -t feature -p 5
uv run eb add "UI refresh" -t epic -p 3
```

Options:
- `-d, --description`: Description (optional)
- `-t, --type`: Type - "issue", "feature", or "epic" (default: issue)
- `-p, --priority`: Priority level (default: 0, higher = more urgent)
- `--parent`: Parent item ID (optional)

### List items

```bash
uv run eb list
uv run eb list --status "in progress"
uv run eb list --type feature
```

### Show item details

```bash
uv run eb show 1
```

### Update item status

```bash
uv run eb status 1 "ready"
uv run eb status 1 "in progress"
uv run eb status 1 "completed"
uv run eb status 1 "done"
uv run eb status 1 "completed" --comment "Fixed locally; closing upstream."
```

### Delete an item

```bash
uv run eb delete 1
```

### Set or clear a parent

```bash
uv run eb parent 12 4
uv run eb parent 12 --clear
```

### Export for git tracking

```bash
uv run eb export
```

Exported file is placed in `eb/exports/items.json` and can be committed to git for tracking changes over time.

### Sync export and commit

```bash
uv run eb sync
uv run eb sync -m "eb export"
```

### Migrate database schema

```bash
uv run eb migrate
uv run eb migrate --dry-run
uv run eb migrate --to-version 2
```

### Show versions

```bash
uv run eb version
```

### Check GitHub CLI (gh)

External sync will require the GitHub CLI. You can verify it is installed:

```bash
uv run eb gh
```

### Sync GitHub issues

Import issues from GitHub:

```bash
uv run eb github import owner/repo
```

Push completed items (status `completed`/`done`) back to GitHub:

```bash
uv run eb github push owner/repo
uv run eb github push owner/repo --dry-run
```

## Database Schema

The SQLite database has a single `items` table with:

- `id`: Auto-incrementing primary key
- `title`: Item title (required)
- `description`: Detailed description (optional)
- `type`: "issue", "feature", or "epic"
- `status`: Current status (proposed, ready, in progress, completed, done)
- `priority`: Integer priority level
- `created_date`: ISO format timestamp
- `updated_date`: ISO format timestamp
- `parent_id`: Parent item ID (optional)

## Schema Versioning

The database stores a `schema_version` table. On startup, eb will migrate older schemas to the current version.

## Status Workflow

Items progress through this workflow:

1. **Proposed**: Initial state when created
2. **Ready**: Ready to work on
3. **In Progress**: Currently being worked on
4. **Completed**: Work finished, pending review/release
5. **Done**: Released/finalized

You can move an item to any status at any time.
