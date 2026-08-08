"""Money handling utilities."""
import re


def parse_money(value) -> int:
    """Parse money value to minor currency units (integer)."""
    if isinstance(value, int):
        return value
    
    text = str(value or "").strip().replace(" ", "").replace(",", ".")
    
    if not re.match(r"^\d+(\.\d{1,2})?$", text):
        raise ValueError("Invalid amount")
    
    whole, _, cents = text.partition(".")
    return int(whole) * 100 + int((cents + "00")[:2])


def divide_amount(amount: int, weights: list[int]) -> list[int]:
    """Divide amount proportionally according to weights."""
    total = sum(weights)
    
    if total <= 0:
        raise ValueError("Split weights must be positive")
    
    shares = [(amount * weight) // total for weight in weights]
    remainder = amount - sum(shares)
    
    # Distribute remainder to first shares
    for idx in range(remainder):
        shares[idx % len(shares)] += 1
    
    return shares
