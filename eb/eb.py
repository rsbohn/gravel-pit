#!/usr/bin/env python3
"""
EasyBeans (eb) - Simple Issue Tracker
Tracks issues and features with SQLite and git-friendly exports
"""

import sqlite3
import argparse
import sys
from datetime import datetime
from pathlib import Path
import json
import shutil
import subprocess
from importlib import metadata

def get_project_base():
    local_db = Path.cwd() / "eb" / "issues.db"
    if local_db.is_file():
        return local_db.parent
    return Path(__file__).parent


def get_db_file():
    return get_project_base() / "issues.db"


def get_export_dir():
    return get_project_base() / "exports"


def get_export_file():
    return get_export_dir() / "items.json"

# Status workflow: proposed -> ready -> in progress -> completed -> done
VALID_STATUSES = ["proposed", "ready", "in progress", "completed", "done"]
VALID_TYPES = ["issue", "feature", "epic"]
CURRENT_SCHEMA_VERSION = 2
EXTERNAL_COLUMNS = {
    "external_source": "TEXT",
    "external_id": "TEXT",
    "external_url": "TEXT",
    "external_repo": "TEXT",
    "external_state": "TEXT",
    "external_updated": "TEXT",
    "external_comment": "TEXT",
}
PARENT_COLUMNS = {
    "parent_id": "INTEGER",
}


