"""
Text Cleaner for Contact Field Values.
Cleans raw AI-extracted text to store only clean, normalized values.
Includes input sanitization for security.
"""

import re
from typing import Dict, Any, Optional


def sanitize_input(text: str, max_length: int = 5000) -> str:
    """
    Sanitize user input to prevent issues and security vulnerabilities.

    - Removes control characters (except newline/tab)
    - Normalizes whitespace
    - Limits length to prevent memory issues
    - Removes potential script injection patterns

    Args:
        text: Raw user input
        max_length: Maximum allowed length (default 5000)

    Returns:
        Sanitized text safe for processing
    """
    if not text:
        return ""

    # Remove control characters (keep printable + newline/tab)
    text = ''.join(c for c in text if c.isprintable() or c in '\n\t')

    # Normalize whitespace (collapse multiple spaces/newlines)
    text = ' '.join(text.split())

    # Limit length to prevent memory issues
    if len(text) > max_length:
        text = text[:max_length] + "..."

    # Remove potential script injection patterns (XSS prevention)
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)  # onclick=, onerror=, etc.

    # Remove null bytes (potential injection)
    text = text.replace('\x00', '')

    return text.strip()


# Patterns to strip from the BEGINNING of field values
PREFIX_PATTERNS = {
    'title': [
        r"^(he's|she's|they're|he is|she is|they are)\s+",
        r"^(the|a|an)\s+",
        r"^(currently|now|working as)\s+(a|an|the)?\s*",
    ],
    'company': [
        r"^(at|from|with|for)\s+",
        r"^(works?\s+)?(at|for|with)\s+",
        r"^(the|a|an)\s+",
        r"^(currently\s+)?(at|with)\s+",
    ],
    'email': [
        r"^(email:?|e-mail:?|mail:?)\s*",
        r"^(his|her|their|my)\s+(email|e-mail)\s+(is|:)\s*",
        r"^(it's|its|that's)\s+",
        r"^(reach\s+(him|her|them)\s+at)\s*",
    ],
    'phone': [
        r"^(phone:?|tel:?|mobile:?|cell:?|call:?)\s*",
        r"^(his|her|their|my)\s+(phone|number|cell|mobile)\s+(is|:)\s*",
        r"^(reach\s+(him|her|them)\s+at)\s*",
        r"^(it's|its|that's)\s+",
    ],
    'address': [
        r"^(based\s+)?(in|at|from)\s+",
        r"^(located\s+)?(in|at)\s+",
        r"^(lives?\s+)?(in|at)\s+",
        r"^(currently\s+)?(in|at)\s+",
    ],
    'linkedin': [
        r"^(linkedin:?|profile:?)\s*",
        r"^(his|her|their)\s+linkedin\s+(is|:)\s*",
        r"^(find\s+(him|her|them)\s+at)\s*",
    ],
    'industry': [
        r"^(in\s+the|in|the)\s+",
        r"^(works?\s+in)\s+",
    ],
    'notes': [
        r"^(note:?|notes:?|also:?|btw:?)\s*",
    ],
}

# Patterns to strip from the END of field values
SUFFIX_PATTERNS = {
    'title': [
        r"\s+at\s+.+$",  # Remove "at Company" from title
        r"\s+for\s+.+$",  # Remove "for Company" from title
        r"\s+with\s+.+$",  # Remove "with Company" from title
    ],
    'company': [
        r"\s+as\s+.+$",  # Remove "as Title" from company
    ],
}

# Fields that should be lowercase
LOWERCASE_FIELDS = {'email'}

# Fields that should be title case
TITLECASE_FIELDS = {'name', 'first_name', 'last_name', 'full_name', 'company', 'address'}

# Fields where we preserve case but clean up
PRESERVE_CASE_FIELDS = {'title', 'industry', 'notes', 'linkedin', 'linkedin_url', 'phone'}


def clean_field_value(field: str, raw_value: str) -> str:
    """
    Clean a raw AI-extracted value for a specific field.

    Examples:
        clean_field_value("title", "He's the CEO") → "CEO"
        clean_field_value("company", "at Synapse Analytics") → "Synapse Analytics"
        clean_field_value("email", "his email is john@test.com") → "john@test.com"
    """
    if not raw_value:
        return raw_value

    value = raw_value.strip()

    # Apply prefix patterns for this field
    if field in PREFIX_PATTERNS:
        for pattern in PREFIX_PATTERNS[field]:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE).strip()

    # Apply suffix patterns for this field
    if field in SUFFIX_PATTERNS:
        for pattern in SUFFIX_PATTERNS[field]:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE).strip()

    # Clean up multiple spaces
    value = re.sub(r'\s+', ' ', value).strip()

    # Apply capitalization rules
    value = normalize_capitalization(field, value)

    return value


