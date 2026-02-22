"""Tests for Batch 4 — pure functions from agent_tools module level."""

from services.agent_tools import (
    _normalize_name,
    extract_linkedin_url,
    extract_email,
    extract_phone,
)


class TestExtractLinkedinUrl:
    def test_valid_url(self):
        result = extract_linkedin_url("check https://www.linkedin.com/in/johndoe")
        assert result == "https://www.linkedin.com/in/johndoe"

    def test_no_url(self):
        assert extract_linkedin_url("no url here") is None

    def test_url_with_trailing_slash(self):
        result = extract_linkedin_url("https://linkedin.com/in/johndoe/")
        assert result is not None
        assert "johndoe" in result


class TestModuleLevelExtractEmail:
    def test_valid_email(self):
        result = extract_email("email is john@example.com ok")
        assert result == "john@example.com"

    def test_no_email(self):
        assert extract_email("no email") is None

    def test_short_email_rejected(self):
        """Very short emails (< 6 chars) should be rejected."""
        assert extract_email("a@b") is None


class TestModuleLevelExtractPhone:
    def test_valid_phone(self):
        result = extract_phone("call 555-123-4567")
        assert result is not None

    def test_short_phone_rejected(self):
        assert extract_phone("123") is None

    def test_international_format(self):
        result = extract_phone("+1 (555) 123-4567")
        assert result is not None


class TestNormalizeName:
    def test_normalizes_case_and_whitespace(self):
        assert _normalize_name("  John   DOE  ") == "john doe"

    def test_empty(self):
        assert _normalize_name("") == ""
