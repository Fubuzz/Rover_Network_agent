"""
Validation utilities for contact data.
"""

import re
from typing import Optional, Tuple, List
from utils.constants import PATTERNS


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return True, None  # Empty is valid (optional field)
    
    email = email.strip().lower()
    pattern = re.compile(PATTERNS["email"])
    
    if pattern.match(email):
        return True, None
    return False, f"Invalid email format: {email}"


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return True, None  # Empty is valid (optional field)
    
    # Remove common separators for validation
    cleaned = re.sub(r"[\s\-\.\(\)]", "", phone)
    
    # Check if it contains only valid characters
    if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
        return False, f"Invalid phone number format: {phone}"
    
    return True, None


def validate_linkedin_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate LinkedIn profile URL.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return True, None  # Empty is valid (optional field)
    
    url = url.strip().lower()
    pattern = re.compile(PATTERNS["linkedin"])
    
    if pattern.match(url):
        return True, None
    return False, f"Invalid LinkedIn URL: {url}"


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate general URL format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return True, None
    
    url = url.strip()
    pattern = re.compile(PATTERNS["url"])
    
    if pattern.match(url):
        return True, None
    return False, f"Invalid URL: {url}"


def validate_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate contact name.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Name is required"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Name must be at least 2 characters"
    
    if len(name) > 100:
        return False, "Name must be less than 100 characters"
    
    return True, None


def validate_classification(classification: str) -> Tuple[bool, Optional[str]]:
    """
    Validate contact classification.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not classification:
        return True, None  # Empty is valid (optional field)
    
    valid_classifications = ["founder", "investor", "enabler", "professional"]
    classification = classification.strip().lower()
    
    if classification in valid_classifications:
        return True, None
    return False, f"Invalid classification: {classification}. Valid options: {', '.join(valid_classifications)}"


def validate_contact_data(data: dict) -> Tuple[bool, List[str]]:
    """
    Validate all contact data fields.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    # Validate name (required)
    is_valid, error = validate_name(data.get("name", ""))
    if not is_valid:
        errors.append(error)
    
    # Validate email
    is_valid, error = validate_email(data.get("email", ""))
    if not is_valid:
        errors.append(error)
    
    # Validate phone
    is_valid, error = validate_phone(data.get("phone", ""))
    if not is_valid:
        errors.append(error)
    
    # Validate LinkedIn URL
    is_valid, error = validate_linkedin_url(data.get("linkedin_url", ""))
    if not is_valid:
        errors.append(error)
    
    # Validate classification
    is_valid, error = validate_classification(data.get("classification", ""))
    if not is_valid:
        errors.append(error)
    
    return len(errors) == 0, errors


def format_phone_number(phone: str) -> str:
    """
    Format phone number to a standard format.
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r"[^\d+]", "", phone)
    
    # Basic formatting
    if cleaned.startswith("+"):
        return cleaned
    elif len(cleaned) == 10:
        return f"+1{cleaned}"  # Assume US number
    else:
        return cleaned


def normalize_email(email: str) -> str:
    """
    Normalize email address.
    """
    if not email:
        return ""
    return email.strip().lower()


def normalize_linkedin_url(url: str) -> str:
    """
    Normalize LinkedIn URL.
    """
    if not url:
        return ""
    
    url = url.strip().lower()
    
    # Add https:// if missing
    if not url.startswith("http"):
        url = "https://" + url
    
    # Ensure it's linkedin.com
    if "linkedin.com" not in url:
        return url
    
    # Remove trailing slash
    url = url.rstrip("/")
    
    return url
