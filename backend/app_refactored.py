#!/usr/bin/env python3
"""Traveler Finance API Server - Refactored Version"""
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import re

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import migrate, Trip, Family, Expense, MoneyTransfer, Loan
from services import SummaryService, JournalService
from utils import parse_money, validate_trip_payload, validate_family_payload

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"


class TravelerFinanceHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Traveler Finance API."""
    
    def do_GET(self):
        """Handle GET requests."""
        self.route()
    
    def do_HEAD(self):
        """Handle HEAD requests."""
        self.route(head_only=True)
    
    def do_POST(self):
        """Handle POST requests."""
        self.route()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self.route()
    
    def do_PUT(self):
        """Handle PUT requests."""
        self.route()
    
    def route(self, head_only=False):
        """Route request to appropriate handler."""
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
            self.send_json(
                {"error": "Internal server error", "detail": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def read_json(self) -> dict:
        """Read and parse JSON request body."""
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))
    
    def send_json(self, payload: dict, status=HTTPStatus.OK, head_only=False):
        """Send JSON response."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        
        if not head_only:
            self.wfile.write(body)
    
    def api(self, path: str, query: dict, head_only=False):
        """Handle API requests."""
        # Trips list
        if path == "/api/trips" and self.command == "GET":
            trips = Trip.get_all()
            return self.send_json({"trips": trips})
        
        # Create trip
        if path == "/api/trips" and self.command == "POST":
            body = self.read_json()
            name, currency, access_code = validate_trip_payload(body)
            trip_id = Trip.create(name, currency, access_code)
            return self.send_json({"id": trip_id}, HTTPStatus.CREATED)
        
        # Parse trip ID from path
        match = re.match(r"^/api/trips/(\d+)(?:/(.*))?$", path)
        if not match:
            return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        
        trip_id = int(match.group(1))
        tail = match.group(2) or ""
        
        # Verify trip exists
        Trip.get_by_id(trip_id)
        
        # Get trip details
        if tail == "" and self.command == "GET":
            trip = Trip.get_by_id(trip_id)
            return self.send_json({"trip": trip})
        
        # Update trip
        if tail == "" and self.command == "PUT":
            body = self.read_json()
            name, currency, access_code = validate_trip_payload(body)
            Trip.update(trip_id, name, currency, access_code)
            return self.send_json({"ok": True})
        
        # Delete trip
        if tail == "" and self.command == "DELETE":
            Trip.soft_delete(trip_id)
            return self.send_json({"ok": True})
        
        # Trip summary
        if tail == "summary" and self.command == "GET":
            summary = SummaryService.compute(trip_id)
            return self.send_json(summary)
        
        # Families list
        if tail == "families" and self.command == "GET":
            families = Family.get_all_for_trip(trip_id)
            return self.send_json({"families": families})
        
        # Create family
        if tail == "families" and self.command == "POST":
            body = self.read_json()
            name, members_count = validate_family_payload(body)
            family_id = Family.create(trip_id, name, members_count)
            return self.send_json({"id": family_id}, HTTPStatus.CREATED)
        
        # Delete family
        family_delete = re.match(r"^families/(\d+)$", tail)
        if family_delete and self.command == "DELETE":
            family_id = int(family_delete.group(1))
            try:
                Family.soft_delete(trip_id, family_id)
                return self.send_json({"ok": True})
            except ValueError as e:
                if "financial history" in str(e):
                    return self.send_json(
                        {"error": str(e)},
                        HTTPStatus.CONFLICT
                    )
                raise
        
        # Create expense
        if tail == "expenses" and self.command == "POST":
            body = self.read_json()
            split_method = body.get("split_method", "equal")
            if split_method not in ("equal", "per_person", "paid_only"):
                raise ValueError("Invalid split_method")
            expense_id = Expense.create(
                trip_id,
                body["description"].strip(),
                parse_money(body["amount"]),
                body.get("category", "Общее").strip() or "Общее",
                int(body["paid_by_family_id"]),
                split_method,
            )
            return self.send_json({"id": expense_id}, HTTPStatus.CREATED)
        
        # Delete expense
        soft_delete = re.match(r"^expenses/(\d+)$", tail)
        if soft_delete and self.command == "DELETE":
            expense_id = int(soft_delete.group(1))
            Expense.soft_delete(trip_id, expense_id)
            return self.send_json({"ok": True})
        
        # Create transfer
        if tail == "transfers" and self.command == "POST":
            body = self.read_json()
            transfer_id = MoneyTransfer.create(
                trip_id,
                int(body["from_family_id"]),
                int(body["to_family_id"]),
                parse_money(body["amount"]),
                body.get("description", "").strip(),
                body["transfer_type"],
            )
            return self.send_json({"id": transfer_id}, HTTPStatus.CREATED)
        
        # Delete transfer
        soft_delete = re.match(r"^transfers/(\d+)$", tail)
        if soft_delete and self.command == "DELETE":
            transfer_id = int(soft_delete.group(1))
            MoneyTransfer.soft_delete(trip_id, transfer_id)
            return self.send_json({"ok": True})
        
        # Get loans
        if tail == "loans" and self.command == "GET":
            loans = Loan.get_all_for_trip(trip_id)
            return self.send_json({"loans": loans})
        
        # Create loan
        if tail == "loans" and self.command == "POST":
            body = self.read_json()
            loan_id = Loan.create(
                trip_id,
                int(body["lender_family_id"]),
                int(body["borrower_family_id"]),
                parse_money(body["amount"]),
                body.get("description", "").strip(),
            )
            return self.send_json({"id": loan_id}, HTTPStatus.CREATED)
        
        # Update loan
        loan_edit = re.match(r"^loans/(\d+)$", tail)
        if loan_edit and self.command == "PUT":
            loan_id = int(loan_edit.group(1))
            body = self.read_json()
            Loan.update(
                trip_id,
                loan_id,
                int(body["lender_family_id"]),
                int(body["borrower_family_id"]),
                parse_money(body["amount"]),
                body.get("description", "").strip(),
            )
            return self.send_json({"ok": True})
        
        # Delete loan
        soft_delete = re.match(r"^loans/(\d+)$", tail)
        if soft_delete and self.command == "DELETE":
            loan_id = int(soft_delete.group(1))
            Loan.soft_delete(trip_id, loan_id)
            return self.send_json({"ok": True})
        
        # Add loan repayment
        loan_repay = re.match(r"^loans/(\d+)/repayments$", tail)
        if loan_repay and self.command == "POST":
            loan_id = int(loan_repay.group(1))
            body = self.read_json()
            result = Loan.add_repayment(
                loan_id,
                trip_id,
                parse_money(body["amount"]),
                body.get("description", "").strip(),
            )
            return self.send_json(result, HTTPStatus.CREATED)
        
        # Get journal
        if tail == "journal" and self.command == "GET":
            items = JournalService.get_journal(trip_id)
            return self.send_json({"items": items})
        
        return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
    
    def static(self, path: str, head_only=False):
        """Serve static files from STATIC_DIR."""
        if path in ("", "/"):
            path = "/index.html"
        
        target = (STATIC_DIR / path.lstrip("/")).resolve()
        
        # Security check: ensure target is within STATIC_DIR
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or target.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        
        # Determine content type
        content_type = self._get_content_type(target.suffix)
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        
        if not head_only:
            self.wfile.write(target.read_bytes())
    
    @staticmethod
    def _get_content_type(suffix: str) -> str:
        """Get content type for file suffix."""
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        return content_types.get(suffix, "text/plain")
    
    def log_message(self, fmt, *args):
        """Log request message."""
        print(f"{self.address_string()} - {fmt % args}")


def main():
    """Start the Traveler Finance server."""
    migrate()
    
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), TravelerFinanceHandler)
    
    print(f"Traveler Finance is running on http://127.0.0.1:{port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