def init_db(db_file=None):
    """Initialize the SQLite database with schema."""
    db_file = db_file or get_db_file()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL DEFAULT 'issue' CHECK(type IN ('issue', 'feature', 'epic')),
        status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'ready', 'in progress', 'completed', 'done')),
        priority INTEGER DEFAULT 0,
        created_date TEXT NOT NULL,
        updated_date TEXT NOT NULL,
        parent_id INTEGER
    )''')

    ensure_schema(conn)

    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(get_db_file())
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(conn):
    """Add missing columns for newer features."""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(items)")}
    for column, col_type in {**PARENT_COLUMNS, **EXTERNAL_COLUMNS}.items():
        if column not in existing:
            c.execute(f"ALTER TABLE items ADD COLUMN {column} {col_type}")


def table_supports_epic(conn):
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'items'")
    row = c.fetchone()
    if not row or not row[0]:
        return True
    sql = row[0]
    if "CHECK(type IN" not in sql:
        return True
    return "'epic'" in sql


def has_column(conn, column_name):
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(items)")}
    return column_name in existing


def schema_version_table_exists(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'")
    return c.fetchone() is not None


def ensure_schema_version_table(conn):
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")


def get_schema_version(conn):
    if not schema_version_table_exists(conn):
        return None
    c = conn.cursor()
    c.execute("SELECT version FROM schema_version LIMIT 1")
    row = c.fetchone()
    if not row:
        return None
    return row[0]


def set_schema_version(conn, version):
    c = conn.cursor()
    c.execute("DELETE FROM schema_version")
    c.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def get_app_version():
    try:
        return metadata.version("gravel-pit")
    except metadata.PackageNotFoundError:
        return "unknown"


def read_db_schema_version():
    db_file = get_db_file()
    if not db_file.exists():
        return None
    conn = sqlite3.connect(db_file)
    try:
        if not schema_version_table_exists(conn):
            return infer_schema_version(conn)
        version = get_schema_version(conn)
        if version is None:
            return infer_schema_version(conn)
        return version
    finally:
        conn.close()


def infer_schema_version(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'items'")
    if not c.fetchone():
        return CURRENT_SCHEMA_VERSION
    if not table_supports_epic(conn):
        return 1
    if not has_column(conn, "parent_id"):
        return 1
    return 2


def rebuild_items_table(conn):
    c = conn.cursor()
    c.execute("ALTER TABLE items RENAME TO items_old")
    c.execute('''CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL DEFAULT 'issue' CHECK(type IN ('issue', 'feature', 'epic')),
        status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'ready', 'in progress', 'completed', 'done')),
        priority INTEGER DEFAULT 0,
        created_date TEXT NOT NULL,
        updated_date TEXT NOT NULL,
        parent_id INTEGER,
        external_source TEXT,
        external_id TEXT,
        external_url TEXT,
        external_repo TEXT,
        external_state TEXT,
        external_updated TEXT,
        external_comment TEXT
    )''')

    existing = {row[1] for row in c.execute("PRAGMA table_info(items_old)")}
    new_columns = [
        "id",
        "title",
        "description",
        "type",
        "status",
        "priority",
        "created_date",
        "updated_date",
        "parent_id",
        *EXTERNAL_COLUMNS.keys(),
    ]
    select_columns = [
        col if col in existing else f"NULL AS {col}"
        for col in new_columns
    ]
    c.execute(
        f"INSERT INTO items ({', '.join(new_columns)}) "
        f"SELECT {', '.join(select_columns)} FROM items_old"
    )
    c.execute("DROP TABLE items_old")


def migrate_1_to_2(conn, dry_run=False):
    if dry_run:
        return
    if not table_supports_epic(conn):
        rebuild_items_table(conn)
    ensure_columns(conn)


MIGRATIONS = {
    1: migrate_1_to_2,
}


def run_migrations(conn, target_version=CURRENT_SCHEMA_VERSION, dry_run=False):
    ensure_schema_version_table(conn)
    version = get_schema_version(conn)
    if version is None:
        version = infer_schema_version(conn)
        if not dry_run:
            print(f"Info: initialized schema version tracking at {version}.")
            set_schema_version(conn, version)

    if version > target_version:
        print(
            f"Error: database schema version {version} is newer than supported {target_version}.",
            file=sys.stderr,
        )
        return False

    if version == target_version:
        return True

    current = version
    if not dry_run:
        print(f"Info: migrating database schema from {version} to {target_version}.")
    while current < target_version:
        migrate_fn = MIGRATIONS.get(current)
        if not migrate_fn:
            print(
                f"Error: missing migration from version {current} to {current + 1}.",
                file=sys.stderr,
            )
            return False
        if dry_run:
            print(f"• Would migrate schema {current} -> {current + 1}")
        else:
            migrate_fn(conn, dry_run=False)
            set_schema_version(conn, current + 1)
            print(f"✓ Migrated schema {current} -> {current + 1}")
        current += 1

    return True


def ensure_schema(conn):
    return run_migrations(conn, CURRENT_SCHEMA_VERSION, dry_run=False)


def fetch_item(conn, item_id):
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    return c.fetchone()


def get_parent_chain(conn, item_id):
    chain = []
    current_id = item_id
    visited = set()
    while current_id:
        if current_id in visited:
            break
        visited.add(current_id)
        row = fetch_item(conn, current_id)
        if not row:
            break
        parent_id = row["parent_id"]
        if not parent_id:
            break
        chain.append(parent_id)
        current_id = parent_id
    return chain


def validate_parent_assignment(conn, child_type, parent_id, child_id=None):
    if parent_id is None:
        return True
    if child_type == "epic":
        print("Error: epics cannot have a parent.", file=sys.stderr)
        return False
    parent = fetch_item(conn, parent_id)
    if not parent:
        print(f"Error: Parent item #{parent_id} not found.", file=sys.stderr)
        return False
    parent_type = parent["type"]
    if parent_type == "epic" and child_type in {"issue", "feature"}:
        return True
    if parent_type == "feature" and child_type == "issue":
        return True
    print(
        f"Error: {parent_type} items cannot contain {child_type} items.",
        file=sys.stderr,
    )
    return False


def add_item(title, description=None, item_type="issue", priority=0, parent_id=None):
    """Add a new issue, feature, or epic."""
    if item_type not in VALID_TYPES:
        print(f"Error: type must be one of {VALID_TYPES}")
        return False
    
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()

    if parent_id is not None:
        if not validate_parent_assignment(conn, item_type, parent_id):
            conn.close()
            return False
    
    c.execute('''INSERT INTO items (title, description, type, status, priority, created_date, updated_date, parent_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (title, description, item_type, "proposed", priority, now, now, parent_id))
    
    conn.commit()
    item_id = c.lastrowid
    conn.close()
    
    print(f"✓ Created {item_type} #{item_id}: {title}")
    return True


