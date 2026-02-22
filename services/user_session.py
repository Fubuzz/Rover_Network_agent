"""
User Session Management for Contact Draft State.

This module implements a "Shopping Cart" pattern where research data
is accumulated in a ContactDraft object before being saved to Airtable.

Fixes:
- Amnesia: Data persists in draft until explicitly saved
- Hallucination: Save reads from draft, not LLM guesses
- Nagging: Clear state transitions prevent loops
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import re


class DraftStatus(Enum):
    """Status of the contact draft."""
    COLLECTING = "collecting"  # Still gathering data
    ENRICHING = "enriching"    # Research in progress
    REVIEW = "review"          # Ready for user review
    READY = "ready"            # User confirmed, ready to save
    SAVED = "saved"            # Already saved to Airtable


class ContactDraft(BaseModel):
    """
    A draft contact being built up before saving.
    Acts as a "shopping cart" for contact data.
    """
    # Core fields
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Professional info
    title: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    company_description: Optional[str] = None
    contact_type: Optional[str] = None  # Founder, Enabler, Investor

    # Contact info
    email: Optional[str] = None
    phone: Optional[str] = None

    # Online presence
    linkedin_url: Optional[str] = None
    company_linkedin: Optional[str] = None
    website: Optional[str] = None

    # Location
    location: Optional[str] = None

    # Research findings (append-only)
    notes: str = ""
    research_summary: str = ""

    # Metadata
    status: DraftStatus = DraftStatus.COLLECTING
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True

    def update_field(self, field: str, value: Any) -> bool:
        """Update a field with validation."""
        if not value:
            return False

        # Email validation
        if field == "email":
            if not self._is_valid_email(value):
                return False

        # LinkedIn URL validation
        if field in ("linkedin_url", "company_linkedin"):
            if not self._is_valid_linkedin(value):
                return False

        # Phone validation - basic cleanup
        if field == "phone":
            value = self._clean_phone(value)
            if not value:
                return False

        setattr(self, field, value)
        self.last_updated = datetime.now()
        return True

    def append_notes(self, text: str):
        """Append research findings to notes."""
        if text and text.strip():
            timestamp = datetime.now().strftime("%H:%M")
            if self.notes:
                self.notes += f"\n\n[{timestamp}] {text.strip()}"
            else:
                self.notes = f"[{timestamp}] {text.strip()}"
            self.last_updated = datetime.now()

    def set_research_summary(self, summary: str):
        """Set the research summary."""
        if summary and summary.strip():
            self.research_summary = summary.strip()
            self.last_updated = datetime.now()

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        if not email or "@" not in email:
            return False
        # Basic email pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip()))

    def _is_valid_linkedin(self, url: str) -> bool:
        """Validate LinkedIn URL."""
        if not url:
            return False
        return "linkedin.com" in url.lower()

    def _clean_phone(self, phone: str) -> str:
        """Clean phone number. Reject if fewer than 7 digits."""
        # Keep only digits, +, -, (, ), and spaces
        cleaned = re.sub(r'[^\d+\-() ]', '', phone)
        digits_only = re.sub(r'\D', '', cleaned)
        if len(digits_only) < 7:
            return ""
        return cleaned.strip()

    def get_display_card(self) -> str:
        """Get a formatted display of the draft."""
        lines = []

        if self.name:
            lines.append(f"**{self.name}**")

        if self.title and self.company:
            lines.append(f"_{self.title} at {self.company}_")
        elif self.title:
            lines.append(f"_{self.title}_")
        elif self.company:
            lines.append(f"_at {self.company}_")

        lines.append("")

        if self.email:
            lines.append(f"📧 {self.email}")
        if self.phone:
            lines.append(f"📱 {self.phone}")
        if self.linkedin_url:
            lines.append(f"🔗 {self.linkedin_url}")
        if self.location:
            lines.append(f"📍 {self.location}")
        if self.industry:
            lines.append(f"🏢 {self.industry}")
        if self.contact_type:
            lines.append(f"👤 {self.contact_type}")
        if self.company_description:
            desc = self.company_description
            if len(desc) > 100:
                desc = desc[:100] + "..."
            lines.append(f"📄 {desc}")

        if self.research_summary:
            lines.append("")
            summary = self.research_summary
            if len(summary) > 200:
                summary = summary[:200] + "..."
            lines.append(f"**Summary:** {summary}")

        return "\n".join(lines)

    def to_contact_dict(self) -> Dict[str, Any]:
        """Convert draft to a dict for saving to Airtable."""
        # Split name into parts if needed
        first_name = self.first_name
        last_name = self.last_name

        if self.name and not first_name:
            parts = self.name.split()
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        return {
            "full_name": self.name,
            "first_name": first_name,
            "last_name": last_name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "source": "telegram",
            "status": "active",
            # Note: These fields may not exist in Airtable yet
            # but are stored for reference
            "_title": self.title,
            "_linkedin_url": self.linkedin_url,
            "_industry": self.industry,
            "_location": self.location,
            "_contact_type": self.contact_type,
            "_company_description": self.company_description,
            "_notes": self.notes,
            "_research_summary": self.research_summary,
        }

    def is_complete(self) -> bool:
        """Check if draft has minimum required fields."""
        return bool(self.name)

    def get_missing_fields(self) -> List[str]:
        """Get list of empty important fields."""
        missing = []
        if not self.email:
            missing.append("email")
        if not self.phone:
            missing.append("phone")
        if not self.linkedin_url:
            missing.append("LinkedIn")
        if not self.company:
            missing.append("company")
        return missing


class UserSession:
    """
    Session state for a single user.
    Maintains the draft contact and conversation context.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.draft: Optional[ContactDraft] = None
        self.last_action: str = "idle"
        self.last_search_query: Optional[str] = None
        self.last_search_results: List[Dict] = []
        self.pending_confirmation: Optional[str] = None
        self.created_at: datetime = datetime.now()
        self.last_activity: datetime = datetime.now()

    def start_new_contact(self, name: str, **kwargs) -> ContactDraft:
        """Start a new contact draft."""
        self.draft = ContactDraft(name=name, **kwargs)
        self.last_action = "add"
        self.last_activity = datetime.now()
        return self.draft

    def get_or_create_draft(self, name: str = None) -> ContactDraft:
        """Get existing draft or create new one."""
        if self.draft is None:
            self.draft = ContactDraft(name=name)
        elif name and not self.draft.name:
            self.draft.name = name
        return self.draft

    def update_draft(self, **kwargs) -> bool:
        """Update draft fields."""
        if self.draft is None:
            return False

        updated = False
        for field, value in kwargs.items():
            if value and hasattr(self.draft, field):
                if self.draft.update_field(field, value):
                    updated = True

        if updated:
            self.last_action = "update"
            self.last_activity = datetime.now()

        return updated

    def append_research(self, text: str):
        """Append research findings to draft notes."""
        if self.draft:
            self.draft.append_notes(text)
            self.last_action = "research"
            self.last_activity = datetime.now()

    def set_research_summary(self, summary: str):
        """Set the research summary on draft."""
        if self.draft:
            self.draft.set_research_summary(summary)

    def store_search_results(self, query: str, results: List[Dict]):
        """Store search results for later reference."""
        self.last_search_query = query
        self.last_search_results = results
        self.last_activity = datetime.now()

    def mark_ready_to_save(self):
        """Mark draft as ready to save."""
        if self.draft:
            self.draft.status = DraftStatus.READY
            self.last_action = "ready"

    def mark_saved(self):
        """Mark draft as saved and clear it."""
        saved_draft = self.draft
        self.draft = None
        self.last_action = "saved"
        self.last_search_query = None
        self.last_search_results = []
        self.pending_confirmation = None
        return saved_draft

    def clear(self):
        """Clear the session completely."""
        self.draft = None
        self.last_action = "cleared"
        self.last_search_query = None
        self.last_search_results = []
        self.pending_confirmation = None

    def has_draft(self) -> bool:
        """Check if there's an active draft."""
        return self.draft is not None and self.draft.name is not None

    def get_context_summary(self) -> str:
        """Get session context for AI."""
        if not self.draft:
            return "No active contact draft."

        return f"Working on: {self.draft.name} | Status: {self.draft.status} | Last action: {self.last_action}"


# Global session storage
_user_sessions: Dict[str, UserSession] = {}
MAX_SESSIONS = 1000


def get_user_session(user_id: str) -> UserSession:
    """Get or create a user session. Evicts oldest when at capacity."""
    if user_id not in _user_sessions:
        if len(_user_sessions) >= MAX_SESSIONS:
            oldest = min(_user_sessions, key=lambda uid: _user_sessions[uid].last_activity)
            del _user_sessions[oldest]
        _user_sessions[user_id] = UserSession(user_id)
    return _user_sessions[user_id]


def clear_user_session(user_id: str):
    """Clear a user's session."""
    if user_id in _user_sessions:
        _user_sessions[user_id].clear()


def get_all_sessions() -> Dict[str, UserSession]:
    """Get all active sessions (for debugging)."""
    return _user_sessions