def normalize_capitalization(field: str, value: str) -> str:
    """
    Normalize capitalization based on field type.

    - Emails: lowercase
    - Names/Companies: Title Case
    - Titles: Smart title case (preserve acronyms like CEO, CTO, VP)
    - Other: Preserve original
    """
    if not value:
        return value

    if field in LOWERCASE_FIELDS:
        return value.lower()

    if field in TITLECASE_FIELDS:
        return smart_title_case(value)

    if field == 'title':
        return smart_title_case_for_job_title(value)

    return value


def smart_title_case(text: str) -> str:
    """
    Apply title case while preserving certain patterns.
    """
    if not text:
        return text

    # Split into words
    words = text.split()
    result = []

    for word in words:
        # Preserve all-caps short words (likely acronyms)
        if word.isupper() and len(word) <= 4:
            result.append(word)
        # Preserve words that look like proper nouns (mixed case)
        elif any(c.isupper() for c in word[1:]):
            result.append(word)
        else:
            result.append(word.capitalize())

    return ' '.join(result)


def smart_title_case_for_job_title(title: str) -> str:
    """
    Apply smart capitalization for job titles.
    Preserves common acronyms: CEO, CTO, CFO, COO, VP, SVP, EVP, MD, etc.
    """
    if not title:
        return title

    # Common title acronyms to preserve uppercase
    acronyms = {
        'ceo', 'cto', 'cfo', 'coo', 'cio', 'cmo', 'cpo', 'cro',
        'vp', 'svp', 'evp', 'avp',
        'md', 'phd', 'mba', 'jd',
        'hr', 'it', 'pr', 'qa',
        'ui', 'ux',
    }

    # Words to keep lowercase (unless at start)
    lowercase_words = {'of', 'the', 'and', 'at', 'in', 'for', 'to', 'a', 'an'}

    words = title.split()
    result = []

    for i, word in enumerate(words):
        word_lower = word.lower()

        if word_lower in acronyms:
            result.append(word.upper())
        elif i > 0 and word_lower in lowercase_words:
            result.append(word_lower)
        elif word.isupper() and len(word) <= 4:
            # Preserve existing short uppercase words
            result.append(word)
        else:
            result.append(word.capitalize())

    return ' '.join(result)


def extract_email(text: str) -> Optional[str]:
    """Extract a clean email address from text."""
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if match:
        return match.group().lower()
    return None


def extract_phone(text: str) -> Optional[str]:
    """Extract and normalize a phone number from text."""
    # Remove common prefixes
    cleaned = re.sub(r'^(phone:?|tel:?|mobile:?|cell:?|call:?)\s*', '', text, flags=re.IGNORECASE)

    # Find phone pattern
    match = re.search(
        r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}',
        cleaned
    )
    if match:
        return match.group().strip()
    return None


def extract_linkedin(text: str) -> Optional[str]:
    """Extract a LinkedIn URL from text."""
    # Match full URL
    match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[\w-]+/?', text, re.IGNORECASE)
    if match:
        return match.group()

    # Match partial (linkedin.com/in/username)
    match = re.search(r'linkedin\.com/in/[\w-]+/?', text, re.IGNORECASE)
    if match:
        return 'https://' + match.group()

    return None


def clean_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean all entities extracted by the AI.
    This is the main function to call after AI extraction.
    """
    if not entities:
        return entities

    cleaned = {}

    for field, value in entities.items():
        if value is None:
            continue

        if isinstance(value, str):
            # Special handling for certain fields
            if field == 'email':
                extracted = extract_email(value)
                if extracted:
                    cleaned[field] = extracted
            elif field in ('linkedin', 'linkedin_url'):
                extracted = extract_linkedin(value)
                if extracted:
                    cleaned[field] = extracted
            elif field == 'phone':
                extracted = extract_phone(value)
                if extracted:
                    cleaned[field] = extracted
            else:
                cleaned_value = clean_field_value(field, value)
                if cleaned_value:
                    cleaned[field] = cleaned_value
        else:
            # Non-string values pass through
            cleaned[field] = value

    return cleaned


def clean_name(name: str) -> str:
    """
    Clean a name by removing common prefixes and normalizing.
    """
    if not name:
        return name

    # Remove common prefixes
    prefixes = [
        r'^(add|adding|new contact:?|contact:?)\s+',
        r'^(his|her|their)\s+name\s+is\s+',
        r'^(called|named)\s+',
    ]

    cleaned = name.strip()
    for pattern in prefixes:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()

    return smart_title_case(cleaned)