def list_items(status=None, item_type=None):
    """List all items, optionally filtered by status or type."""
    conn = get_db()
    c = conn.cursor()
    
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if item_type:
        query += " AND type = ?"
        params.append(item_type)
    
    query += " ORDER BY priority DESC, created_date ASC"
    
    c.execute(query, params)
    items = c.fetchall()
    conn.close()
    
    if not items:
        print("No items found.")
        return
    
    # Print header
    print(f"\n{'ID':<4} {'Type':<8} {'Status':<12} {'Priority':<8} {'Parent':<6} {'Title':<34}")
    print("-" * 86)
    
    for item in items:
        status_display = item['status'].ljust(12)
        title_display = item['title'][:34].ljust(34)
        parent_display = str(item['parent_id']) if item['parent_id'] else "-"
        print(f"{item['id']:<4} {item['type']:<8} {status_display} {item['priority']:<8} {parent_display:<6} {title_display}")


def show_item(item_id):
    """Show detailed information about an item."""
    conn = get_db()
    c = conn.cursor()
    
    item = fetch_item(conn, item_id)
    conn.close()
    
    if not item:
        print(f"Error: Item #{item_id} not found")
        return False
    
    print(f"\n{'ID:':<15} {item['id']}")
    print(f"{'Title:':<15} {item['title']}")
    print(f"{'Type:':<15} {item['type']}")
    print(f"{'Status:':<15} {item['status']}")
    print(f"{'Priority:':<15} {item['priority']}")
    if item["parent_id"]:
        conn = get_db()
        parent = fetch_item(conn, item["parent_id"])
        conn.close()
        if parent:
            parent_label = f"{parent['id']}: {parent['title']}"
        else:
            parent_label = f"{item['parent_id']} (missing)"
        print(f"{'Parent:':<15} {parent_label}")
    else:
        print(f"{'Parent:':<15} None")
    print(f"{'Description:':<15} {item['description'] or 'N/A'}")
    print(f"{'Created:':<15} {item['created_date']}")
    print(f"{'Updated:':<15} {item['updated_date']}")
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, title, type, status FROM items WHERE parent_id = ? ORDER BY priority DESC, created_date ASC",
        (item_id,),
    )
    children = c.fetchall()
    conn.close()
    if children:
        print(f"{'Children:':<15} {len(children)}")
        for child in children:
            print(f"{'':<15} #{child['id']} [{child['type']}] {child['status']} - {child['title']}")
    print()
    
    return True


def update_status(item_id, new_status, comment=None):
    """Update the status of an item."""
    if new_status not in VALID_STATUSES:
        print(f"Error: status must be one of {VALID_STATUSES}")
        return False
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT status FROM items WHERE id = ?", (item_id,))
    result = c.fetchone()
    
    if not result:
        print(f"Error: Item #{item_id} not found")
        conn.close()
        return False
    
    now = datetime.now().isoformat()
    c.execute(
        "UPDATE items SET status = ?, updated_date = ?, external_comment = COALESCE(?, external_comment) WHERE id = ?",
        (new_status, now, comment, item_id),
    )
    conn.commit()
    conn.close()
    
    print(f"✓ Item #{item_id} status updated to: {new_status}")
    return True


