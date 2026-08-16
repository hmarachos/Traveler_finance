"""Loan model."""
from .database import connect, row_to_dict


class Loan:
    """Loan management operations."""
    
    @staticmethod
    def create(trip_id: int, lender_family_id: int, borrower_family_id: int, 
               principal_amount_minor: int, description: str, user_id: int = None):
        """Create or net a loan for a family pair and return affected loan ID."""
        from .database import now
        
        with connect() as db:
            existing = Loan._get_open_between_families(
                db, trip_id, lender_family_id, borrower_family_id
            )
            stamp = now()
            
            if existing:
                loan_id = existing["id"]
                
                if existing["lender_family_id"] == lender_family_id:
                    principal = existing["principal_amount_minor"] + principal_amount_minor
                    remaining = existing["remaining_amount_minor"] + principal_amount_minor
                    db.execute(
                        """UPDATE loans
                           SET principal_amount_minor = ?, remaining_amount_minor = ?,
                               description = ?, status = ?, updated_at = ?
                           WHERE id = ?""",
                        (
                            principal,
                            remaining,
                            description or existing["description"],
                            "active" if remaining == principal else "partially_repaid",
                            stamp,
                            loan_id,
                        ),
                    )
                    return loan_id
                
                repayment = min(principal_amount_minor, existing["remaining_amount_minor"])
                if repayment > 0:
                    db.execute(
                        "INSERT INTO loan_repayments(loan_id, amount_minor, created_at, description, created_by_user_id) VALUES (?, ?, ?, ?, ?)",
                        (loan_id, repayment, stamp, description or "Встречный заем", user_id),
                    )
                
                remaining = existing["remaining_amount_minor"] - repayment
                status = "repaid" if remaining == 0 else "partially_repaid"
                db.execute(
                    "UPDATE loans SET remaining_amount_minor = ?, status = ?, updated_at = ? WHERE id = ?",
                    (remaining, status, stamp, loan_id),
                )
                
                remainder = principal_amount_minor - repayment
                if remainder == 0:
                    return loan_id
                
                principal_amount_minor = remainder
            
            cur = db.execute(
                """INSERT INTO loans(trip_id, lender_family_id, borrower_family_id, 
                                     principal_amount_minor, remaining_amount_minor, 
                                     description, created_by_user_id, created_at, updated_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (trip_id, lender_family_id, borrower_family_id, 
                 principal_amount_minor, principal_amount_minor, description, user_id, stamp, stamp),
            )
            return cur.lastrowid

    @staticmethod
    def _get_open_between_families(db, trip_id: int, first_family_id: int, second_family_id: int):
        """Find the newest open loan between two families in either direction."""
        return row_to_dict(
            db.execute(
                """
                SELECT * FROM loans
                WHERE trip_id = ?
                  AND deleted_at IS NULL
                  AND remaining_amount_minor > 0
                  AND status <> 'cancelled'
                  AND (
                    (lender_family_id = ? AND borrower_family_id = ?)
                    OR (lender_family_id = ? AND borrower_family_id = ?)
                  )
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    trip_id,
                    first_family_id,
                    second_family_id,
                    second_family_id,
                    first_family_id,
                ),
            ).fetchone()
        )
    
    @staticmethod
    def get_all_for_trip(trip_id: int):
        """Get all non-deleted loans for a trip with repayments."""
        with connect() as db:
            loans = [
                row_to_dict(r)
                for r in db.execute(
                    "SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id DESC",
                    (trip_id,)
                )
            ]
            
            for loan in loans:
                loan["repayments"] = [
                    row_to_dict(r)
                    for r in db.execute(
                        "SELECT * FROM loan_repayments WHERE loan_id = ? ORDER BY id",
                        (loan["id"],)
                    )
                ]
            
            return loans
    
    @staticmethod
    def get_by_id(loan_id: int, trip_id: int):
        """Get loan by ID and trip ID."""
        with connect() as db:
            return row_to_dict(
                db.execute(
                    "SELECT * FROM loans WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                    (loan_id, trip_id)
                ).fetchone()
            )
    
    @staticmethod
    def add_repayment(loan_id: int, trip_id: int, amount_minor: int, description: str, user_id: int = None):
        """Add loan repayment and update remaining amount."""
        from .database import now
        
        with connect() as db:
            loan = Loan.get_by_id(loan_id, trip_id)
            
            if not loan:
                raise LookupError("Loan not found")
            
            if loan["status"] in ("repaid", "cancelled"):
                raise ValueError("Loan is not active")
            
            if amount_minor > loan["remaining_amount_minor"]:
                raise ValueError("Repayment cannot exceed remaining loan amount")
            
            stamp = now()
            remaining = loan["remaining_amount_minor"] - amount_minor
            status = "repaid" if remaining == 0 else "partially_repaid"
            
            db.execute(
                "INSERT INTO loan_repayments(loan_id, amount_minor, created_at, description, created_by_user_id) VALUES (?, ?, ?, ?, ?)",
                (loan_id, amount_minor, stamp, description, user_id),
            )
            
            db.execute(
                "UPDATE loans SET remaining_amount_minor = ?, status = ?, updated_at = ? WHERE id = ?",
                (remaining, status, stamp, loan_id),
            )
            
            return {"remaining_amount_minor": remaining, "status": status}
    
    @staticmethod
    def update(trip_id: int, loan_id: int, lender_family_id: int, borrower_family_id: int,
               principal_amount_minor: int, description: str):
        """Update loan details while preserving recorded repayments."""
        from .database import now
        
        with connect() as db:
            loan = Loan.get_by_id(loan_id, trip_id)
            
            if not loan:
                raise LookupError("Loan not found")
            
            repaid = db.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM loan_repayments WHERE loan_id = ?",
                (loan_id,),
            ).fetchone()["total"]
            remaining = max(principal_amount_minor - repaid, 0)
            status = "repaid" if remaining == 0 else ("partially_repaid" if repaid else "active")
            
            db.execute(
                """
                UPDATE loans
                SET lender_family_id = ?, borrower_family_id = ?, principal_amount_minor = ?,
                    remaining_amount_minor = ?, description = ?, status = ?, updated_at = ?
                WHERE id = ? AND trip_id = ?
                """,
                (
                    lender_family_id,
                    borrower_family_id,
                    principal_amount_minor,
                    remaining,
                    description,
                    status,
                    now(),
                    loan_id,
                    trip_id,
                ),
            )
            
            return {"remaining_amount_minor": remaining, "status": status}
    
    @staticmethod
    def soft_delete(trip_id: int, loan_id: int):
        """Soft delete loan."""
        from .database import now
        
        with connect() as db:
            db.execute(
                "UPDATE loans SET deleted_at = ? WHERE id = ? AND trip_id = ?",
                (now(), loan_id, trip_id)
            )
