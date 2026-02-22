"""Tests for Airtable formula escaping — no API calls."""

from services.airtable_service import _escape_airtable_value


class TestEscapeAirtableValue:
    def test_single_quote(self):
        assert _escape_airtable_value("O'Brien") == "O\\'Brien"

    def test_multiple_quotes(self):
        assert _escape_airtable_value("it's a 'test'") == "it\\'s a \\'test\\'"

    def test_empty_string(self):
        assert _escape_airtable_value("") == ""

    def test_no_quotes(self):
        assert _escape_airtable_value("John Smith") == "John Smith"
