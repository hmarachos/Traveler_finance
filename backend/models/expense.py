"""Expense model."""
from .database import connect, row_to_dict


# Standard expense categories for travel and shared living
STANDARD_CATEGORIES = [
    "Общее",
    "Жильё",
    "Транспорт",
    "Еда",
    "Продукты",
    "Развлечения",
    "Сувениры",
    "Здоровье",
    "Связь",
    "Страховка",
    "Парковка",
    "Туалеты",
    "Другое"
]


class Expense:
    """Expense management operations."""
    
    @staticmethod
    def get_standard_categories():
        """Get list of standard expense categories."""
        return STANDARD_CATEGORIES
    
    @staticmethod
    def create(trip_id: int, description: str, amount_minor: int, category: str, 
               paid_by_family_id: int, split_method: str, user_id: int = None, 
               custom_split_weights: str = None):
        """Create new expense and return its ID."""
        from .database import now
        
        if split_method not in ("equal", "per_person", "paid_only", "custom"):
            raise ValueError("Invalid split_method")
        
        if split_method == "custom" and not custom_split_weights:
            raise ValueError("custom_split_weights required for custom split method")
        
        with connect() as db:
            stamp = now()
            cur = db.execute(
                """INSERT INTO expenses(trip_id, description, amount_minor, category, 
                                        paid_by_family_id, split_method, custom_split_weights, 
                                        created_by_user_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trip_id, description, amount_minor, category, paid_by_family_id, 
                 split_method, custom_split_weights, user_id, stamp, stamp),
            )
            return cur.lastrowid
    
    @staticmethod
    def soft_delete(trip_id: int, expense_id: int):
        """Soft delete expense."""
        from .database import now
        
        with connect() as db:
            db.execute(
                "UPDATE expenses SET deleted_at = ? WHERE id = ? AND trip_id = ?",
                (now(), expense_id, trip_id)
            )
    
    @staticmethod
    def get_all_for_trip(trip_id: int):
        """Get all non-deleted expenses for a trip."""
        with connect() as db:
            return [
                row_to_dict(r)
                for r in db.execute(
                    "SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id",
                    (trip_id,)
                )
            ]