def delete_item(item_id):
    """Delete an item."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT title FROM items WHERE id = ?", (item_id,))
    result = c.fetchone()
    
    if not result:
        print(f"Error: Item #{item_id} not found")
        conn.close()
        return False
    
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    print(f"✓ Deleted item #{item_id}: {result['title']}")
    return True


def set_parent(child_id, parent_id=None):
    conn = get_db()
    c = conn.cursor()

    child = fetch_item(conn, child_id)
    if not child:
        print(f"Error: Item #{child_id} not found", file=sys.stderr)
        conn.close()
        return False

    if parent_id is None:
        now = datetime.now().isoformat()
        c.execute(
            "UPDATE items SET parent_id = NULL, updated_date = ? WHERE id = ?",
            (now, child_id),
        )
        conn.commit()
        conn.close()
        print(f"✓ Cleared parent for item #{child_id}")
        return True

    if parent_id == child_id:
        print("Error: Item cannot be its own parent.", file=sys.stderr)
        conn.close()
        return False

    if not validate_parent_assignment(conn, child["type"], parent_id, child_id=child_id):
        conn.close()
        return False

    parent_chain = get_parent_chain(conn, parent_id)
    if child_id in parent_chain:
        print("Error: Parent assignment would create a cycle.", file=sys.stderr)
        conn.close()
        return False

    now = datetime.now().isoformat()
    c.execute(
        "UPDATE items SET parent_id = ?, updated_date = ? WHERE id = ?",
        (parent_id, now, child_id),
    )
    conn.commit()
    conn.close()
    print(f"✓ Set parent of item #{child_id} to #{parent_id}")
    return True


def export_json():
    """Export all items to JSON for git tracking."""
    export_dir = get_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM items ORDER BY id")
    items = c.fetchall()
    conn.close()
    
    data = [dict(item) for item in items]
    
    export_file = get_export_file()
    with open(export_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Exported {len(data)} items to {export_file}")


def check_gh_cli():
    """Check if GitHub CLI (gh) is installed and runnable."""
    gh_path = shutil.which("gh")
    if not gh_path:
        print(
            "Error: GitHub CLI (gh) not found.\n"
            "Install with:\n"
            "  brew install gh\n"
            "or see https://cli.github.com",
            file=sys.stderr,
        )
        return False

    result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(
            "Error: GitHub CLI (gh) was found but failed to run.",
            file=sys.stderr,
        )
        if stderr:
            print(stderr, file=sys.stderr)
        print(
            "Try reinstalling:\n"
            "  brew install gh\n"
            "or see https://cli.github.com",
            file=sys.stderr,
        )
        return False

    version_line = result.stdout.strip().splitlines()[0] if result.stdout else "gh (unknown version)"
    print(f"✓ GitHub CLI detected: {version_line}")
    return True


def parse_iso8601(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_gh(args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown error"
        print("Error: GitHub CLI command failed.", file=sys.stderr)
        print(stderr, file=sys.stderr)
        return None
    return result.stdout


def map_github_state(state):
    return "completed" if state == "closed" else "proposed"


def import_github(repo, state="all", limit=200):
    if not check_gh_cli():
        return False

    output = run_gh([
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,body,state,url,updatedAt",
    ])
    if output is None:
        return False

    try:
        issues = json.loads(output)
    except json.JSONDecodeError:
        print("Error: Failed to parse GitHub CLI output.", file=sys.stderr)
        return False

    conn = get_db()
    c = conn.cursor()
    created = 0
    updated = 0

    for issue in issues:
        external_id = str(issue.get("number"))
        title = issue.get("title") or "(untitled)"
        body = issue.get("body") or None
        external_state = issue.get("state") or "open"
        external_url = issue.get("url")
        external_updated = issue.get("updatedAt")
        mapped_status = map_github_state(external_state)

        c.execute(
            "SELECT id, updated_date, external_updated FROM items WHERE external_source = ? AND external_id = ? AND external_repo = ?",
            ("github", external_id, repo),
        )
        row = c.fetchone()

        if not row:
            now = datetime.now().isoformat()
            c.execute(
                """INSERT INTO items
                   (title, description, type, status, priority, created_date, updated_date,
                    external_source, external_id, external_url, external_repo, external_state, external_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    title,
                    body,
                    "issue",
                    mapped_status,
                    0,
                    now,
                    now,
                    "github",
                    external_id,
                    external_url,
                    repo,
                    external_state,
                    external_updated,
                ),
            )
            created += 1
            continue

        local_updated = parse_iso8601(row["updated_date"])
        remote_updated = parse_iso8601(external_updated)
        should_update = True
        if local_updated and remote_updated and remote_updated <= local_updated:
            should_update = False

        if should_update:
            now = datetime.now().isoformat()
            c.execute(
                """UPDATE items
                   SET title = ?, description = ?, status = ?, updated_date = ?,
                       external_url = ?, external_state = ?, external_updated = ?
                   WHERE id = ?""",
                (
                    title,
                    body,
                    mapped_status,
                    now,
                    external_url,
                    external_state,
                    external_updated,
                    row["id"],
                ),
            )
            updated += 1
        else:
            c.execute(
                """UPDATE items
                   SET external_url = ?, external_state = ?, external_updated = ?
                   WHERE id = ?""",
                (external_url, external_state, external_updated, row["id"]),
            )

    conn.commit()
    conn.close()

    print(f"✓ Imported {created} issue(s), updated {updated} issue(s) from {repo}")
    return True


