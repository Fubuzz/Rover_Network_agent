"""Tests for Batch 2 — name normalization and early dedup."""

import pytest
from unittest.mock import patch, MagicMock
from services.agent_tools import _normalize_name


class TestNormalizeName:
    def test_basic(self):
        assert _normalize_name("John Smith") == "john smith"

    def test_extra_whitespace(self):
        assert _normalize_name("  John   Smith  ") == "john smith"

    def test_empty_string(self):
        assert _normalize_name("") == ""

    def test_none(self):
        assert _normalize_name(None) == ""

    def test_case_insensitive(self):
        assert _normalize_name("JOHN SMITH") == "john smith"


class TestEarlyDuplicateDetection:
    """Test that add_contact rejects duplicates early."""

    @pytest.mark.asyncio
    async def test_rejects_existing_name(self):
        """add_contact should reject when name already exists in storage."""
        from data.schema import Contact
        existing = Contact(full_name="Jane Doe", email="jane@example.com")

        with patch("services.agent_tools.find_contact_in_storage", return_value=existing), \
             patch("services.agent_tools.get_memory_service") as mock_mem:
            mock_svc = MagicMock()
            mock_svc.is_collecting.return_value = False
            mock_mem.return_value = mock_svc

            from services.agent_tools import AgentTools
            tools = AgentTools.__new__(AgentTools)
            tools.user_id = "test_user"
            tools.memory = mock_svc

            result = await tools.add_contact(name="Jane Doe")
            assert "already exists" in result

    @pytest.mark.asyncio
    async def test_rejects_existing_email(self):
        """add_contact should reject when email already used."""
        from data.schema import Contact
        existing = Contact(full_name="Jane Doe", email="jane@example.com")

        mock_sheets = MagicMock()
        mock_sheets.find_contact_by_email.return_value = existing

        with patch("services.agent_tools.find_contact_in_storage", return_value=None), \
             patch("services.agent_tools.get_sheets_service", return_value=mock_sheets), \
             patch("services.agent_tools.get_memory_service") as mock_mem:
            mock_svc = MagicMock()
            mock_svc.is_collecting.return_value = False
            mock_mem.return_value = mock_svc

            from services.agent_tools import AgentTools
            tools = AgentTools.__new__(AgentTools)
            tools.user_id = "test_user"
            tools.memory = mock_svc

            result = await tools.add_contact(name="John Smith", email="jane@example.com")
            assert "already belongs to" in result
