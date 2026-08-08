"""Trip model."""
import time
from .database import connect, row_to_dict


class Trip:
    """Trip management operations."""
    
    @staticmethod
    def get_all():
        """Get all non-deleted trips."""
        with connect() as db:
            return [
                row_to_dict(r) 
                for r in db.execute("SELECT * FROM trips WHERE deleted_at IS NULL ORDER BY id")
            ]
    
    @staticmethod
    def get_by_id(trip_id: int):
        """Get trip by ID or raise LookupError."""
        with connect() as db:
            trip = row_to_dict(
                db.execute("SELECT * FROM trips WHERE id = ? AND deleted_at IS NULL", (trip_id,)).fetchone()
            )
            if not trip:
                raise LookupError("Trip not found")
            return trip
    
    @staticmethod
    def create(name: str, currency: str, access_code: str):
        """Create new trip and return its ID."""
        import sqlite3
        from .database import now
        
        with connect() as db:
            stamp = now()
            try:
                cur = db.execute(
                    "INSERT INTO trips(name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (name, currency, access_code, stamp, stamp),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError("Access code is already used by another trip")
    
    @staticmethod
    def update(trip_id: int, name: str, currency: str, access_code: str):
        """Update trip details."""
        import sqlite3
        from .database import now
        
        with connect() as db:
            try:
                db.execute(
                    """UPDATE trips
                       SET name = ?, currency = ?, access_code = ?, updated_at = ?
                       WHERE id = ? AND deleted_at IS NULL""",
                    (name, currency, access_code, now(), trip_id),
                )
            except sqlite3.IntegrityError:
                raise ValueError("Access code is already used by another trip")
    
    @staticmethod
    def soft_delete(trip_id: int):
        """Soft delete trip. Must leave at least one active trip.
        
        Raises ValueError if trying to delete the last remaining trip.
        """
        from .database import now
        
        with connect() as db:
            active_count = db.execute(
                "SELECT COUNT(*) AS c FROM trips WHERE deleted_at IS NULL"
            ).fetchone()["c"]
            
            if active_count <= 1:
                raise ValueError("Cannot delete the last trip. Create a new one first, then delete this one.")
            
            stamp = now()
            db.execute(
                "UPDATE trips SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
                (stamp, stamp, trip_id),
            )
