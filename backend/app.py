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


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed(db: sqlite3.Connection):
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


def get_trip(db, trip_id: int):
    trip = row_to_dict(db.execute("SELECT * FROM trips WHERE id = ? AND deleted_at IS NULL", (trip_id,)).fetchone())
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
    for r in db.execute("SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        items.append(
            {
                "type": "expense",
                "title": r["description"],
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "meta": f"Оплатили: {fams.get(r['paid_by_family_id'], 'Unknown')} · {r['category']} · {r['split_method']}",
            }
        )
    for r in db.execute("SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        items.append(
            {
                "type": "advance" if r["transfer_type"] == "advance" else "transfer",
                "title": r["description"] or ("Аванс" if r["transfer_type"] == "advance" else "Перевод"),
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "meta": f"{fams.get(r['from_family_id'], 'Unknown')} → {fams.get(r['to_family_id'], 'Unknown')}",
            }
        )
    for r in db.execute("SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL", (trip_id,)):
        items.append(
            {
                "type": "loan",
                "title": r["description"] or "Заем",
                "amount_minor": r["principal_amount_minor"],
                "created_at": r["created_at"],
                "remaining_amount_minor": r["remaining_amount_minor"],
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
        items.append(
            {
                "type": "loan_repayment",
                "title": r["description"] or "Возврат займа",
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
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
            self.send_json({"error": "Internal server error", "detail": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def api(self, path, query, head_only=False):
        with connect() as db:
            if path == "/api/trips" and self.command == "GET":
                trips = [row_to_dict(r) for r in db.execute("SELECT * FROM trips WHERE deleted_at IS NULL ORDER BY id")]
                return self.send_json({"trips": trips})
            if path == "/api/trips" and self.command == "POST":
                body = self.read_json()
                stamp = now()
                name, currency, access_code = validate_trip_payload(body)
                try:
                    cur = db.execute(
                        "INSERT INTO trips(name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (name, currency, access_code, stamp, stamp),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("Access code is already used by another trip")
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)

            match = re.match(r"^/api/trips/(\d+)(?:/(.*))?$", path)
            if not match:
                return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            trip_id = int(match.group(1))
            tail = match.group(2) or ""
            get_trip(db, trip_id)

            if tail == "" and self.command == "GET":
                return self.send_json({"trip": get_trip(db, trip_id)})
            if tail == "" and self.command == "PUT":
                body = self.read_json()
                name, currency, access_code = validate_trip_payload(body)
                try:
                    db.execute(
                        """
                        UPDATE trips
                        SET name = ?, currency = ?, access_code = ?, updated_at = ?
                        WHERE id = ? AND deleted_at IS NULL
                        """,
                        (name, currency, access_code, now(), trip_id),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("Access code is already used by another trip")
                return self.send_json({"ok": True})
            if tail == "" and self.command == "DELETE":
                active_count = db.execute("SELECT COUNT(*) AS c FROM trips WHERE deleted_at IS NULL").fetchone()["c"]
                if active_count <= 1:
                    raise ValueError("At least one trip must remain")
                stamp = now()
                db.execute(
                    "UPDATE trips SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
                    (stamp, stamp, trip_id),
                )
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
            if tail == "expenses" and self.command == "POST":
                body = self.read_json()
                stamp = now()
                cur = db.execute(
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
                        body["split_method"],
                        stamp,
                        stamp,
                    ),
                )
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
            if tail == "transfers" and self.command == "POST":
                body = self.read_json()
                stamp = now()
                cur = db.execute(
                    """
                    INSERT INTO money_transfers(trip_id, from_family_id, to_family_id, amount_minor, description, transfer_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trip_id,
                        int(body["from_family_id"]),
                        int(body["to_family_id"]),
                        parse_money(body["amount"]),
                        body.get("description", "").strip(),
                        body["transfer_type"],
                        stamp,
                    ),
                )
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
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
                stamp = now()
                amount = parse_money(body["amount"])
                cur = db.execute(
                    """
                    INSERT INTO loans(trip_id, lender_family_id, borrower_family_id, principal_amount_minor, remaining_amount_minor, description, created_at, updated_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    """,
                    (
                        trip_id,
                        int(body["lender_family_id"]),
                        int(body["borrower_family_id"]),
                        amount,
                        amount,
                        body.get("description", "").strip(),
                        stamp,
                        stamp,
                    ),
                )
                return self.send_json({"id": cur.lastrowid}, HTTPStatus.CREATED)
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
                    "INSERT INTO loan_repayments(loan_id, amount_minor, created_at, description) VALUES (?, ?, ?, ?)",
                    (loan_id, amount, stamp, body.get("description", "").strip()),
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

    def send_json(self, payload, status=HTTPStatus.OK, head_only=False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
