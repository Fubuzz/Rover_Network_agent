"""
Parsers for extracting contact information from various inputs.
"""

import re
from typing import Dict, Optional, List
from utils.constants import PATTERNS, CLASSIFICATION_KEYWORDS


def extract_email(text: str) -> Optional[str]:
    """Extract email address from text."""
    pattern = re.compile(PATTERNS["email"])
    match = pattern.search(text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    pattern = re.compile(PATTERNS["phone"])
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def extract_linkedin(text: str) -> Optional[str]:
    """Extract LinkedIn URL from text."""
    pattern = re.compile(PATTERNS["linkedin"], re.IGNORECASE)
    match = pattern.search(text)
    return match.group(0) if match else None


def extract_urls(text: str) -> List[str]:
    """Extract all URLs from text."""
    pattern = re.compile(PATTERNS["url"])
    return pattern.findall(text)


def guess_classification(text: str) -> Optional[str]:
    """
    Guess contact classification based on text content.
    Returns the most likely classification or None.
    """
    text_lower = text.lower()
    scores = {category: 0 for category in CLASSIFICATION_KEYWORDS}
    
    for category, keywords in CLASSIFICATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[category] += 1
    
    # Get the highest scoring category
    max_score = max(scores.values())
    if max_score > 0:
        for category, score in scores.items():
            if score == max_score:
                return category
    
    return None


def parse_contact_from_text(text: str) -> Dict:
    """
    Parse contact information from natural language text.
    
    Returns a dictionary with extracted fields.
    """
    result = {
        "name": None,
        "job_title": None,
        "company": None,
        "phone": None,
        "email": None,
        "linkedin_url": None,
        "location": None,
        "classification": None,
        "raw_text": text
    }
    
    # Extract structured data
    result["email"] = extract_email(text)
    result["phone"] = extract_phone(text)
    result["linkedin_url"] = extract_linkedin(text)
    
    # Try to extract name (usually the first line or first few words)
    lines = text.strip().split("\n")
    if lines:
        first_line = lines[0].strip()
        # If first line doesn't contain special characters, it might be a name
        if not re.search(r"[@:;,\d]", first_line) and len(first_line) < 50:
            result["name"] = first_line
    
    # Look for common patterns
    patterns = {
        "job_title": [
            r"(?:works?\s+as|title[:\s]+|position[:\s]+|role[:\s]+)(.+?)(?:\n|at|,|$)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+at\s+",
        ],
        "company": [
            r"(?:at|@|works?\s+(?:at|for)|company[:\s]+|from)[\s]*([A-Z][^\n,]+?)(?:\n|,|$)",
            r"(?:CEO|CTO|COO|Founder|Director|Manager)\s+(?:at|of)\s+([^\n,]+)",
        ],
        "location": [
            r"(?:based\s+in|located?\s+in|from|location[:\s]+)[\s]*([A-Z][^\n,]+?)(?:\n|,|$)",
            r"([A-Z][a-z]+(?:,\s*[A-Z]{2})?)\s*$",  # City, State format
        ]
    }
    
    for field, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match and not result[field]:
                result[field] = match.group(1).strip()
                break
    
    # Guess classification
    result["classification"] = guess_classification(text)
    
    return result


def parse_contact_from_voice(transcript: str) -> Dict:
    """
    Parse contact information from voice transcript.
    Uses the same logic as text parsing but with some adjustments.
    """
    # Clean up common transcription artifacts
    cleaned = transcript
    
    # Common voice-to-text corrections
    replacements = {
        " at sign ": "@",
        " at the rate ": "@",
        " dot ": ".",
        " underscore ": "_",
        " hyphen ": "-",
        " dash ": "-",
    }
    
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    
    return parse_contact_from_text(cleaned)


def parse_contact_from_structured(data: Dict) -> Dict:
    """
    Normalize contact data from structured input (like OCR or API).
    """
    result = {
        "name": None,
        "job_title": None,
        "company": None,
        "phone": None,
        "email": None,
        "linkedin_url": None,
        "location": None,
        "classification": None,
    }
    
    # Map common field names
    field_mappings = {
        "name": ["name", "full_name", "fullname", "contact_name"],
        "job_title": ["job_title", "title", "position", "role", "job"],
        "company": ["company", "organization", "org", "employer", "company_name"],
        "phone": ["phone", "phone_number", "tel", "telephone", "mobile", "cell"],
        "email": ["email", "email_address", "e-mail", "mail"],
        "linkedin_url": ["linkedin", "linkedin_url", "linkedin_profile"],
        "location": ["location", "address", "city", "place", "region"],
        "classification": ["classification", "type", "category", "class"],
    }
    
    for target_field, source_fields in field_mappings.items():
        for source_field in source_fields:
            if source_field in data and data[source_field]:
                result[target_field] = data[source_field]
                break
    
    # Validate and clean extracted data
    if result["email"]:
        result["email"] = result["email"].lower().strip()
    
    if result["linkedin_url"]:
        result["linkedin_url"] = result["linkedin_url"].strip()
    
    return result


def parse_bulk_contacts(text: str, delimiter: str = "\n") -> List[Dict]:
    """
    Parse multiple contacts from bulk text input.
    Each contact should be separated by the delimiter.
    """
    contacts = []
    entries = text.split(delimiter)
    
    for entry in entries:
        entry = entry.strip()
        if entry:
            contact = parse_contact_from_text(entry)
            if contact.get("name") or contact.get("email"):
                contacts.append(contact)
    
    return contacts


def parse_csv_row(row: List[str], headers: List[str]) -> Dict:
    """
    Parse a CSV row into contact data.
    """
    result = {}
    
    for i, header in enumerate(headers):
        if i < len(row):
            header_lower = header.lower().strip()
            value = row[i].strip() if row[i] else None
            
            # Map header to field name
            if "name" in header_lower:
                result["name"] = value
            elif "title" in header_lower or "position" in header_lower:
                result["job_title"] = value
            elif "company" in header_lower or "org" in header_lower:
                result["company"] = value
            elif "phone" in header_lower or "tel" in header_lower:
                result["phone"] = value
            elif "email" in header_lower or "mail" in header_lower:
                result["email"] = value
            elif "linkedin" in header_lower:
                result["linkedin_url"] = value
            elif "location" in header_lower or "city" in header_lower:
                result["location"] = value
    
    return result