def push_github(repo, dry_run=False):
    if not check_gh_cli():
        return False

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT id, external_id, external_comment, status, external_state
           FROM items
           WHERE external_source = ? AND external_repo = ? AND status IN ('completed', 'done')""",
        ("github", repo),
    )
    items = c.fetchall()

    if not items:
        print("No completed items to sync.")
        conn.close()
        return True

    updated = 0
    for item in items:
        if item["external_state"] == "closed":
            continue
        issue_number = item["external_id"]
        comment = item["external_comment"]

        if dry_run:
            action = "close"
            if comment:
                action = "comment + close"
            print(f"• Would {action} GitHub issue #{issue_number} in {repo}")
            continue

        if comment:
            result = run_gh([
                "issue",
                "comment",
                issue_number,
                "--repo",
                repo,
                "--body",
                comment,
            ])
            if result is None:
                continue

        result = run_gh([
            "issue",
            "close",
            issue_number,
            "--repo",
            repo,
        ])
        if result is None:
            continue

        now = datetime.now().isoformat()
        c.execute(
            "UPDATE items SET external_state = ?, external_updated = ?, external_comment = NULL WHERE id = ?",
            ("closed", now, item["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()

    if dry_run:
        print("✓ Dry run complete.")
    else:
        print(f"✓ Synced {updated} issue(s) to {repo}")
    return True


def run_git(args, cwd):
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown error"
        print("Error: git command failed.", file=sys.stderr)
        print(stderr, file=sys.stderr)
        return None
    return result.stdout


def get_repo_root(start_dir):
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=start_dir,
    )
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return Path(output)


def sync_export_commit(message="eb export"):
    """Export items, stage the export, and commit."""
    export_json()

    export_file = get_export_file()
    repo_root = get_repo_root(export_file.parent)
    if repo_root is None:
        print("Error: Not inside a git repository.", file=sys.stderr)
        return False

    try:
        relative_export = export_file.relative_to(repo_root)
    except ValueError:
        print("Error: Export file is not inside the git repository.", file=sys.stderr)
        return False
    status = run_git(["status", "--porcelain", str(relative_export)], cwd=repo_root)
    if status is None:
        return False

    if not status.strip():
        print("No changes to commit.")
        return True

    if run_git(["add", str(relative_export)], cwd=repo_root) is None:
        return False

    if run_git(["commit", "-m", message], cwd=repo_root) is None:
        return False

    print(f"✓ Committed {relative_export}")
    return True


def init_project():
    project_dir = Path.cwd() / "eb"
    if project_dir.exists() and not project_dir.is_dir():
        print("Error: ./eb exists and is not a directory.", file=sys.stderr)
        return False

    project_dir.mkdir(exist_ok=True)
    db_file = project_dir / "issues.db"
    init_db(db_file=db_file)

    export_dir = project_dir / "exports"
    export_dir.mkdir(exist_ok=True)

    print(f"✓ Initialized eb project at {project_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="EasyBeans (eb) - Simple Issue Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  eb init
  eb add "Fix login bug" -d "Users can't log in with Google" -t issue -p 10
  eb add "Theme overhaul" -t epic -p 3
  eb add "Dark mode" -t feature --parent 2
  eb add "Fix contrast" -t issue --parent 3
  eb list
  eb list --status "in progress"
  eb show 1
  eb status 1 "ready"
  eb parent 4 2
  eb parent 4 --clear
  eb delete 1
  eb export
  eb gh
  eb github import owner/repo
  eb sync
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Init command
    subparsers.add_parser("init", help="Initialize a new eb project in ./eb")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new issue, feature, or epic")
    add_parser.add_argument("title", help="Title of the item")
    add_parser.add_argument("-d", "--description", help="Description")
    add_parser.add_argument("-t", "--type", choices=VALID_TYPES, default="issue", help="Type (default: issue)")
    add_parser.add_argument("-p", "--priority", type=int, default=0, help="Priority level (default: 0)")
    add_parser.add_argument("--parent", type=int, help="Parent item ID")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all items")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--type", help="Filter by type")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show item details")
    show_parser.add_argument("id", type=int, help="Item ID")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Update item status")
    status_parser.add_argument("id", type=int, help="Item ID")
    status_parser.add_argument("status", choices=VALID_STATUSES, help="New status")
    status_parser.add_argument("--comment", help="Comment to sync with external issue close")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an item")
    delete_parser.add_argument("id", type=int, help="Item ID")

    # Parent command
    parent_parser = subparsers.add_parser("parent", help="Set or clear an item's parent")
    parent_parser.add_argument("child_id", type=int, help="Child item ID")
    parent_parser.add_argument("parent_id", type=int, nargs="?", help="Parent item ID")
    parent_parser.add_argument("--clear", action="store_true", help="Clear the current parent")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export items to JSON")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Export items and commit JSON")
    sync_parser.add_argument("-m", "--message", default="eb export", help="Commit message")

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate database schema")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Show migrations without applying them")
    migrate_parser.add_argument("--to-version", type=int, default=CURRENT_SCHEMA_VERSION, help="Target schema version")

    # Version command
    subparsers.add_parser("version", help="Show app and schema version")

    # GitHub CLI check command
    gh_parser = subparsers.add_parser("gh", help="Check GitHub CLI (gh) availability")

    # GitHub sync commands
    github_parser = subparsers.add_parser("github", help="GitHub issue sync")
    github_subparsers = github_parser.add_subparsers(dest="github_command", help="GitHub command to run")

    github_import = github_subparsers.add_parser("import", help="Import issues from GitHub")
    github_import.add_argument("repo", help="Repository (owner/repo)")
    github_import.add_argument("--state", choices=["open", "closed", "all"], default="all", help="Issue state")
    github_import.add_argument("--limit", type=int, default=200, help="Max issues to import")

    github_push = github_subparsers.add_parser("push", help="Push completed items to GitHub")
    github_push.add_argument("repo", help="Repository (owner/repo)")
    github_push.add_argument("--dry-run", action="store_true", help="Show actions without applying them")
    
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "init":
        init_project()
        return

    # Initialize database for standard commands
    if args.command not in {"version"}:
        init_db()
    
    if args.command == "add":
        add_item(args.title, args.description, args.type, args.priority, args.parent)
    elif args.command == "list":
        list_items(args.status, args.type)
    elif args.command == "show":
        show_item(args.id)
    elif args.command == "status":
        update_status(args.id, args.status, args.comment)
    elif args.command == "delete":
        delete_item(args.id)
    elif args.command == "parent":
        if args.clear:
            set_parent(args.child_id, None)
        elif args.parent_id is None:
            print("Error: parent_id is required unless --clear is used.", file=sys.stderr)
        else:
            set_parent(args.child_id, args.parent_id)
    elif args.command == "export":
        export_json()
    elif args.command == "gh":
        check_gh_cli()
    elif args.command == "sync":
        sync_export_commit(args.message)
    elif args.command == "migrate":
        conn = get_db()
        run_migrations(conn, args.to_version, args.dry_run)
        conn.close()
    elif args.command == "version":
        app_version = get_app_version()
        db_version = read_db_schema_version()
        print(f"EasyBeans version: {app_version}")
        if db_version is None:
            print(f"Database schema version: not initialized (current: {CURRENT_SCHEMA_VERSION})")
        else:
            print(f"Database schema version: {db_version} (current: {CURRENT_SCHEMA_VERSION})")
    elif args.command == "github":
        if not args.github_command:
            github_parser.print_help()
        elif args.github_command == "import":
            import_github(args.repo, args.state, args.limit)
        elif args.github_command == "push":
            push_github(args.repo, args.dry_run)


if __name__ == "__main__":
    main()
