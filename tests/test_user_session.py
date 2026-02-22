"""Tests for Batch 4 — session lifecycle and eviction."""

from datetime import datetime, timedelta
from services.user_session import (
    get_user_session, _user_sessions, MAX_SESSIONS,
    UserSession, ContactDraft, DraftStatus,
)


class TestSessionLifecycle:
    def test_get_user_session_creates_new(self):
        session = get_user_session("user_1")
        assert session is not None
        assert session.user_id == "user_1"

    def test_get_user_session_returns_same(self):
        s1 = get_user_session("user_2")
        s2 = get_user_session("user_2")
        assert s1 is s2

    def test_start_new_contact(self):
        session = get_user_session("user_3")
        draft = session.start_new_contact("Jane Doe", title="CEO")
        assert draft.name == "Jane Doe"
        assert draft.title == "CEO"
        assert session.has_draft()

    def test_clear_session(self):
        session = get_user_session("user_4")
        session.start_new_contact("Test")
        session.clear()
        assert not session.has_draft()
        assert session.draft is None

    def test_mark_saved_clears_draft(self):
        session = get_user_session("user_5")
        session.start_new_contact("Test")
        saved = session.mark_saved()
        assert saved is not None
        assert saved.name == "Test"
        assert session.draft is None
        assert not session.has_draft()


class TestSessionEviction:
    def test_eviction_at_capacity(self):
        """When at MAX_SESSIONS, adding a new session evicts the oldest."""
        # Manually fill sessions up to capacity
        for i in range(MAX_SESSIONS):
            uid = f"evict_user_{i}"
            _user_sessions[uid] = UserSession(uid)

        # Make user_0 the oldest
        _user_sessions["evict_user_0"].last_activity = datetime.now() - timedelta(hours=2)

        assert len(_user_sessions) == MAX_SESSIONS

        # Adding one more should evict the oldest
        new_session = get_user_session("brand_new_user")
        assert new_session is not None
        assert "evict_user_0" not in _user_sessions
        assert "brand_new_user" in _user_sessions
        assert len(_user_sessions) == MAX_SESSIONS

    def test_no_eviction_under_capacity(self):
        """No eviction when under capacity."""
        s1 = get_user_session("cap_user_1")
        s2 = get_user_session("cap_user_2")
        assert "cap_user_1" in _user_sessions
        assert "cap_user_2" in _user_sessions


class TestDraftStatus:
    def test_mark_ready_to_save(self):
        session = get_user_session("status_user")
        session.start_new_contact("Test")
        session.mark_ready_to_save()
        # status may be the enum itself or its value depending on pydantic version
        status = session.draft.status
        assert status == DraftStatus.READY or status == DraftStatus.READY.value

    def test_context_summary_with_draft(self):
        session = get_user_session("ctx_user")
        session.start_new_contact("Alice")
        summary = session.get_context_summary()
        assert "Alice" in summary

    def test_context_summary_no_draft(self):
        session = get_user_session("ctx_user_2")
        assert "No active" in session.get_context_summary()
