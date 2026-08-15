"""Summary calculation service."""
from models.database import connect, row_to_dict
from models.family import Family
from utils.money import divide_amount


class SummaryService:
    """Calculate trip financial summary."""
    
    @staticmethod
    def compute(trip_id: int) -> dict:
        """Compute complete financial summary for a trip."""
        with connect() as db:
            trip = row_to_dict(
                db.execute("SELECT * FROM trips WHERE id = ? AND deleted_at IS NULL", (trip_id,)).fetchone()
            )
            
            if not trip:
                raise LookupError("Trip not found")
            
            fams = Family.get_all_for_trip(trip_id)
            
            # Initialize stats for each family
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
            
            # Process expenses
            total_expenses = SummaryService._process_expenses(db, trip_id, fams, stats)
            
            # Process money transfers
            SummaryService._process_transfers(db, trip_id, stats)
            
            # Process loans
            by_id = {f["id"]: f for f in fams}
            loan_total, open_loan_total, loan_obligations = SummaryService._process_loans(db, trip_id, stats, by_id)
            
            # Calculate settlements
            settlements = SummaryService._calculate_settlements(stats)
            
            return {
                "trip": trip,
                "families": fams,
                "totals": {
                    "expenses_minor": total_expenses,
                    "paid_minor": sum(s["expense_paid_minor"] for s in stats.values()),
                    "loans_principal_minor": loan_total,
                    "loans_open_minor": open_loan_total,
                    "transfers_minor": SummaryService._sum_by_type(db, trip_id, "transfer"),
                    "advances_minor": SummaryService._sum_by_type(db, trip_id, "advance"),
                    "members_count": sum(f["members_count"] for f in fams),
                    "families_count": len(fams),
                },
                "family_stats": list(stats.values()),
                "expense_settlements": settlements,
                "loan_obligations": loan_obligations,
            }
    
    @staticmethod
    def _process_expenses(db, trip_id: int, fams: list, stats: dict) -> int:
        """Process expenses and update stats."""
        total = 0
        
        for expense in db.execute(
            "SELECT * FROM expenses WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id",
            (trip_id,)
        ):
            paid_by = expense["paid_by_family_id"]
            
            if paid_by in stats:
                stats[paid_by]["expense_paid_minor"] += expense["amount_minor"]
            
            total += expense["amount_minor"]
            
            # Calculate shares based on split method
            if expense["split_method"] == "paid_only":
                # Only the paying family bears the expense
                if paid_by in stats:
                    stats[paid_by]["expense_share_minor"] += expense["amount_minor"]
            else:
                weights = (
                    [1 for _ in fams] 
                    if expense["split_method"] == "equal" 
                    else [f["members_count"] for f in fams]
                )
                
                shares = divide_amount(expense["amount_minor"], weights)
                
                for family, share in zip(fams, shares):
                    stats[family["id"]]["expense_share_minor"] += share
        
        # Finalize expense balances
        for stat in stats.values():
            stat["expense_balance_minor"] = (
                stat["expense_paid_minor"] - stat["expense_share_minor"]
            )
        
        return total
    
    @staticmethod
    def _process_transfers(db, trip_id: int, stats: dict):
        """Process money transfers and updates stats."""
        for transfer in db.execute(
            "SELECT * FROM money_transfers WHERE trip_id = ? AND deleted_at IS NULL ORDER BY id",
            (trip_id,)
        ):
            amount = transfer["amount_minor"]
            
            if transfer["transfer_type"] == "advance":
                sent_key = "advances_sent_minor"
                received_key = "advances_received_minor"
            else:
                sent_key = "transfers_sent_minor"
                received_key = "transfers_received_minor"
            
            if transfer["from_family_id"] in stats:
                stats[transfer["from_family_id"]][sent_key] += amount
            
            if transfer["to_family_id"] in stats:
                stats[transfer["to_family_id"]][received_key] += amount
    
    @staticmethod
    def _process_loans(db, trip_id: int, stats: dict, by_id: dict) -> tuple[int, int, list]:
        """Process loans and return totals and obligations."""
        loan_total = 0
        open_loan_total = 0
        loan_obligations = []
        
        for loan in db.execute(
            "SELECT * FROM loans WHERE trip_id = ? AND deleted_at IS NULL AND status <> 'cancelled' ORDER BY id",
            (trip_id,)
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
                loan_obligations.append({
                    "from_family_id": borrower,
                    "from_family_name": by_id.get(borrower, {}).get("name", "Unknown"),
                    "to_family_id": lender,
                    "to_family_name": by_id.get(lender, {}).get("name", "Unknown"),
                    "amount_minor": loan["remaining_amount_minor"],
                    "loan_id": loan["id"],
                })
        
        return loan_total, open_loan_total, loan_obligations
    
    @staticmethod
    def _calculate_settlements(stats: dict) -> list:
        """Calculate optimal expense settlements between families."""
        debtors = []
        creditors = []
        
        for family_id, stat in stats.items():
            balance = stat["expense_balance_minor"]
            item = {
                "family_id": family_id,
                "family_name": stat["family"]["name"],
                "amount": abs(balance)
            }
            
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
                settlements.append({
                    "from_family_id": debtors[i]["family_id"],
                    "from_family_name": debtors[i]["family_name"],
                    "to_family_id": creditors[j]["family_id"],
                    "to_family_name": creditors[j]["family_name"],
                    "amount_minor": amount,
                })
            
            debtors[i]["amount"] -= amount
            creditors[j]["amount"] -= amount
            
            if debtors[i]["amount"] == 0:
                i += 1
            
            if creditors[j]["amount"] == 0:
                j += 1
        
        return settlements
    
    @staticmethod
    def _sum_by_type(db, trip_id: int, transfer_type: str) -> int:
        """Sum all transfers of a specific type."""
        row = db.execute(
            "SELECT SUM(amount_minor) as total FROM money_transfers WHERE trip_id = ? AND transfer_type = ? AND deleted_at IS NULL",
            (trip_id, transfer_type)
        ).fetchone()
        return row["total"] or 0
