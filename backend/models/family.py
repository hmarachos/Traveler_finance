"""Family model."""
from .database import connect, row_to_dict


class Family:
    """Family management operations."""
    
    @staticmethod
    def get_all_for_trip(trip_id: int):
        """Get all non-deleted families for a trip."""
        with connect() as db:
            return [
                row_to_dict(r)
                for r in db.execute(
                    "SELECT * FROM families WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id",
                    (trip_id,)
                )
            ]
    
    @staticmethod
    def create(trip_id: int, name: str, members_count: int):
        """Create new family and return its ID."""
        from .database import now
        
        with connect() as db:
            stamp = now()
            cur = db.execute(
                "INSERT INTO families(trip_id, name, members_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (trip_id, name, members_count, stamp, stamp),
            )
            return cur.lastrowid
    
    @staticmethod
    def soft_delete(trip_id: int, family_id: int):
        """Soft delete family if it has no financial history."""
        from .database import now
        
        with connect() as db:
            family = row_to_dict(
                db.execute(
                    "SELECT * FROM families WHERE id = ? AND trip_id = ? AND deleted_at IS NULL",
                    (family_id, trip_id),
                ).fetchone()
            )
            
            if not family:
                raise LookupError("Family not found")
            
            # Check if at least one family remains
            families = Family.get_all_for_trip(trip_id)
            if len(families) <= 1:
                raise ValueError("At least one family must remain in the trip")
            
            # Check for financial references
            if Family._has_financial_refs(db, trip_id, family_id):
                raise ValueError("Family has financial history and cannot be deleted")
            
            db.execute(
                "UPDATE families SET deleted_at = ?, updated_at = ? WHERE id = ? AND trip_id = ?",
                (now(), now(), family_id, trip_id),
            )
    
    @staticmethod
    def _has_financial_refs(db, trip_id: int, family_id: int) -> bool:
        """Check if family has any financial transactions."""
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
        return total > 0
