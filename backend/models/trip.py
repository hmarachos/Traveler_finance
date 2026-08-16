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
    def get_all_for_user(user_id: int):
        """Get all non-deleted trips available to user."""
        with connect() as db:
            return [
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
                    (user_id, user_id),
                )
            ]

    @staticmethod
    def role_for_user(trip_id: int, user_id: int):
        """Return user's role for a trip, or None when user has no access."""
        with connect() as db:
            row = db.execute(
                """
                SELECT COALESCE(tu.role, CASE WHEN t.owner_user_id = ? THEN 'owner' END) AS role
                FROM trips t
                LEFT JOIN trip_users tu ON tu.trip_id = t.id AND tu.user_id = ?
                WHERE t.id = ? AND t.deleted_at IS NULL
                """,
                (user_id, user_id, trip_id),
            ).fetchone()
            return row["role"] if row else None
    
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
    def get_for_user(trip_id: int, user_id: int):
        """Get trip by ID for a specific user or raise LookupError."""
        with connect() as db:
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
    
    @staticmethod
    def create(name: str, currency: str, access_code: str, owner_user_id: int | None = None):
        """Create new trip and return its ID."""
        import sqlite3
        from .database import now
        
        with connect() as db:
            stamp = now()
            try:
                cur = db.execute(
                    "INSERT INTO trips(owner_user_id, name, currency, access_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (owner_user_id, name, currency, access_code, stamp, stamp),
                )
                if owner_user_id is not None:
                    db.execute(
                        "INSERT INTO trip_users(trip_id, user_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                        (cur.lastrowid, owner_user_id, stamp),
                    )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError("Access code is already used by another trip")
    
    @staticmethod
    def update(trip_id: int, name: str, currency: str, access_code: str, user_id: int | None = None):
        """Update trip details."""
        import sqlite3
        from .database import now
        
        with connect() as db:
            try:
                query = """UPDATE trips
                           SET name = ?, currency = ?, access_code = ?, updated_at = ?
                           WHERE id = ? AND deleted_at IS NULL"""
                params = [name, currency, access_code, now(), trip_id]
                if user_id is not None:
                    query += """
                        AND (
                          owner_user_id = ?
                          OR EXISTS (
                            SELECT 1 FROM trip_users
                            WHERE trip_users.trip_id = trips.id AND trip_users.user_id = ?
                          )
                        )
                    """
                    params.extend([user_id, user_id])
                db.execute(
                    query,
                    params,
                )
            except sqlite3.IntegrityError:
                raise ValueError("Access code is already used by another trip")
    
    @staticmethod
    def soft_delete(trip_id: int, owner_user_id: int | None = None):
        """Soft delete trip. Must leave at least one active trip.
        
        Raises ValueError if trying to delete the last remaining trip.
        """
        from .database import now
        
        with connect() as db:
            if owner_user_id is None:
                active_count = db.execute(
                    "SELECT COUNT(*) AS c FROM trips WHERE deleted_at IS NULL"
                ).fetchone()["c"]
            else:
                active_count = db.execute(
                    "SELECT COUNT(*) AS c FROM trips WHERE owner_user_id = ? AND deleted_at IS NULL",
                    (owner_user_id,),
                ).fetchone()["c"]
            
            if active_count <= 1:
                raise ValueError("Cannot delete the last trip. Create a new one first, then delete this one.")
            
            stamp = now()
            query = "UPDATE trips SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL"
            params = [stamp, stamp, trip_id]
            if owner_user_id is not None:
                query += " AND owner_user_id = ?"
                params.append(owner_user_id)
            db.execute(query, params)

    @staticmethod
    def require_owner(trip_id: int, user_id: int):
        """Raise LookupError if user is not trip owner."""
        if Trip.role_for_user(trip_id, user_id) != "owner":
            raise LookupError("Trip not found")

    @staticmethod
    def users(trip_id: int):
        """List users with access to a trip."""
        with connect() as db:
            return [
                row_to_dict(r)
                for r in db.execute(
                    """
                    SELECT u.id, u.username, tu.role, tu.created_at
                    FROM trip_users tu
                    JOIN users u ON u.id = tu.user_id
                    WHERE tu.trip_id = ?
                    ORDER BY CASE tu.role WHEN 'owner' THEN 0 ELSE 1 END, u.username
                    """,
                    (trip_id,),
                )
            ]

    @staticmethod
    def add_user(trip_id: int, username: str, role: str = "member"):
        """Grant a registered user access to a trip."""
        from .database import now

        username = str(username or "").strip().lower()
        if role not in ("owner", "member"):
            raise ValueError("Invalid role")

        with connect() as db:
            user = row_to_dict(db.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone())
            if not user:
                raise LookupError("User not found")

            try:
                db.execute(
                    "INSERT INTO trip_users(trip_id, user_id, role, created_at) VALUES (?, ?, ?, ?)",
                    (trip_id, user["id"], role, now()),
                )
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    raise ValueError("Пользователь уже добавлен в путешествие")
                raise

            if role == "owner":
                db.execute("UPDATE trips SET owner_user_id = ?, updated_at = ? WHERE id = ?", (user["id"], now(), trip_id))

            return user

    @staticmethod
    def remove_user(trip_id: int, user_id: int):
        """Revoke non-owner user's access to a trip."""
        with connect() as db:
            row = row_to_dict(
                db.execute(
                    "SELECT role FROM trip_users WHERE trip_id = ? AND user_id = ?",
                    (trip_id, user_id),
                ).fetchone()
            )
            if not row:
                raise LookupError("User not found")
            if row["role"] == "owner":
                raise ValueError("Нельзя удалить владельца путешествия")

            db.execute("DELETE FROM trip_users WHERE trip_id = ? AND user_id = ?", (trip_id, user_id))
