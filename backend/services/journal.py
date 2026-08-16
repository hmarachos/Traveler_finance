"""Journal/transaction log service."""
from models.database import connect, row_to_dict
from models.family import Family


class JournalService:
    """Generate transaction journal entries."""
    
    @staticmethod
    def get_journal(trip_id: int) -> list:
        """Get all transactions for a trip in reverse chronological order."""
        with connect() as db:
            fams = Family.get_all_for_trip(trip_id)
            family_names = {f["id"]: f["name"] for f in fams}
            
            # Get all users for author names
            users = {
                r["id"]: r["username"]
                for r in db.execute("SELECT id, username FROM users")
            }
            
            items = []
            
            # Add expenses
            items.extend(JournalService._get_expense_entries(db, trip_id, family_names, users))
            
            # Add transfers and advances
            items.extend(JournalService._get_transfer_entries(db, trip_id, family_names, users))
            
            # Add loans
            items.extend(JournalService._get_loan_entries(db, trip_id, family_names, users))
            
            # Add loan repayments
            items.extend(JournalService._get_repayment_entries(db, trip_id, family_names, users))
            
            # Sort by creation date (newest first)
            return sorted(items, key=lambda x: x["created_at"], reverse=True)
    
    @staticmethod
    def _get_expense_entries(db, trip_id: int, family_names: dict, users: dict) -> list:
        """Get expense journal entries."""
        entries = []
        
        for r in db.execute(
            "SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL",
            (trip_id,)
        ):
            created_by_user_id = r["created_by_user_id"] if "created_by_user_id" in r.keys() else None
            author = users.get(created_by_user_id) if created_by_user_id else None
            author = author or "Система"
            
            entries.append({
                "id": r["id"],
                "type": "expense",
                "title": r["description"],
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": (
                    f"Оплатили: {family_names.get(r['paid_by_family_id'], 'Unknown')} · "
                    f"{r['category']}"
                ),
            })
        
        return entries
    
    @staticmethod
    def _get_transfer_entries(db, trip_id: int, family_names: dict, users: dict) -> list:
        """Get transfer and advance journal entries."""
        entries = []
        
        for r in db.execute(
            "SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL",
            (trip_id,)
        ):
            created_by_user_id = r["created_by_user_id"] if "created_by_user_id" in r.keys() else None
            author = users.get(created_by_user_id) if created_by_user_id else None
            author = author or "Система"
            
            entry_type = "advance" if r["transfer_type"] == "advance" else "transfer"
            
            entries.append({
                "id": r["id"],
                "type": entry_type,
                "title": r["description"] or (
                    "Аванс" if r["transfer_type"] == "advance" else "Перевод"
                ),
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": (
                    f"{family_names.get(r['from_family_id'], 'Unknown')} → "
                    f"{family_names.get(r['to_family_id'], 'Unknown')}"
                ),
            })
        
        return entries
    
    @staticmethod
    def _get_loan_entries(db, trip_id: int, family_names: dict, users: dict) -> list:
        """Get loan journal entries."""
        entries = []
        
        for r in db.execute(
            "SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL",
            (trip_id,)
        ):
            created_by_user_id = r["created_by_user_id"] if "created_by_user_id" in r.keys() else None
            author = users.get(created_by_user_id) if created_by_user_id else None
            author = author or "Система"
            
            entries.append({
                "id": r["id"],
                "type": "loan",
                "title": r["description"] or "Заем",
                "amount_minor": r["principal_amount_minor"],
                "created_at": r["created_at"],
                "remaining_amount_minor": r["remaining_amount_minor"],
                "author": author,
                "meta": (
                    f"{family_names.get(r['borrower_family_id'], 'Unknown')} должны "
                    f"{family_names.get(r['lender_family_id'], 'Unknown')}"
                ),
            })
        
        return entries
    
    @staticmethod
    def _get_repayment_entries(db, trip_id: int, family_names: dict, users: dict) -> list:
        """Get loan repayment journal entries."""
        entries = []
        
        for r in db.execute(
            """SELECT lr.*, l.trip_id, l.lender_family_id, l.borrower_family_id
               FROM loan_repayments lr 
               JOIN loans l ON l.id = lr.loan_id
               WHERE l.trip_id = ?""",
            (trip_id,)
        ):
            created_by_user_id = r["created_by_user_id"] if "created_by_user_id" in r.keys() else None
            author = users.get(created_by_user_id) if created_by_user_id else None
            author = author or "Система"
            
            entries.append({
                "id": r["id"],
                "type": "loan_repayment",
                "title": r["description"] or "Возврат займа",
                "amount_minor": r["amount_minor"],
                "created_at": r["created_at"],
                "author": author,
                "meta": (
                    f"{family_names.get(r['borrower_family_id'], 'Unknown')} → "
                    f"{family_names.get(r['lender_family_id'], 'Unknown')}"
                ),
            })
        
        return entries
