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
              owner_user_id INTEGER REFERENCES users(id),
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

            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token_hash TEXT NOT NULL UNIQUE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trip_users (
              trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
              created_at TEXT NOT NULL,
              PRIMARY KEY (trip_id, user_id)
            );
            """
        )
        ensure_column(db, "trips", "owner_user_id", "INTEGER REFERENCES users(id)")
        ensure_column(db, "trips", "deleted_at", "TEXT")
        ensure_column(db, "money_transfers", "updated_at", "TEXT")
        ensure_column(db, "expenses", "created_by_user_id", "INTEGER REFERENCES users(id)")
        ensure_column(db, "money_transfers", "created_by_user_id", "INTEGER REFERENCES users(id)")
        ensure_column(db, "loans", "created_by_user_id", "INTEGER REFERENCES users(id)")
        ensure_column(db, "loan_repayments", "created_by_user_id", "INTEGER REFERENCES users(id)")
        ensure_valid_split_method(db)
        ensure_trip_users(db)
        seed(db)


def ensure_valid_split_method(db: sqlite3.Connection):
    """Allow all currently supported split methods."""
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'expenses'"
    ).fetchone()
    if not row or "paid_only" in (row["sql"] or ""):
        return

    # Check if expenses_old already exists
    old_exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'expenses_old'"
    ).fetchone()
    
    if old_exists:
        # expenses_old already exists, likely from a previous failed migration
        # Check if we have both tables and determine which one to keep
        expenses_count = db.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        expenses_old_count = db.execute("SELECT COUNT(*) FROM expenses_old").fetchone()[0]
        
        if expenses_old_count > expenses_count:
            # expenses_old has more data, replace expenses with it
            db.execute("DROP TABLE IF EXISTS expenses")
            db.execute("ALTER TABLE expenses_old RENAME TO expenses")
        else:
            # expenses has more or equal data, drop expenses_old
            db.execute("DROP TABLE IF EXISTS expenses_old")
            
        # Re-check if we still need to fix the split_method constraint
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'expenses'"
        ).fetchone()
        if "paid_only" not in (row["sql"] or ""):
            # Still need to fix the split_method constraint
            db.execute("ALTER TABLE expenses RENAME TO expenses_old")
            db.execute("""
                CREATE TABLE expenses (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trip_id INTEGER NOT NULL REFERENCES trips(id),
                  description TEXT NOT NULL,
                  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
                  category TEXT NOT NULL DEFAULT 'Общее',
                  paid_by_family_id INTEGER NOT NULL REFERENCES families(id),
                  split_method TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  deleted_at TEXT
                )
            """)
            db.execute("INSERT INTO expenses SELECT * FROM expenses_old")
            db.execute("DROP TABLE expenses_old")
    else:
        # Normal migration path
        db.execute("ALTER TABLE expenses RENAME TO expenses_old")
        db.execute("""
            CREATE TABLE expenses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trip_id INTEGER NOT NULL REFERENCES trips(id),
              description TEXT NOT NULL,
              amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
              category TEXT NOT NULL DEFAULT 'Общее',
              paid_by_family_id INTEGER NOT NULL REFERENCES families(id),
              split_method TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT
            )
        """)
        db.execute("INSERT INTO expenses SELECT * FROM expenses_old")
        db.execute("DROP TABLE expenses_old")


def ensure_trip_users(db: sqlite3.Connection):
    """Backfill trip membership from existing owner_user_id values."""
    stamp = now()
    db.execute(
        """
        INSERT OR IGNORE INTO trip_users(trip_id, user_id, role, created_at)
        SELECT id, owner_user_id, 'owner', ?
        FROM trips
        WHERE owner_user_id IS NOT NULL
        """,
        (stamp,),
    )


def seed(db: sqlite3.Connection):
    """Seed database with example trip if empty."""
    count = db.execute("SELECT COUNT(*) AS c FROM trips WHERE deleted_at IS NULL").fetchone()["c"]
    if count:
        return
    stamp = now()
    cur = db.execute(
        "INSERT INTO trips(owner_user_id, name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (None, "Италия 2026", "EUR", "IT26X7", stamp, stamp),
    )
    trip_id = cur.lastrowid
    for name, members in [("Ивановы", 4), ("Петровы", 3), ("Сидоровы", 2)]:
        db.execute(
            "INSERT INTO families(trip_id, name, members_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (trip_id, name, members, stamp, stamp),
        )
