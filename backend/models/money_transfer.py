"""Money transfer model."""
from .database import connect, row_to_dict


class MoneyTransfer:
    """Money transfer and advance management operations."""
    
    @staticmethod
    def create(trip_id: int, from_family_id: int, to_family_id: int, 
               amount_minor: int, description: str, transfer_type: str):
        """Create new money transfer and return its ID."""
        from .database import now
        
        with connect() as db:
            stamp = now()
            cur = db.execute(
                """INSERT INTO money_transfers(trip_id, from_family_id, to_family_id, 
                                               amount_minor, description, transfer_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (trip_id, from_family_id, to_family_id, amount_minor, description, transfer_type, stamp),
            )
            return cur.lastrowid
    
    @staticmethod
    def soft_delete(trip_id: int, transfer_id: int):
        """Soft delete money transfer."""
        from .database import now
        
        with connect() as db:
            db.execute(
                "UPDATE money_transfers SET deleted_at = ? WHERE id = ? AND trip_id = ?",
                (now(), transfer_id, trip_id)
            )
    
    @staticmethod
    def get_all_for_trip(trip_id: int):
        """Get all non-deleted money transfers for a trip."""
        with connect() as db:
            return [
                row_to_dict(r)
                for r in db.execute(
                    "SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id",
                    (trip_id,)
                )
            ]
