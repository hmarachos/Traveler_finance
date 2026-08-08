"""Validation utilities."""
import re


def validate_trip_payload(body: dict) -> tuple[str, str, str]:
    """Validate and sanitize trip creation/update payload.
    
    Returns:
        tuple of (name, currency, access_code)
    
    Raises:
        ValueError: if validation fails
    """
    name = body["name"].strip()
    currency = body.get("currency", "EUR").strip().upper()
    access_code = body["access_code"].strip().upper()
    
    if not name:
        raise ValueError("Trip name is required")
    
    if not re.match(r"^[A-Z]{3}$", currency):
        raise ValueError("Currency must be a 3-letter code")
    
    if not re.match(r"^[A-Z0-9_-]{3,24}$", access_code):
        raise ValueError("Access code must contain 3-24 letters, digits, _ or -")
    
    return name, currency, access_code


def validate_family_payload(body: dict) -> tuple[str, int]:
    """Validate family creation payload.
    
    Returns:
        tuple of (name, members_count)
    
    Raises:
        ValueError: if validation fails
    """
    name = body["name"].strip()
    members_count = int(body["members_count"])
    
    if not name:
        raise ValueError("Family name is required")
    
    if members_count <= 0:
        raise ValueError("Members count must be positive")
    
    return name, members_count
