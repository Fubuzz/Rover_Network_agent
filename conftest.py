"""
Project-root fixtures for the Rover Network Agent test suite.
Provides mocks for AI, Airtable, and memory state so tests run
without any external API calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from data.schema import Contact
from services.contact_memory import get_memory_service


# ── AI service mock ──────────────────────────────────────────
@pytest.fixture
def mock_ai_service():
    """Patch get_ai_service with a MagicMock."""
    mock = MagicMock()
    mock.generate_response.return_value = "mocked AI response"
    mock.classify_contact.return_value = {"classification": "founder", "confidence": 0.8}
    with patch("services.ai_service.get_ai_service", return_value=mock):
        yield mock


# ── Airtable / sheets service mock ──────────────────────────
@pytest.fixture
def mock_airtable():
    """Patch get_sheets_service with a MagicMock pre-loaded with helpers."""
    mock = MagicMock()
    mock._ensure_initialized.return_value = None
    mock.get_all_contacts.return_value = []
    mock.get_contact_by_name.return_value = None
    mock.find_contact_by_email.return_value = None
    mock.add_contact.return_value = True
    mock.update_contact.return_value = True
    mock.search_contacts.return_value = []
    with patch("services.airtable_service.get_sheets_service", return_value=mock):
        yield mock


# ── Memory cleanup ──────────────────────────────────────────
@pytest.fixture(autouse=True)
def clean_memory():
    """Clear ContactMemoryService._memories before and after each test."""
    svc = get_memory_service()
    svc._memories.clear()
    yield
    svc._memories.clear()


# ── Reusable test data ───────────────────────────────────────
@pytest.fixture
def sample_contact():
    """A fully-populated Contact for testing."""
    return Contact(
        full_name="Jane Doe",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="+1-555-123-4567",
        company="Acme Inc",
        title="CEO",
        contact_type="Founder",
        industry="SaaS",
        address="San Francisco, CA",
        linkedin_url="https://linkedin.com/in/janedoe",
        company_description="Cloud-based SaaS platform",
    )
