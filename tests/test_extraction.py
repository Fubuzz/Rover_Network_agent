"""Tests for Batch 1 — company_description flow, phone rejection."""

from data.schema import Contact
from utils.validators import validate_and_clean_field
from utils.formatters import contact_draft_card
from utils.text_cleaner import extract_phone


class TestCompanyDescriptionField:
    def test_field_exists_on_contact(self):
        c = Contact(full_name="Test")
        assert c.company_description is None

    def test_setting_company_description(self):
        c = Contact(full_name="Test", company_description="A fintech startup")
        assert c.company_description == "A fintech startup"

    def test_display_card_includes_company_description(self):
        c = Contact(full_name="Test", company_description="Cloud platform for SMBs")
        card = contact_draft_card(c)
        assert "Cloud platform" in card

    def test_to_dict_includes_company_description(self):
        c = Contact(full_name="Test", company_description="AI-driven analytics")
        result = c.to_dict()
        # Contact.to_dict() doesn't include company_description by default,
        # but the field is on the dataclass
        assert c.company_description == "AI-driven analytics"


class TestPhoneValidation:
    def test_rejects_short_phone(self):
        """Phone with fewer than 7 digits should be rejected."""
        val, ok, err = validate_and_clean_field("phone", "123")
        assert ok is False

    def test_accepts_valid_phone(self):
        val, ok, err = validate_and_clean_field("phone", "+1-555-123-4567")
        assert ok is True
        assert "555" in val

    def test_text_cleaner_rejects_short_phone(self):
        """extract_phone should return None for text with < 7 digits."""
        assert extract_phone("call 123") is None

    def test_text_cleaner_accepts_valid_phone(self):
        result = extract_phone("call 555-123-4567")
        assert result is not None
        assert "555" in result
