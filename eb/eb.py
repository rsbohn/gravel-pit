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

DB_FILE = Path(__file__).parent / "issues.db"
EXPORT_DIR = Path(__file__).parent / "exports"
EXPORT_FILE = EXPORT_DIR / "items.json"

# Status workflow: proposed -> ready -> in progress -> completed -> done
VALID_STATUSES = ["proposed", "ready", "in progress", "completed", "done"]
VALID_TYPES = ["issue", "feature"]
EXTERNAL_COLUMNS = {
    "external_source": "TEXT",
    "external_id": "TEXT",
    "external_url": "TEXT",
    "external_repo": "TEXT",
    "external_state": "TEXT",
    "external_updated": "TEXT",
    "external_comment": "TEXT",
}


def init_db():
    """Initialize the SQLite database with schema."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL DEFAULT 'issue' CHECK(type IN ('issue', 'feature')),
        status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'ready', 'in progress', 'completed', 'done')),
        priority INTEGER DEFAULT 0,
        created_date TEXT NOT NULL,
        updated_date TEXT NOT NULL
    )''')

    ensure_columns(conn)

    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(conn):
    """Add missing columns for newer features."""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(items)")}
    for column, col_type in EXTERNAL_COLUMNS.items():
        if column not in existing:
            c.execute(f"ALTER TABLE items ADD COLUMN {column} {col_type}")


def add_item(title, description=None, item_type="issue", priority=0):
    """Add a new issue or feature."""
    if item_type not in VALID_TYPES:
        print(f"Error: type must be one of {VALID_TYPES}")
        return False
    
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    c.execute('''INSERT INTO items (title, description, type, status, priority, created_date, updated_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (title, description, item_type, "proposed", priority, now, now))
    
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
    print(f"\n{'ID':<4} {'Type':<8} {'Status':<12} {'Priority':<8} {'Title':<40}")
    print("-" * 80)
    
    for item in items:
        status_display = item['status'].ljust(12)
        title_display = item['title'][:40].ljust(40)
        print(f"{item['id']:<4} {item['type']:<8} {status_display} {item['priority']:<8} {title_display}")


def show_item(item_id):
    """Show detailed information about an item."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = c.fetchone()
    conn.close()
    
    if not item:
        print(f"Error: Item #{item_id} not found")
        return False
    
    print(f"\n{'ID:':<15} {item['id']}")
    print(f"{'Title:':<15} {item['title']}")
    print(f"{'Type:':<15} {item['type']}")
    print(f"{'Status:':<15} {item['status']}")
    print(f"{'Priority:':<15} {item['priority']}")
    print(f"{'Description:':<15} {item['description'] or 'N/A'}")
    print(f"{'Created:':<15} {item['created_date']}")
    print(f"{'Updated:':<15} {item['updated_date']}")
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


def export_json():
    """Export all items to JSON for git tracking."""
    EXPORT_DIR.mkdir(exist_ok=True)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM items ORDER BY id")
    items = c.fetchall()
    conn.close()
    
    data = [dict(item) for item in items]
    
    with open(EXPORT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Exported {len(data)} items to {EXPORT_FILE}")


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


def sync_export_commit(message="eb export"):
    """Export items, stage the export, and commit."""
    export_json()

    repo_root = Path(__file__).resolve().parents[1]
    if run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_root) is None:
        return False

    relative_export = EXPORT_FILE.relative_to(repo_root)
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


def main():
    parser = argparse.ArgumentParser(
        description="EasyBeans (eb) - Simple Issue Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  eb add "Fix login bug" -d "Users can't log in with Google" -t issue -p 10
  eb list
  eb list --status "in progress"
  eb show 1
  eb status 1 "ready"
  eb delete 1
  eb export
  eb gh
  eb github import owner/repo
  eb sync
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new issue or feature")
    add_parser.add_argument("title", help="Title of the issue/feature")
    add_parser.add_argument("-d", "--description", help="Description")
    add_parser.add_argument("-t", "--type", choices=VALID_TYPES, default="issue", help="Type (default: issue)")
    add_parser.add_argument("-p", "--priority", type=int, default=0, help="Priority level (default: 0)")
    
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
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export items to JSON")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Export items and commit JSON")
    sync_parser.add_argument("-m", "--message", default="eb export", help="Commit message")

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
    
    # Initialize database
    init_db()
    
    # Handle commands
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "add":
        add_item(args.title, args.description, args.type, args.priority)
    elif args.command == "list":
        list_items(args.status, args.type)
    elif args.command == "show":
        show_item(args.id)
    elif args.command == "status":
        update_status(args.id, args.status, args.comment)
    elif args.command == "delete":
        delete_item(args.id)
    elif args.command == "export":
        export_json()
    elif args.command == "gh":
        check_gh_cli()
    elif args.command == "sync":
        sync_export_commit(args.message)
    elif args.command == "github":
        if not args.github_command:
            github_parser.print_help()
        elif args.github_command == "import":
            import_github(args.repo, args.state, args.limit)
        elif args.github_command == "push":
            push_github(args.repo, args.dry_run)


if __name__ == "__main__":
    main()
