"""Tests for Batch 1 — company_description flow, phone rejection."""

from services.user_session import ContactDraft
from utils.text_cleaner import extract_phone


class TestCompanyDescriptionField:
    def test_field_exists_on_draft(self):
        d = ContactDraft(name="Test")
        assert d.company_description is None

    def test_update_field_sets_company_description(self):
        d = ContactDraft(name="Test")
        assert d.update_field("company_description", "A fintech startup") is True
        assert d.company_description == "A fintech startup"

    def test_display_card_includes_company_description(self):
        d = ContactDraft(name="Test")
        d.update_field("company_description", "Cloud platform for SMBs")
        card = d.get_display_card()
        assert "Cloud platform" in card

    def test_to_contact_dict_includes_company_description(self):
        d = ContactDraft(name="Test")
        d.update_field("company_description", "AI-driven analytics")
        result = d.to_contact_dict()
        assert result["_company_description"] == "AI-driven analytics"


class TestPhoneValidation:
    def test_draft_rejects_short_phone(self):
        """Phone with fewer than 7 digits should be cleaned to empty string."""
        d = ContactDraft(name="Test")
        d.update_field("phone", "123")
        # _clean_phone returns "" for < 7 digits, but update_field
        # still sets the field to the cleaned value (empty string)
        # Since empty string is falsy, the field retains its default
        assert not d.phone or d.phone == ""

    def test_draft_accepts_valid_phone(self):
        d = ContactDraft(name="Test")
        d.update_field("phone", "+1-555-123-4567")
        assert d.phone == "+1-555-123-4567"

    def test_text_cleaner_rejects_short_phone(self):
        """extract_phone should return None for text with < 7 digits."""
        assert extract_phone("call 123") is None

    def test_text_cleaner_accepts_valid_phone(self):
        result = extract_phone("call 555-123-4567")
        assert result is not None
        assert "555" in result
