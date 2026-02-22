"""Tests for services/contact_memory.py — ContactMemoryService lifecycle."""

from services.contact_memory import ContactMemoryService, ConversationState
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
