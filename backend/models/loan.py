"""Loan model."""
from .database import connect, row_to_dict


class Loan:
    """Loan management operations."""
    
    @staticmethod
    def create(trip_id: int, lender_family_id: int, borrower_family_id: int, 
               principal_amount_minor: int, description: str):
        """Create new loan and return its ID."""
        from .database import now
        
        with connect() as db:
            stamp = now()
            cur = db.execute(
                """INSERT INTO loans(trip_id, lender_family_id, borrower_family_id, 
                                     principal_amount_minor, remaining_amount_minor, 
                                     description, created_at, updated_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (trip_id, lender_family_id, borrower_family_id, 
                 principal_amount_minor, principal_amount_minor, description, stamp, stamp),
            )
            return cur.lastrowid
    
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
    def add_repayment(loan_id: int, trip_id: int, amount_minor: int, description: str):
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
                "INSERT INTO loan_repayments(loan_id, amount_minor, created_at, description) VALUES (?, ?, ?, ?)",
                (loan_id, amount_minor, stamp, description),
            )
            
            db.execute(
                "UPDATE loans SET remaining_amount_minor = ?, status = ?, updated_at = ? WHERE id = ?",
                (remaining, status, stamp, loan_id),
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
