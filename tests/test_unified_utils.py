"""Tests for unified utility functions — replacements for ContactDraft methods."""

import pytest
from utils.validators import validate_and_clean_field
from utils.formatters import contact_draft_card, contact_missing_fields
from data.schema import Contact


# ── validate_and_clean_field ────────────────────────────────

class TestValidateAndCleanFieldEmail:
    def test_valid_email(self):
        val, ok, err = validate_and_clean_field("email", "A@B.COM")
        assert ok is True
        assert val == "a@b.com"  # lowercased

    def test_invalid_email(self):
        val, ok, err = validate_and_clean_field("email", "not-an-email")
        assert ok is False
        assert "Invalid email" in err

    def test_empty_email(self):
        val, ok, err = validate_and_clean_field("email", "")
        assert ok is True


class TestValidateAndCleanFieldPhone:
    def test_valid_phone(self):
        val, ok, err = validate_and_clean_field("phone", "+1 (555) 123-4567")
        assert ok is True
        assert "555" in val

    def test_short_phone_rejected(self):
        val, ok, err = validate_and_clean_field("phone", "123")
        assert ok is False
        assert "too short" in err

    def test_strips_letters(self):
        val, ok, err = validate_and_clean_field("phone", "call 555-123-4567 now")
        assert ok is True
        assert "555" in val


class TestValidateAndCleanFieldLinkedIn:
    def test_valid_linkedin(self):
        val, ok, err = validate_and_clean_field("linkedin_url", "https://linkedin.com/in/test")
        assert ok is True

    def test_invalid_linkedin(self):
        val, ok, err = validate_and_clean_field("linkedin_url", "https://twitter.com/foo")
        assert ok is False
        assert "LinkedIn" in err

    def test_company_linkedin(self):
        val, ok, err = validate_and_clean_field("company_linkedin", "https://linkedin.com/company/acme")
        assert ok is True


class TestValidateAndCleanFieldPassthrough:
    def test_strips_whitespace(self):
        val, ok, err = validate_and_clean_field("title", "  CEO  ")
        assert ok is True
        assert val == "CEO"

    def test_empty_passthrough(self):
        val, ok, err = validate_and_clean_field("title", None)
        assert ok is True


# ── contact_draft_card ──────────────────────────────────────

class TestContactDraftCard:
    def test_includes_name(self):
        c = Contact(full_name="Jane Doe")
        card = contact_draft_card(c)
        assert "Jane Doe" in card

    def test_includes_title_and_company(self):
        c = Contact(full_name="Jane Doe", title="CEO", company="Acme")
        card = contact_draft_card(c)
        assert "CEO" in card
        assert "Acme" in card

    def test_includes_email(self):
        c = Contact(full_name="Jane Doe", email="jane@example.com")
        card = contact_draft_card(c)
        assert "jane@example.com" in card

    def test_includes_research_summary(self):
        c = Contact(full_name="Jane Doe")
        c.research_summary = "Experienced founder in SaaS"
        card = contact_draft_card(c)
        assert "Experienced founder" in card

    def test_truncates_long_company_description(self):
        c = Contact(full_name="Test", company_description="A" * 200)
        card = contact_draft_card(c)
        assert "..." in card


# ── contact_missing_fields ──────────────────────────────────

class TestContactMissingFields:
    def test_all_missing(self):
        c = Contact(full_name="Test")
        missing = contact_missing_fields(c)
        assert "email" in missing
        assert "phone" in missing
        assert "LinkedIn" in missing
        assert "company" in missing

    def test_none_missing(self):
        c = Contact(
            full_name="Test",
            email="a@b.com",
            phone="+15551234567",
            linkedin_url="https://linkedin.com/in/test",
            company="Acme",
        )
        assert contact_missing_fields(c) == []

    def test_partial_missing(self):
        c = Contact(full_name="Test", email="a@b.com")
        missing = contact_missing_fields(c)
        assert "email" not in missing
        assert "phone" in missing
