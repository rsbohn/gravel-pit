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

DB_FILE = Path(__file__).parent / "issues.db"
EXPORT_DIR = Path(__file__).parent / "exports"

# Status workflow: proposed -> ready -> in progress -> completed -> done
VALID_STATUSES = ["proposed", "ready", "in progress", "completed", "done"]
VALID_TYPES = ["issue", "feature"]


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
    
    conn.commit()
    conn.close()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


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


def update_status(item_id, new_status):
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
    c.execute("UPDATE items SET status = ?, updated_date = ? WHERE id = ?",
              (new_status, now, item_id))
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
    
    export_file = EXPORT_DIR / "items.json"
    with open(export_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Exported {len(data)} items to {export_file}")


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
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an item")
    delete_parser.add_argument("id", type=int, help="Item ID")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export items to JSON")
    
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
        update_status(args.id, args.status)
    elif args.command == "delete":
        delete_item(args.id)
    elif args.command == "export":
        export_json()


if __name__ == "__main__":
    main()
