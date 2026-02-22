"""Tests for Batch 3 — classification returns 'unknown' when no matches."""

from services.classification import ClassificationService


class TestClassifyByRules:
    def test_zero_matches_returns_unknown(self):
        """When no keywords match, should return 'unknown' with low confidence."""
        svc = ClassificationService()
        classification, confidence = svc.classify_by_rules({})
        assert classification == "unknown"
        assert confidence == 0.2

    def test_zero_matches_with_irrelevant_data(self):
        svc = ClassificationService()
        classification, confidence = svc.classify_by_rules({
            "name": "xyz",
            "job_title": "baker",
            "company": "bakery llc",
        })
        assert classification == "unknown"
        assert confidence == 0.2

    def test_founder_keywords_detected(self):
        svc = ClassificationService()
        classification, confidence = svc.classify_by_rules({
            "job_title": "co-founder and CEO",
        })
        assert classification == "founder"
        assert confidence > 0.2

    def test_investor_keywords_detected(self):
        svc = ClassificationService()
        classification, confidence = svc.classify_by_rules({
            "job_title": "partner",
            "company": "ABC Ventures Capital",
        })
        assert classification == "investor"
        assert confidence > 0.2
