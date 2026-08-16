#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from models.auth import Auth
from models.expense import Expense
from models.loan import Loan
from models.trip import Trip


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("TRAVELER_DB", DATA_DIR / "traveler.sqlite3"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def row_to_dict(row):
    return dict(row) if row else None


def parse_money(value) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "").strip().replace(" ", "").replace(",", ".")
    if not re.match(r"^\d+(\.\d{1,2})?$", text):
        raise ValueError("Invalid amount")
    whole, _, cents = text.partition(".")
    return int(whole) * 100 + int((cents + "00")[:2])


def divide_amount(amount: int, weights: list[int]) -> list[int]:
    total = sum(weights)
    if total <= 0:
        raise ValueError("Split weights must be positive")
    shares = [(amount * weight) // total for weight in weights]
    remainder = amount - sum(shares)
    for idx in range(remainder):
        shares[idx % len(shares)] += 1
    return shares


def migrate():
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
              split_method TEXT NOT NULL,
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
              updated_at TEXT,
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


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_valid_split_method(db: sqlite3.Connection):
    """Ensure split_method column accepts all valid values."""
    # Get current CHECK constraint
    try:
        result = db.execute("PRAGMA table_info(expenses)").fetchall()
        columns_in_old = [row[1] for row in result]
        
        # Only recreate if created_by_user_id doesn't exist
        if 'created_by_user_id' not in columns_in_old:
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
                  deleted_at TEXT,
                  created_by_user_id INTEGER REFERENCES users(id)
                )
            """)
            db.execute("INSERT INTO expenses SELECT id, trip_id, description, amount_minor, category, paid_by_family_id, COALESCE(split_method, 'equal'), created_at, updated_at, deleted_at, NULL FROM expenses_old")
            db.execute("DROP TABLE expenses_old")
    except sqlite3.OperationalError:
        pass  # Table doesn't exist or other error - will be created by migrate()


def ensure_trip_users(db: sqlite3.Connection):
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


def get_trip(db, trip_id: int, user_id: int | None = None):
    if user_id is None:
        trip = row_to_dict(db.execute("SELECT * FROM trips WHERE id = ? AND deleted_at IS NULL", (trip_id,)).fetchone())
    else:
        trip = row_to_dict(
            db.execute(
                """
                SELECT DISTINCT t.*
                FROM trips t
                LEFT JOIN trip_users tu ON tu.trip_id = t.id
                WHERE t.id = ? AND t.deleted_at IS NULL
                  AND (t.owner_user_id = ? OR tu.user_id = ?)
                """,
                (trip_id, user_id, user_id),
            ).fetchone()
        )
    if not trip:
        raise LookupError("Trip not found")
    return trip


def validate_trip_payload(body):
    name = body["name"].strip()
    currency = body.get("currency", "EUR").strip().upper()
    access_code = body["access_code"].strip().upper()
    if not name:
        raise ValueError("Trip name is required")
    if not re.match(r"^[A-Z]{3}$", currency):
        raise ValueError("Currency must be a 3-letter code")
    if not re.match(r"^[A-Z0-9_-]{3,24}$", access_code):
        raise ValueError("Access code must contain 3-24 letters, digits, _ or -")
    return name, currency, access_code


def families(db, trip_id: int):
    return [
        row_to_dict(r)
        for r in db.execute(
            "SELECT * FROM families WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id", (trip_id,)
        )
    ]


def family_financial_refs(db: sqlite3.Connection, trip_id: int, family_id: int) -> int:
    checks = [
        ("expenses", "paid_by_family_id = ?"),
        ("money_transfers", "from_family_id = ? OR to_family_id = ?"),
        ("loans", "lender_family_id = ? OR borrower_family_id = ?"),
    ]
    total = 0
    for table, where in checks:
        params = (family_id, family_id) if " OR " in where else (family_id,)
        row = db.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE trip_id = ? AND ({where})",
            (trip_id, *params),
        ).fetchone()
        total += row["c"]
    return total


def compute_summary(db, trip_id: int):
    trip = get_trip(db, trip_id)
    fams = families(db, trip_id)
    by_id = {f["id"]: f for f in fams}
    stats = {
        f["id"]: {
            "family": f,
            "expense_paid_minor": 0,
            "expense_share_minor": 0,
            "expense_balance_minor": 0,
            "transfers_sent_minor": 0,
            "transfers_received_minor": 0,
            "advances_sent_minor": 0,
            "advances_received_minor": 0,
            "loans_given_minor": 0,
            "loans_taken_minor": 0,
            "loan_receivable_minor": 0,
            "loan_payable_minor": 0,
        }
        for f in fams
    }
    total_expenses = 0
    for expense in db.execute(
        "SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id", (trip_id,)
    ):
        paid_by = expense["paid_by_family_id"]
        if paid_by in stats:
            stats[paid_by]["expense_paid_minor"] += expense["amount_minor"]
        total_expenses += expense["amount_minor"]
        if expense["split_method"] == "paid_only":
            # Only the paying family bears the expense
            if paid_by in stats:
                stats[paid_by]["expense_share_minor"] += expense["amount_minor"]
        else:
            weights = [1 for _ in fams] if expense["split_method"] == "equal" else [f["members_count"] for f in fams]
            shares = divide_amount(expense["amount_minor"], weights)
            for family, share in zip(fams, shares):
                stats[family["id"]]["expense_share_minor"] += share

    for stat in stats.values():
        stat["expense_balance_minor"] = stat["expense_paid_minor"] - stat["expense_share_minor"]

    transfer_total = 0
    advance_total = 0
    for transfer in db.execute(
        "SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id", (trip_id,)
    ):
        amount = transfer["amount_minor"]
        if transfer["transfer_type"] == "advance":
            advance_total += amount
            sent_key, received_key = "advances_sent_minor", "advances_received_minor"
        else:
            transfer_total += amount
            sent_key, received_key = "transfers_sent_minor", "transfers_received_minor"
        if transfer["from_family_id"] in stats:
            stats[transfer["from_family_id"]][sent_key] += amount
        if transfer["to_family_id"] in stats:
            stats[transfer["to_family_id"]][received_key] += amount

    loan_total = 0
    open_loan_total = 0
    loan_obligations = []
    for loan in db.execute(
        "SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL AND status <> 'cancelled' ORDER BY id",
        (trip_id,),
    ):
        loan_total += loan["principal_amount_minor"]
        open_loan_total += loan["remaining_amount_minor"]
        lender = loan["lender_family_id"]
        borrower = loan["borrower_family_id"]
        if lender in stats:
            stats[lender]["loans_given_minor"] += loan["principal_amount_minor"]
            stats[lender]["loan_receivable_minor"] += loan["remaining_amount_minor"]
        if borrower in stats:
            stats[borrower]["loans_taken_minor"] += loan["principal_amount_minor"]
            stats[borrower]["loan_payable_minor"] += loan["remaining_amount_minor"]
        if loan["remaining_amount_minor"] > 0:
            loan_obligations.append(
                {
                    "from_family_id": borrower,
                    "from_family_name": by_id.get(borrower, {}).get("name", "Unknown"),
                    "to_family_id": lender,
                    "to_family_name": by_id.get(lender, {}).get("name", "Unknown"),
                    "amount_minor": loan["remaining_amount_minor"],
                    "loan_id": loan["id"],
                }
            )

    settlements = expense_settlements(stats)
    return {
        "trip": trip,
        "families": fams,
        "totals": {
            "expenses_minor": total_expenses,
            "paid_minor": sum(s["expense_paid_minor"] for s in stats.values()),
            "loans_principal_minor": loan_total,
            "loans_open_minor": open_loan_total,
            "transfers_minor": transfer_total,
            "advances_minor": advance_total,
            "members_count": sum(f["members_count"] for f in fams),
            "families_count": len(fams),
        },
        "family_stats": list(stats.values()),
        "expense_settlements": settlements,
        "loan_obligations": loan_obligations,
    }


def expense_settlements(stats):
    debtors = []
    creditors = []
    for family_id, stat in stats.items():
        balance = stat["expense_balance_minor"]
        item = {"family_id": family_id, "family_name": stat["family"]["name"], "amount": abs(balance)}
        if balance < 0:
            debtors.append(item)
        elif balance > 0:
            creditors.append(item)
    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)
    settlements = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i]["amount"], creditors[j]["amount"])
        if amount:
            settlements.append(
                {
                    "from_family_id": debtors[i]["family_id"],
                    "from_family_name": debtors[i]["family_name"],
                    "to_family_id": creditors[j]["family_id"],
                    "to_family_name": creditors[j]["family_name"],
                    "amount_minor": amount,
                }
            )
        debtors[i]["amount"] -= amount
        creditors[j]["amount"] -= amount
        if debtors[i]["amount"] == 0:
            i += 1
        if creditors[j]["amount"] == 0:
            j += 1
    return settlements


def journal(db, trip_id: int):
    items = []
    fams = {f["id"]: f["name"] for f in families(db, trip_id)}
    # Get all users for author names
    users = {
        r["id"]: r["username"]
        for r in db.execute("SELECT id, username FROM users")
    }
    for r in db.execute("SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        # Handle both cases: column exists or doesn't exist
        created_by_user_id = None
        try:
            created_by_user_id = r["created_by_user_id"]
        except IndexError:
            pass
        author = users.get(created_by_user_id) if created_by_user_id else "Система"
        items.append(
            {
                "id": r["id"],
                "type": "expense",
                "title": r["description"],
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": f"Оплатили: {fams.get(r['paid_by_family_id'], 'Unknown')} · {r['category']}",
            }
        )
    for r in db.execute("SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        created_by_user_id = None
        try:
            created_by_user_id = r["created_by_user_id"]
        except IndexError:
            pass
        author = users.get(created_by_user_id) if created_by_user_id else "Система"
        items.append(
            {
                "id": r["id"],
                "type": "advance" if r["transfer_type"] == "advance" else "transfer",
                "title": r["description"] or ("Аванс" if r["transfer_type"] == "advance" else "Перевод"),
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": f"{fams.get(r['from_family_id'], 'Unknown')} → {fams.get(r['to_family_id'], 'Unknown')}",
            }
        )
    for r in db.execute("SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        created_by_user_id = None
        try:
            created_by_user_id = r["created_by_user_id"]
        except IndexError:
            pass
        author = users.get(created_by_user_id) if created_by_user_id else "Система"
        items.append(
            {
                "id": r["id"],
                "type": "loan",
                "title": r["description"] or "Заем",
                "amount_minor": r["principal_amount_minor"],
                "created_at": r["created_at"],
                "remaining_amount_minor": r["remaining_amount_minor"],
                "author": author,
                "meta": f"{fams.get(r['borrower_family_id'], 'Unknown')} должны {fams.get(r['lender_family_id'], 'Unknown')}",
            }
        )
    for r in db.execute(
        """
        SELECT lr.*, l.trip_id, l.lender_family_id, l.borrower_family_id
        FROM loan_repayments lr JOIN loans l ON l.id = lr.loan_id
        WHERE l.trip_id = ?
        """,
        (trip_id,),
    ):
        created_by_user_id = None
        try:
            created_by_user_id = r["created_by_user_id"]
        except IndexError:
            pass
        author = users.get(created_by_user_id) if created_by_user_id else "Система"
        items.append(
            {
                "id": r["id"],
                "type": "loan_repayment",
                "title": r["description"] or "Возврат займа",
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": f"{fams.get(r['borrower_family_id'], 'Unknown')} → {fams.get(r['lender_family_id'], 'Unknown')}",
            }
        )
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.route()

    def do_HEAD(self):
        self.route(head_only=True)

    def do_POST(self):
        self.route()

    def do_PUT(self):
        self.route()

    def do_DELETE(self):
        self.route()

    def route(self, head_only=False):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path.startswith("/api/"):
                return self.api(path, parse_qs(parsed.query), head_only)
            return self.static(path, head_only)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except LookupError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            import traceback
            print(f"ERROR: {exc}")
            print(traceback.format_exc())
            self.send_json({"error": "Internal server error", "detail": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def api(self, path, query, head_only=False):
        with connect() as db:
            if path == "/api/auth/status" and self.command == "GET":
                user = Auth.user_from_cookie(self.headers.get("Cookie"))
                return self.send_json({
                    "authenticated": bool(user),
                    "user": user,
                    "users_count": Auth.users_count(),
                })
            if path == "/api/auth/register" and self.command == "POST":
                body = self.read_json()
                user = Auth.register(body.get("username", ""), body.get("password", ""))
                token = Auth.create_session(user["id"])
                return self.send_json(
                    {"user": user},
                    HTTPStatus.CREATED,
                    headers={"Set-Cookie": Auth.session_cookie(token)},
                )
            if path == "/api/auth/login" and self.command == "POST":
                body = self.read_json()
                user = Auth.login(body.get("username", ""), body.get("password", ""))
                token = Auth.create_session(user["id"])
                return self.send_json({"user": user}, headers={"Set-Cookie": Auth.session_cookie(token)})
            if path == "/api/auth/logout" and self.command == "POST":
                Auth.logout(self.headers.get("Cookie"))
                return self.send_json({"ok": True}, headers={"Set-Cookie": Auth.clear_cookie()})

            current_user = Auth.user_from_cookie(self.headers.get("Cookie"))
            if not current_user:
                return self.send_json({"error": "Требуется вход"}, HTTPStatus.UNAUTHORIZED)

            if path == "/api/trips" and self.command == "GET":
                trips = [
                    row_to_dict(r)
                    for r in db.execute(
                        """
                        SELECT DISTINCT t.*
                        FROM trips t
                        LEFT JOIN trip_users tu ON tu.trip_id = t.id
                        WHERE t.deleted_at IS NULL
                          AND (t.owner_user_id = ? OR tu.user_id = ?)
                        ORDER BY t.id
                        """,
                        (current_user["id"], current_user["id"]),
                    )
                ]
                return self.send_json({"trips": trips})
            if path == "/api/trips" and self.command == "POST":
                body = self.read_json()
                stamp = now()
                name, currency, access_code = validate_trip_payload(body)
                try:
                    cur = db.execute(
                        "INSERT INTO trips(owner_user_id, name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (current_user["id"], name, currency, access_code, stamp, stamp),
                    )
                    db.execute(
                        "INSERT INTO trip_users(trip_id, user_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                        (cur.lastrowid, current_user["id"], stamp),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("Access code is already used by another trip")
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)

            match = re.match(r"^/api/trips/(\d+)(?:/(.*))?$", path)
            if not match:
                return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            trip_id = int(match.group(1))
            tail = match.group(2) or ""
            get_trip(db, trip_id, current_user["id"])

            if tail == "" and self.command == "GET":
                return self.send_json({"trip": get_trip(db, trip_id, current_user["id"])})
            if tail == "" and self.command == "PUT":
                body = self.read_json()
                name, currency, access_code = validate_trip_payload(body)
                try:
                    db.execute(
                        """
                        UPDATE trips
                        SET name = ?, currency = ?, access_code = ?, updated_at = ?
                        WHERE id = ? AND deleted_at IS NULL
                          AND (
                            owner_user_id = ?
                            OR EXISTS (
                              SELECT 1 FROM trip_users
                              WHERE trip_users.trip_id = trips.id AND trip_users.user_id = ?
                            )
                          )
                        """,
                        (name, currency, access_code, now(), trip_id, current_user["id"], current_user["id"]),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("Access code is already used by another trip")
                return self.send_json({"ok": True})
            if tail == "" and self.command == "DELETE":
                Trip.require_owner(trip_id, current_user["id"])
                active_count = db.execute(
                    "SELECT COUNT(*) AS c FROM trips WHERE owner_user_id = ? AND deleted_at IS NULL",
                    (current_user["id"],),
                ).fetchone()["c"]
                if active_count <= 1:
                    raise ValueError("At least one trip must remain")
                stamp = now()
                db.execute(
                    "UPDATE trips SET deleted_at = ?, updated_at = ? WHERE id = ? AND owner_user_id = ? AND deleted_at IS NULL",
                    (stamp, stamp, trip_id, current_user["id"]),
                )
                return self.send_json({"ok": True})

            if tail == "users" and self.command == "GET":
                return self.send_json({"users": Trip.users(trip_id)})
            if tail == "users" and self.command == "POST":
                Trip.require_owner(trip_id, current_user["id"])
                body = self.read_json()
                user = Trip.add_user(trip_id, body.get("username", ""), body.get("role", "member"))
                return self.send_json({"user": user}, HTTPStatus.CREATED)
            trip_user_delete = re.match(r"^users/(\d+)$", tail)
            if trip_user_delete and self.command == "DELETE":
                Trip.require_owner(trip_id, current_user["id"])
                Trip.remove_user(trip_id, int(trip_user_delete.group(1)))
                return self.send_json({"ok": True})

            if tail == "summary" and self.command == "GET":
                return self.send_json(compute_summary(db, trip_id))
            if tail == "families" and self.command == "GET":
                return self.send_json({"families": families(db, trip_id)})
            if tail == "families" and self.command == "POST":
                body = self.read_json()
                name = body["name"].strip()
                members_count = int(body["members_count"])
                if not name:
                    raise ValueError("Family name is required")
                if members_count <= 0:
                    raise ValueError("Members count must be positive")
                stamp = now()
                cur = db.execute(
                    "INSERT INTO families(trip_id, name, members_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (trip_id, name, members_count, stamp, stamp),
                )
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
            if tail == "categories" and self.command == "GET":
                # Return standard expense categories
                categories = Expense.get_standard_categories()
                return self.send_json({"categories": categories}, HTTPStatus.OK)
            if tail == "expenses" and self.command == "POST":
                body = self.read_json()
                split_method = body.get("split_method", "equal")
                if split_method not in ("equal", "per_person", "paid_only"):
                    raise ValueError("Invalid split_method")
                stamp = now()
                try:
                    # Check if created_by_user_id column exists
                    columns = {row[1] for row in db.execute("PRAGMA table_info(expenses)")}
                    print(f"DEBUG: Expense columns: {columns}")
                    print(f"DEBUG: created_by_user_id in columns: {'created_by_user_id' in columns}")
                    print(f"DEBUG: current_user: {current_user}")
                    if "created_by_user_id" in columns:
                        # Insert with created_by_user_id
                        print(f"DEBUG: Inserting WITH created_by_user_id={current_user['id']}")
                        db.execute(
                            """
                            INSERT INTO expenses(trip_id, description, amount_minor, category, paid_by_family_id, split_method, created_by_user_id, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                trip_id,
                                body["description"].strip(),
                                parse_money(body["amount"]),
                                body.get("category", "Общее").strip() or "Общее",
                                int(body["paid_by_family_id"]),
                                split_method,
                                current_user["id"],
                                stamp,
                                stamp,
                            ),
                        )
                    else:
                        # Insert without created_by_user_id if column doesn't exist
                        print(f"DEBUG: Inserting WITHOUT created_by_user_id")
                        db.execute(
                            """
                            INSERT INTO expenses(trip_id, description, amount_minor, category, paid_by_family_id, split_method, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                trip_id,
                                body["description"].strip(),
                                parse_money(body["amount"]),
                                body.get("category", "Общее").strip() or "Общее",
                                int(body["paid_by_family_id"]),
                                split_method,
                                stamp,
                                stamp,
                            ),
                        )
                    expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                    return self.send_json({"id": expense_id}, HTTPStatus.CREATED)
                except Exception as e:
                    import traceback
                    print(f"Error creating expense: {e}")
                    print(traceback.format_exc())
                    raise
            
            expense_edit = re.match(r"^expenses/(\d+)$", tail)
            if expense_edit and self.command == "PUT":
                expense_id = int(expense_edit.group(1))
                body = self.read_json()
                split_method = body.get("split_method", "equal")
                if split_method not in ("equal", "per_person", "paid_only"):
                    raise ValueError("Invalid split_method")
                expense = row_to_dict(
                    db.execute(
                        "SELECT * FROM expenses WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (expense_id, trip_id),
                    ).fetchone()
                )
                if not expense:
                    raise LookupError("Expense not found")
                stamp = now()
                db.execute(
                    """
                    UPDATE expenses
                    SET description = ?, amount_minor = ?, category = ?, paid_by_family_id = ?, split_method = ?, updated_at = ?
                    WHERE id = ? AND trip_id = ?
                    """,
                    (
                        body["description"].strip(),
                        parse_money(body["amount"]),
                        body.get("category", "Общее").strip() or "Общее",
                        int(body["paid_by_family_id"]),
                        split_method,
                        stamp,
                        expense_id,
                        trip_id,
                    ),
                )
                return self.send_json({"ok": True})
            
            if tail == "transfers" and self.command == "POST":
                body = self.read_json()
                stamp = now()
                cur = db.execute(
                    """
                    INSERT INTO money_transfers(trip_id, from_family_id, to_family_id, amount_minor, description, transfer_type, created_by_user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trip_id,
                        int(body["from_family_id"]),
                        int(body["to_family_id"]),
                        parse_money(body["amount"]),
                        body.get("description", "").strip(),
                        body["transfer_type"],
                        current_user["id"],
                        stamp,
                        stamp,
                    ),
                )
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
            
            transfer_edit = re.match(r"^transfers/(\d+)$", tail)
            if transfer_edit and self.command == "PUT":
                transfer_id = int(transfer_edit.group(1))
                body = self.read_json()
                transfer = row_to_dict(
                    db.execute(
                        "SELECT * FROM money_transfers WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (transfer_id, trip_id),
                    ).fetchone()
                )
                if not transfer:
                    raise LookupError("Transfer not found")
                stamp = now()
                db.execute(
                    """
                    UPDATE money_transfers
                    SET from_family_id = ?, to_family_id = ?, amount_minor = ?, description = ?, transfer_type = ?, updated_at = ?
                    WHERE id = ? AND trip_id = ?
                    """,
                    (
                        int(body["from_family_id"]),
                        int(body["to_family_id"]),
                        parse_money(body["amount"]),
                        body.get("description", "").strip(),
                        body["transfer_type"],
                        stamp,
                        transfer_id,
                        trip_id,
                    ),
                )
                return self.send_json({"ok": True})
            if tail == "loans" and self.command == "GET":
                loans = [row_to_dict(r) for r in db.execute("SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id DESC", (trip_id,))]
                for loan in loans:
                    loan["repayments"] = [
                        row_to_dict(r)
                        for r in db.execute("SELECT * FROM loan_repayments WHERE loan_id = ? ORDER BY id", (loan["id"],))
                    ]
                return self.send_json({"loans": loans})
            if tail == "loans" and self.command == "POST":
                body = self.read_json()
                loan_id = Loan.create(
                    trip_id,
                    int(body["lender_family_id"]),
                    int(body["borrower_family_id"]),
                    parse_money(body["amount"]),
                    body.get("description", "").strip(),
                    current_user["id"],
                )
                return self.send_json({"id": loan_id}, HTTPStatus.CREATED)
            
            loan_edit = re.match(r"^loans/(\d+)$", tail)
            if loan_edit and self.command == "PUT":
                loan_id = int(loan_edit.group(1))
                body = self.read_json()
                loan = row_to_dict(
                    db.execute(
                        "SELECT * FROM loans WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (loan_id, trip_id),
                    ).fetchone()
                )
                if not loan:
                    raise LookupError("Loan not found")
                Loan.update(
                    trip_id,
                    loan_id,
                    int(body["lender_family_id"]),
                    int(body["borrower_family_id"]),
                    parse_money(body["amount"]),
                    body.get("description", "").strip(),
                )
                return self.send_json({"ok": True})
            if tail == "journal" and self.command == "GET":
                return self.send_json({"items": journal(db, trip_id)})

            loan_repay = re.match(r"^loans/(\d+)/repayments$", tail)
            if loan_repay and self.command == "POST":
                loan_id = int(loan_repay.group(1))
                body = self.read_json()
                loan = row_to_dict(
                    db.execute(
                        "SELECT * FROM loans WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (loan_id, trip_id),
                    ).fetchone()
                )
                if not loan:
                    raise LookupError("Loan not found")
                if loan["status"] in ("repaid", "cancelled"):
                    raise ValueError("Loan is not active")
                amount = parse_money(body["amount"])
                if amount > loan["remaining_amount_minor"]:
                    raise ValueError("Repayment cannot exceed remaining loan amount")
                stamp = now()
                remaining = loan["remaining_amount_minor"] - amount
                status = "repaid" if remaining == 0 else "partially_repaid"
                db.execute(
                    "INSERT INTO loan_repayments(loan_id, amount_minor, created_at, description, created_by_user_id) VALUES (?, ?, ?, ?, ?)",
                    (loan_id, amount, stamp, body.get("description", "").strip(), current_user["id"]),
                )
                db.execute(
                    "UPDATE loans SET remaining_amount_minor = ?, status = ?, updated_at = ? WHERE id = ?",
                    (remaining, status, stamp, loan_id),
                )
                return self.send_json({"remaining_amount_minor": remaining, "status": status}, HTTPStatus.CREATED)

            family_edit = re.match(r"^families/(\d+)$", tail)
            if family_edit and self.command == "PUT":
                family_id = int(family_edit.group(1))
                body = self.read_json()
                name = body["name"].strip()
                members_count = int(body["members_count"])
                
                if not name:
                    raise ValueError("Family name is required")
                if members_count <= 0:
                    raise ValueError("Members count must be positive")
                
                family = row_to_dict(
                    db.execute(
                        "SELECT * FROM families WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (family_id, trip_id),
                    ).fetchone()
                )
                if not family:
                    raise LookupError("Family not found")
                
                db.execute(
                    "UPDATE families SET name = ?, members_count = ?, updated_at = ? WHERE id = ? AND trip_id = ?",
                    (name, members_count, now(), family_id, trip_id),
                )
                return self.send_json({"ok": True})
                
            family_delete = re.match(r"^families/(\d+)$", tail)
            if family_delete and self.command == "DELETE":
                family_id = int(family_delete.group(1))
                family = row_to_dict(
                    db.execute(
                        "SELECT * FROM families WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                        (family_id, trip_id),
                    ).fetchone()
                )
                if not family:
                    raise LookupError("Family not found")
                if len(families(db, trip_id)) <= 1:
                    raise ValueError("At least one family must remain in the trip")
                if family_financial_refs(db, trip_id, family_id):
                    return self.send_json(
                        {"error": "Family has financial history and cannot be deleted"},
                        HTTPStatus.CONFLICT,
                    )
                db.execute(
                    "UPDATE families SET deleted_at = ?, updated_at = ? WHERE id = ? AND trip_id = ?",
                    (now(), now(), family_id, trip_id),
                )
                return self.send_json({"ok": True})

            soft_delete = re.match(r"^(expenses|transfers|loans)/(\d+)$", tail)
            if soft_delete and self.command == "DELETE":
                table = {"expenses": "expenses", "transfers": "money_transfers", "loans": "loans"}[soft_delete.group(1)]
                db.execute(f"UPDATE {table} SET deleted_at = ? WHERE id = ? AND trip_id = ?", (now(), int(soft_delete.group(2)), trip_id))
                return self.send_json({"ok": True})

        return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def static(self, path, head_only=False):
        if path in ("", "/"):
            path = "/index.html"
        target = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or target.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/plain"
        if target.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif target.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        elif target.suffix == ".svg":
            content_type = "image/svg+xml"
        elif target.suffix == ".ico":
            content_type = "image/x-icon"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            self.wfile.write(target.read_bytes())

    def send_json(self, payload, status=HTTPStatus.OK, head_only=False, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    migrate()
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Traveler Finance is running on http://127.0.0.1:{port}")
    server.serve_forever()
