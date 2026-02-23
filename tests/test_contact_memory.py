"""Tests for services/contact_memory.py — ContactMemoryService lifecycle."""

from unittest.mock import patch
import pytest

from services.contact_memory import (
    ContactMemoryService, ConversationState,
    TaskType, TaskStatus, ActiveTask, IntroDraftSlots, ContactDraftSlots,
)
from data.schema import Contact


class TestMemoryLifecycle:
    def test_get_memory_creates_new(self):
        svc = ContactMemoryService()
        mem = svc.get_memory("user_1")
        assert mem is not None
        assert mem.user_id == "user_1"

    def test_get_memory_returns_same(self):
        svc = ContactMemoryService()
        m1 = svc.get_memory("user_2")
        m2 = svc.get_memory("user_2")
        assert m1 is m2

    def test_start_collecting(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_3", contact)
        assert svc.is_collecting("user_3")
        assert svc.get_pending_contact("user_3").name == "Jane Doe"

    def test_hard_reset(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_4", contact)
        svc.hard_reset("user_4", "Jane Doe")
        assert not svc.is_collecting("user_4")
        assert svc.get_pending_contact("user_4") is None

    def test_cancel_pending(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_5", contact)
        svc.cancel_pending("user_5")
        assert not svc.is_collecting("user_5")


class TestUpdatePending:
    def test_updates_fields(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_6", contact)
        svc.update_pending("user_6", {"email": "jane@example.com", "company": "Acme"})
        pending = svc.get_pending_contact("user_6")
        assert pending.email == "jane@example.com"
        assert pending.company == "Acme"

    def test_update_nonexistent_returns_false(self):
        svc = ContactMemoryService()
        assert svc.update_pending("nobody", {"email": "x@y.com"}) is False


class TestResearchSummary:
    def test_set_research_summary(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_7", contact)
        svc.set_research_summary("user_7", "Experienced SaaS founder")
        pending = svc.get_pending_contact("user_7")
        assert pending.research_summary == "Experienced SaaS founder"

    def test_append_notes(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_8", contact)
        svc.append_notes("user_8", "Met at conference")
        pending = svc.get_pending_contact("user_8")
        assert "Met at conference" in pending.notes

    def test_append_notes_accumulates(self):
        svc = ContactMemoryService()
        contact = Contact(full_name="Jane Doe")
        svc.start_collecting("user_9", contact)
        svc.append_notes("user_9", "First note")
        svc.append_notes("user_9", "Second note")
        pending = svc.get_pending_contact("user_9")
        assert "First note" in pending.notes
        assert "Second note" in pending.notes


class TestExpiryCleanup:
    def test_cleanup_removes_expired(self):
        from datetime import datetime, timedelta
        svc = ContactMemoryService()
        mem = svc.get_memory("stale_user")
        mem.last_activity = datetime.now() - timedelta(hours=24)
        svc.cleanup_expired()
        # After cleanup, getting the memory should create a fresh one
        new_mem = svc.get_memory("stale_user")
        assert new_mem.state == ConversationState.IDLE
        assert new_mem.pending_contact is None


class TestTaskStack:
    """Tests for task-stack dialog orchestration."""

    def test_park_switch_contact_draft(self):
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        ahmed = Contact(full_name="Ahmed")
        svc.start_collecting("ts1", ryan)
        svc.start_collecting("ts1", ahmed)
        mem = svc.get_memory("ts1")
        # Ahmed is active, Ryan is parked
        active = mem.task_stack.active_task
        assert active.task_type == TaskType.CONTACT_DRAFT
        assert active.slots.contact.name == "Ahmed"
        parked = mem.task_stack.get_parked_tasks()
        assert len(parked) == 1
        assert parked[0].slots.contact.name == "Ryan"
        assert mem.pending_contact.name == "Ahmed"

    def test_save_active_resumes_parked(self):
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        ahmed = Contact(full_name="Ahmed")
        svc.start_collecting("ts2", ryan)
        svc.start_collecting("ts2", ahmed)
        svc.hard_reset("ts2", "Ahmed")
        mem = svc.get_memory("ts2")
        # Ahmed is locked, Ryan is restored as pending/current/COLLECTING
        assert "ahmed" in mem.locked_contacts
        assert mem.pending_contact is not None
        assert mem.pending_contact.name == "Ryan"
        assert mem.current_contact.name == "Ryan"
        assert mem.state == ConversationState.COLLECTING

    def test_draft_intro_save_commits(self):
        svc = ContactMemoryService()
        mem = svc.get_memory("ts3")
        intro_task = ActiveTask(
            task_type=TaskType.INTRO_DRAFT,
            status=TaskStatus.ACTIVE,
            slots=IntroDraftSlots(connector="Alice", target="Bob"),
            label="Intro: Alice → Bob",
        )
        mem.task_stack.push(intro_task)
        mem.task_stack.complete_active()
        # Stack empty, no side effects on pending
        assert mem.task_stack.active_task is None
        assert mem.pending_contact is None

    def test_draft_intro_cancel_resumes_parked_contact(self):
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        svc.start_collecting("ts4", ryan)
        mem = svc.get_memory("ts4")
        intro_task = ActiveTask(
            task_type=TaskType.INTRO_DRAFT,
            status=TaskStatus.ACTIVE,
            slots=IntroDraftSlots(connector="Alice", target="Bob"),
            label="Intro: Alice → Bob",
        )
        mem.task_stack.push(intro_task)
        # Ryan should be parked now
        assert mem.task_stack.active_task.task_type == TaskType.INTRO_DRAFT
        # Cancel the intro — Ryan should resume
        resumed = mem.cancel_pending()
        assert resumed is not None
        assert resumed.task_type == TaskType.CONTACT_DRAFT
        assert resumed.slots.contact.name == "Ryan"
        assert mem.pending_contact.name == "Ryan"
        assert mem.current_contact.name == "Ryan"
        assert mem.state == ConversationState.COLLECTING

    @patch("services.agent_tools.find_contact_in_storage", return_value=None)
    def test_workflow_status_active(self, mock_storage):
        from services.agent_tools import AgentTools
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        svc.start_collecting("ts5", ryan)
        tools = AgentTools("ts5")
        tools.memory = svc
        result = pytest.importorskip("asyncio").get_event_loop().run_until_complete(
            tools.get_workflow_status("Ryan")
        )
        assert "still being edited" in result

    @patch("services.agent_tools.find_contact_in_storage", return_value=None)
    def test_workflow_status_parked(self, mock_storage):
        from services.agent_tools import AgentTools
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        ahmed = Contact(full_name="Ahmed")
        svc.start_collecting("ts6", ryan)
        svc.start_collecting("ts6", ahmed)
        tools = AgentTools("ts6")
        tools.memory = svc
        result = pytest.importorskip("asyncio").get_event_loop().run_until_complete(
            tools.get_workflow_status("Ryan")
        )
        assert "parked" in result.lower()

    @patch("services.agent_tools.find_contact_in_storage", return_value=None)
    def test_workflow_status_saved(self, mock_storage):
        from services.agent_tools import AgentTools
        svc = ContactMemoryService()
        ryan = Contact(full_name="Ryan")
        svc.start_collecting("ts7", ryan)
        svc.hard_reset("ts7", "Ryan")
        tools = AgentTools("ts7")
        tools.memory = svc
        result = pytest.importorskip("asyncio").get_event_loop().run_until_complete(
            tools.get_workflow_status("Ryan")
        )
        assert "saved" in result.lower()
