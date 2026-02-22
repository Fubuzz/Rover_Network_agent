"""Tests for services/user_session.py ContactDraft model — no API calls."""

from services.user_session import ContactDraft


class TestUpdateField:
    def test_valid_email_accepted(self):
        d = ContactDraft(name="Test")
        assert d.update_field("email", "a@b.com") is True
        assert d.email == "a@b.com"

    def test_invalid_email_rejected(self):
        d = ContactDraft(name="Test")
        assert d.update_field("email", "not-an-email") is False
        assert d.email is None

    def test_valid_linkedin_accepted(self):
        d = ContactDraft(name="Test")
        assert d.update_field("linkedin_url", "https://linkedin.com/in/johndoe") is True

    def test_invalid_linkedin_rejected(self):
        d = ContactDraft(name="Test")
        assert d.update_field("linkedin_url", "https://twitter.com/johndoe") is False
        assert d.linkedin_url is None

    def test_empty_value_rejected(self):
        d = ContactDraft(name="Test")
        assert d.update_field("title", "") is False
        assert d.update_field("title", None) is False


class TestCleanPhone:
    def test_strips_invalid_chars(self):
        d = ContactDraft(name="Test")
        d.update_field("phone", "+1 (555) 123-4567")
        assert d.phone == "+1 (555) 123-4567"

    def test_removes_letters(self):
        d = ContactDraft(name="Test")
        d.update_field("phone", "call 555-123-4567 now")
        # Letters removed, only phone chars remain
        assert "555" in d.phone


class TestGetMissingFields:
    def test_all_missing(self):
        d = ContactDraft(name="Test")
        missing = d.get_missing_fields()
        assert "email" in missing
        assert "phone" in missing
        assert "LinkedIn" in missing
        assert "company" in missing

    def test_none_missing(self):
        d = ContactDraft(name="Test")
        d.update_field("email", "a@b.com")
        d.update_field("phone", "+1-555-1234567")
        d.update_field("linkedin_url", "https://linkedin.com/in/test")
        d.update_field("company", "Acme")
        assert d.get_missing_fields() == []


class TestIsComplete:
    def test_complete_with_name(self):
        assert ContactDraft(name="Jane").is_complete() is True

    def test_incomplete_without_name(self):
        assert ContactDraft().is_complete() is False


class TestToContactDict:
    def test_basic_mapping(self):
        d = ContactDraft(name="Jane Doe")
        d.update_field("email", "jane@example.com")
        result = d.to_contact_dict()
        assert result["full_name"] == "Jane Doe"
        assert result["email"] == "jane@example.com"
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Doe"

    def test_source_is_telegram(self):
        d = ContactDraft(name="Test")
        assert d.to_contact_dict()["source"] == "telegram"


class TestGetDisplayCard:
    def test_includes_name(self):
        d = ContactDraft(name="Jane Doe")
        card = d.get_display_card()
        assert "Jane Doe" in card

    def test_includes_title_and_company(self):
        d = ContactDraft(name="Jane Doe")
        d.update_field("title", "CEO")
        d.update_field("company", "Acme")
        card = d.get_display_card()
        assert "CEO" in card
        assert "Acme" in card
