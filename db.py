"""
db.py - Database module for GrocoPilot.
---------------------------------------
This module handles all SQLite database interactions.
We use Python's built-in `sqlite3` library, so no extra database server is needed.
All tables, queries, insertions, and updates are neatly organized here into
small, readable functions with clear docstrings and type hints.
"""

from __future__ import annotations
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Path to the SQLite database file in the project directory
DB_FILE = Path(__file__).parent / "grocopilot.db"


def get_connection(db_path: Path = DB_FILE) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    We enable sqlite3.Row so we can access columns by their name like a dict.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_FILE) -> None:
    """
    Initializes the database schema if tables do not already exist.
    Creates:
      1. items: Main grocery tracking table
      2. user_overrides: Custom shelf life overrides remembered for unknown items
      3. settings: Key-value app configuration (like default storage per category)
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Main items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                price REAL,
                purchase_date TEXT NOT NULL,
                storage TEXT NOT NULL CHECK(storage IN ('fridge', 'room', 'freezer')),
                expiry_date TEXT NOT NULL,
                date_source TEXT NOT NULL CHECK(date_source IN ('estimated', 'scanned', 'typed')),
                opened INTEGER NOT NULL DEFAULT 0,
                opened_date TEXT,
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'used', 'thrown')),
                status_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 2. Table for remembering custom shelf-life overrides entered by user
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_overrides (
                item_name TEXT PRIMARY KEY,
                category TEXT,
                storage TEXT,
                shelf_days INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 3. Settings table for defaults
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_item(
    name: str,
    category: str,
    quantity: float,
    unit: str,
    purchase_date: str,
    storage: str,
    expiry_date: str,
    date_source: str = "estimated",
    price: Optional[float] = None,
    opened: int = 0,
    opened_date: Optional[str] = None,
    db_path: Path = DB_FILE,
) -> int:
    """
    Inserts a single grocery item into the items table.
    Returns the new item's integer ID.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO items (
                name, category, quantity, unit, price,
                purchase_date, storage, expiry_date, date_source,
                opened, opened_date, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            """,
            (
                name.strip(),
                category.strip(),
                quantity,
                unit.strip(),
                price,
                purchase_date,
                storage.lower().strip(),
                expiry_date,
                date_source,
                opened,
                opened_date,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def add_items_bulk(
    items_list: List[Dict[str, Any]],
    db_path: Path = DB_FILE,
) -> int:
    """
    Inserts multiple items in a single transaction for high performance.
    Used when saving reviewed items from receipts or bulk text entry.
    Returns the count of successfully saved items.
    """
    if not items_list:
        return 0

    count = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for item in items_list:
            cursor.execute(
                """
                INSERT INTO items (
                    name, category, quantity, unit, price,
                    purchase_date, storage, expiry_date, date_source,
                    opened, opened_date, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
                """,
                (
                    item["name"].strip(),
                    item.get("category", "General").strip(),
                    float(item.get("quantity", 1.0)),
                    item.get("unit", "pack").strip(),
                    item.get("price"),
                    item.get("purchase_date", date.today().isoformat()),
                    item.get("storage", "fridge").lower().strip(),
                    item["expiry_date"],
                    item.get("date_source", "estimated"),
                    int(item.get("opened", 0)),
                    item.get("opened_date"),
                ),
            )
            count += 1
        conn.commit()
    return count


def get_active_items(
    storage_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    db_path: Path = DB_FILE,
) -> List[Dict[str, Any]]:
    """
    Fetches all active items (not used and not thrown).
    Optionally filters by storage place ('fridge', 'room', 'freezer')
    and search keyword in the item's name or category.
    """
    query = "SELECT * FROM items WHERE status = 'active'"
    params: List[Any] = []

    if storage_filter and storage_filter.lower() != "all":
        query += " AND storage = ?"
        params.append(storage_filter.lower().strip())

    if search_query and search_query.strip():
        query += " AND (name LIKE ? OR category LIKE ?)"
        term = f"%{search_query.strip()}%"
        params.extend([term, term])

    query += " ORDER BY expiry_date ASC, name ASC"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_item_by_id(item_id: int, db_path: Path = DB_FILE) -> Optional[Dict[str, Any]]:
    """
    Fetches a single item by its ID.
    Returns a dict representation or None if not found.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_item_status(
    item_id: int,
    status: str,
    db_path: Path = DB_FILE,
) -> bool:
    """
    Updates the status of an item ('used' or 'thrown') and records today's date.
    Returns True if an item was updated.
    """
    today_str = date.today().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE items SET status = ?, status_date = ? WHERE id = ?",
            (status, today_str, item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def mark_item_opened(
    item_id: int,
    new_expiry_date: str,
    db_path: Path = DB_FILE,
) -> bool:
    """
    Marks an item as opened today and updates its expiry date
    according to the opened-pack clock logic.
    """
    today_str = date.today().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE items
            SET opened = 1, opened_date = ?, expiry_date = ?
            WHERE id = ?
            """,
            (today_str, new_expiry_date, item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_item_expiry(
    item_id: int,
    new_expiry_date: str,
    date_source: str = "scanned",
    db_path: Path = DB_FILE,
) -> bool:
    """
    Upgrades or edits an item's expiry date (e.g. from a pack label scan or manual edit).
    Updates date_source to 'scanned' or 'typed'.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE items
            SET expiry_date = ?, date_source = ?
            WHERE id = ?
            """,
            (new_expiry_date, date_source, item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_waste_summary(
    month_prefix: Optional[str] = None,
    db_path: Path = DB_FILE,
) -> Dict[str, Any]:
    """
    Calculates monthly waste and saved statistics.
    Rules:
      - Uses only items where price is NOT NULL and > 0 for waste valuation.
      - Never guesses or estimates missing prices.
      - Returns counts and sums for both 'thrown' and 'used' items.
    """
    if not month_prefix:
        month_prefix = date.today().strftime("%Y-%m")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Thrown items
        cursor.execute(
            """
            SELECT COUNT(*) AS total_thrown,
                   SUM(CASE WHEN price IS NOT NULL AND price > 0 THEN price ELSE 0 END) AS known_thrown_cost,
                   SUM(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 ELSE 0 END) AS priced_thrown_count
            FROM items
            WHERE status = 'thrown' AND status_date LIKE ?
            """,
            (f"{month_prefix}%",),
        )
        thrown_row = cursor.fetchone()

        # Used items (what was saved)
        cursor.execute(
            """
            SELECT COUNT(*) AS total_used,
                   SUM(CASE WHEN price IS NOT NULL AND price > 0 THEN price ELSE 0 END) AS known_used_cost,
                   SUM(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 ELSE 0 END) AS priced_used_count
            FROM items
            WHERE status = 'used' AND status_date LIKE ?
            """,
            (f"{month_prefix}%",),
        )
        used_row = cursor.fetchone()

        # List of thrown items details
        cursor.execute(
            """
            SELECT id, name, category, quantity, unit, price, status_date
            FROM items
            WHERE status = 'thrown' AND status_date LIKE ?
            ORDER BY status_date DESC
            """,
            (f"{month_prefix}%",),
        )
        thrown_items = [dict(r) for r in cursor.fetchall()]

        # List of used items details
        cursor.execute(
            """
            SELECT id, name, category, quantity, unit, price, status_date
            FROM items
            WHERE status = 'used' AND status_date LIKE ?
            ORDER BY status_date DESC
            """,
            (f"{month_prefix}%",),
        )
        used_items = [dict(r) for r in cursor.fetchall()]

        return {
            "month": month_prefix,
            "thrown_count": thrown_row["total_thrown"] if thrown_row else 0,
            "thrown_value": round(thrown_row["known_thrown_cost"] or 0.0, 2) if thrown_row else 0.0,
            "thrown_priced_count": thrown_row["priced_thrown_count"] if thrown_row else 0,
            "used_count": used_row["total_used"] if used_row else 0,
            "used_value": round(used_row["known_used_cost"] or 0.0, 2) if used_row else 0.0,
            "used_priced_count": used_row["priced_used_count"] if used_row else 0,
            "thrown_items": thrown_items,
            "used_items": used_items,
        }


def save_user_override(
    item_name: str,
    category: str,
    storage: str,
    shelf_days: int,
    db_path: Path = DB_FILE,
) -> None:
    """
    Saves or updates a user's custom shelf life override for an item name.
    Next time this item is seen, the app will remember the user's shelf life.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_overrides (item_name, category, storage, shelf_days, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(item_name) DO UPDATE SET
                category = excluded.category,
                storage = excluded.storage,
                shelf_days = excluded.shelf_days,
                updated_at = CURRENT_TIMESTAMP
            """,
            (item_name.lower().strip(), category, storage, shelf_days),
        )
        conn.commit()


def get_user_override(item_name: str, db_path: Path = DB_FILE) -> Optional[Dict[str, Any]]:
    """
    Looks up whether the user previously defined a shelf life override for this item.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user_overrides WHERE item_name = ?",
            (item_name.lower().strip(),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def set_setting(key: str, value: str, db_path: Path = DB_FILE) -> None:
    """
    Saves a configuration key-value pair into the settings table.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def get_setting(key: str, default: str = "", db_path: Path = DB_FILE) -> str:
    """
    Retrieves a configuration value from settings, returning `default` if not present.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return str(row["value"]) if row else default


def clear_all_data(db_path: Path = DB_FILE) -> None:
    """
    Deletes all records from items and user_overrides.
    Settings are preserved.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items")
        cursor.execute("DELETE FROM user_overrides")
        conn.commit()


def load_demo_data(db_path: Path = DB_FILE) -> int:
    """
    Populates the database with 8 realistic demo items for hackathon presentation.
    Includes items in RED (urgent/expired), YELLOW (attention soon), and GREEN (safe).
    Covers different storage locations, date sources, and opened states.
    """
    from datetime import timedelta

    today = date.today()

    demo_items = [
        # RED: Expired 1 day ago (Milk opened)
        {
            "name": "Amul Toned Milk",
            "category": "Dairy",
            "quantity": 1.0,
            "unit": "pack",
            "price": 32.0,
            "purchase_date": (today - timedelta(days=3)).isoformat(),
            "storage": "fridge",
            "expiry_date": (today - timedelta(days=1)).isoformat(),
            "date_source": "estimated",
            "opened": 1,
            "opened_date": (today - timedelta(days=3)).isoformat(),
        },
        # RED: Expires tomorrow (Spinach / Palak)
        {
            "name": "Fresh Spinach (Palak)",
            "category": "Produce",
            "quantity": 1.0,
            "unit": "bunch",
            "price": 25.0,
            "purchase_date": (today - timedelta(days=3)).isoformat(),
            "storage": "fridge",
            "expiry_date": (today + timedelta(days=1)).isoformat(),
            "date_source": "estimated",
            "opened": 0,
            "opened_date": None,
        },
        # RED: Expires in 2 days (Paneer - Scanned from pack!)
        {
            "name": "Malai Paneer",
            "category": "Dairy",
            "quantity": 200.0,
            "unit": "g",
            "price": 95.0,
            "purchase_date": (today - timedelta(days=5)).isoformat(),
            "storage": "fridge",
            "expiry_date": (today + timedelta(days=2)).isoformat(),
            "date_source": "scanned",
            "opened": 0,
            "opened_date": None,
        },
        # YELLOW: Expires in 4 days (Brown Bread)
        {
            "name": "Harvest Brown Bread",
            "category": "Bakery",
            "quantity": 1.0,
            "unit": "loaf",
            "price": 50.0,
            "purchase_date": (today - timedelta(days=2)).isoformat(),
            "storage": "room",
            "expiry_date": (today + timedelta(days=4)).isoformat(),
            "date_source": "scanned",
            "opened": 1,
            "opened_date": (today - timedelta(days=1)).isoformat(),
        },
        # YELLOW: Expires in 5 days (Tomatoes)
        {
            "name": "Country Tomatoes",
            "category": "Produce",
            "quantity": 1.0,
            "unit": "kg",
            "price": 40.0,
            "purchase_date": (today - timedelta(days=2)).isoformat(),
            "storage": "fridge",
            "expiry_date": (today + timedelta(days=5)).isoformat(),
            "date_source": "estimated",
            "opened": 0,
            "opened_date": None,
        },
        # GREEN: Expires in 14 days (Greek Yogurt)
        {
            "name": "Epigamia Greek Yogurt",
            "category": "Dairy",
            "quantity": 2.0,
            "unit": "cups",
            "price": 80.0,
            "purchase_date": today.isoformat(),
            "storage": "fridge",
            "expiry_date": (today + timedelta(days=14)).isoformat(),
            "date_source": "scanned",
            "opened": 0,
            "opened_date": None,
        },
        # GREEN: Expires in 25 days (Farm Eggs)
        {
            "name": "Farm Fresh Eggs",
            "category": "Poultry",
            "quantity": 12.0,
            "unit": "pcs",
            "price": 96.0,
            "purchase_date": (today - timedelta(days=1)).isoformat(),
            "storage": "fridge",
            "expiry_date": (today + timedelta(days=20)).isoformat(),
            "date_source": "typed",
            "opened": 0,
            "opened_date": None,
        },
        # GREEN: Expires in 60 days (Basmati Rice)
        {
            "name": "Daawat Basmati Rice",
            "category": "Pantry",
            "quantity": 5.0,
            "unit": "kg",
            "price": 450.0,
            "purchase_date": (today - timedelta(days=10)).isoformat(),
            "storage": "room",
            "expiry_date": (today + timedelta(days=60)).isoformat(),
            "date_source": "estimated",
            "opened": 1,
            "opened_date": (today - timedelta(days=10)).isoformat(),
        },
    ]

    return add_items_bulk(demo_items, db_path=db_path)
