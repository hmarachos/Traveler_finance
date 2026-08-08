"""Database connection and schema management."""
import sqlite3
import time
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("TRAVELER_DB", DATA_DIR / "traveler.sqlite3"))


def now() -> str:
    """Return current UTC timestamp in ISO format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect() -> sqlite3.Connection:
    """Create database connection with foreign keys enabled."""
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def row_to_dict(row):
    """Convert sqlite3.Row to dictionary."""
    return dict(row) if row else None


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str):
    """Add column to table if it doesn't exist."""
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate():
    """Create database schema if not exists and seed initial data."""
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS trips (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              currency TEXT NOT NULL DEFAULT 'EUR',
              access_code TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS families (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trip_id INTEGER NOT NULL REFERENCES trips(id),
              name TEXT NOT NULL,
              members_count INTEGER NOT NULL CHECK (members_count > 0),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS expenses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trip_id INTEGER NOT NULL REFERENCES trips(id),
              description TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              category TEXT NOT NULL DEFAULT 'Общее',
              paid_by_family_id INTEGER NOT NULL REFERENCES families(id),
              split_method TEXT NOT NULL CHECK (split_method IN ('equal', 'per_person')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS money_transfers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trip_id INTEGER NOT NULL REFERENCES trips(id),
              from_family_id INTEGER NOT NULL REFERENCES families(id),
              to_family_id INTEGER NOT NULL REFERENCES families(id),
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              description TEXT,
              transfer_type TEXT NOT NULL CHECK (transfer_type IN ('transfer', 'advance')),
              created_at TEXT NOT NULL,
              deleted_at TEXT,
              CHECK (from_family_id <> to_family_id)
            );

            CREATE TABLE IF NOT EXISTS loans (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trip_id INTEGER NOT NULL REFERENCES trips(id),
              lender_family_id INTEGER NOT NULL REFERENCES families(id),
              borrower_family_id INTEGER NOT NULL REFERENCES families(id),
              principal_amount_minor INTEGER NOT NULL CHECK (principal_amount_minor > 0),
              remaining_amount_minor INTEGER NOT NULL CHECK (remaining_amount_minor >= 0),
              description TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('active', 'partially_repaid', 'repaid', 'cancelled')),
              deleted_at TEXT,
              CHECK (lender_family_id <> borrower_family_id)
            );

            CREATE TABLE IF NOT EXISTS loan_repayments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              loan_id INTEGER NOT NULL REFERENCES loans(id),
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              created_at TEXT NOT NULL,
              description TEXT
            );
            """
        )
        ensure_column(db, "trips", "deleted_at", "TEXT")
        seed(db)


def seed(db: sqlite3.Connection):
    """Seed database with example trip if empty."""
    count = db.execute("SELECT COUNT(*) AS c FROM trips WHERE deleted_at IS NULL").fetchone()["c"]
    if count:
        return
    stamp = now()
    cur = db.execute(
        "INSERT INTO trips(name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("Италия 2026", "EUR", "IT26X7", stamp, stamp),
    )
    trip_id = cur.lastrowid
    for name, members in [("Ивановы", 4), ("Петровы", 3), ("Сидоровы", 2)]:
        db.execute(
            "INSERT INTO families(trip_id, name, members_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (trip_id, name, members, stamp, stamp),
        )
