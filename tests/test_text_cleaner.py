"""Tests for utils/text_cleaner.py — pure functions, no API calls."""

from utils.text_cleaner import (
    clean_field_value,
    extract_email,
    extract_phone,
    extract_linkedin,
    smart_title_case_for_job_title,
    sanitize_input,
    clean_name,
    clean_entities,
)


class TestCleanFieldValue:
    def test_title_strips_pronoun_prefix(self):
        assert clean_field_value("title", "He's the CEO") == "CEO"

    def test_title_strips_article(self):
        assert clean_field_value("title", "the CTO") == "CTO"

    def test_company_strips_preposition(self):
        assert clean_field_value("company", "at Synapse Analytics") == "Synapse Analytics"

    def test_company_strips_works_at(self):
        assert clean_field_value("company", "works at Google") == "Google"

    def test_email_strips_prefix(self):
        result = clean_field_value("email", "his email is john@test.com")
        assert result == "john@test.com"

    def test_empty_returns_empty(self):
        assert clean_field_value("title", "") == ""

    def test_none_returns_none(self):
        assert clean_field_value("title", None) is None


class TestExtractEmail:
    def test_simple_email(self):
        assert extract_email("reach me at alice@example.com") == "alice@example.com"

    def test_no_email(self):
        assert extract_email("no email here") is None

    def test_mixed_case(self):
        assert extract_email("Email: Alice@Example.COM") == "alice@example.com"


class TestExtractPhone:
    def test_us_format(self):
        result = extract_phone("call me at 555-123-4567")
        assert result is not None
        assert "555" in result

    def test_no_phone(self):
        assert extract_phone("no phone") is None


class TestExtractLinkedin:
    def test_full_url(self):
        result = extract_linkedin("check https://www.linkedin.com/in/janedoe")
        assert result is not None
        assert "linkedin.com/in/janedoe" in result

    def test_partial_url(self):
        result = extract_linkedin("linkedin.com/in/janedoe")
        assert result is not None
        assert result.startswith("https://")

    def test_no_linkedin(self):
        assert extract_linkedin("no profile") is None


class TestSmartTitleCaseForJobTitle:
    def test_preserves_acronyms(self):
        assert smart_title_case_for_job_title("ceo") == "CEO"
        assert smart_title_case_for_job_title("vp of engineering") == "VP of Engineering"

    def test_lowercase_connectors(self):
        result = smart_title_case_for_job_title("head of product")
        assert result == "Head of Product"


class TestSanitizeInput:
    def test_strips_script_tags(self):
        result = sanitize_input("<script>alert('xss')</script>hello")
        assert "<script>" not in result
        assert "hello" in result

    def test_limits_length(self):
        long_input = "a" * 6000
        result = sanitize_input(long_input, max_length=100)
        assert len(result) <= 104  # 100 + "..."

    def test_empty_input(self):
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


class TestCleanName:
    def test_strips_add_prefix(self):
        assert clean_name("add John Smith") == "John Smith"

    def test_title_cases(self):
        assert clean_name("jane doe") == "Jane Doe"


class TestCleanEntities:
    def test_full_dict(self):
        raw = {
            "name": "john doe",
            "email": "reach him at john@example.com",
            "title": "He's the CTO",
            "company": "at Acme Corp",
            "phone": "phone: 555-123-4567",
        }
        cleaned = clean_entities(raw)
        assert cleaned["email"] == "john@example.com"
        assert cleaned["title"] == "CTO"
        assert cleaned["company"] == "Acme Corp"

    def test_none_values_skipped(self):
        assert clean_entities({"name": None, "email": "a@b.com"}) == {"email": "a@b.com"}

    def test_empty_dict(self):
        assert clean_entities({}) == {}
