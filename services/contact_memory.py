"""
Persistent Contact Memory Service.
Tracks conversation context and recent contacts per user.
Includes conversation state management for smarter multi-message flows.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import OrderedDict
from enum import Enum

from data.schema import Contact
from config import SessionConfig


class ConversationState(Enum):
    """States for the conversation flow."""
    IDLE = "idle"              # No active contact, waiting for new input
    COLLECTING = "collecting"  # Actively gathering info about a contact (not yet saved)
    CONFIRMING = "confirming"  # Showing summary, waiting for save confirmation


@dataclass
class UserMemory:
    """Memory state for a single user."""
    user_id: str
    current_contact: Optional[Contact] = None
    pending_contact: Optional[Contact] = None  # Contact being built, not yet saved
    recent_contacts: OrderedDict = field(default_factory=OrderedDict)  # name -> Contact
    locked_contacts: Dict[str, Contact] = field(default_factory=dict)  # name -> Contact (LOCKED after save)
    last_saved_contact: Optional[str] = None  # Name of last saved contact (for debugging)
    last_saved_company: Optional[str] = None  # Company of last saved contact (for enrichment)
    last_activity: datetime = field(default_factory=datetime.now)
    last_message_time: Optional[datetime] = None  # For detecting rapid messages
    message_count: int = 0
    state: ConversationState = ConversationState.IDLE
    auto_saved: bool = False  # Flag to notify user if contact was auto-saved

    # Settings - use config values with fallback defaults
    MAX_RECENT_CONTACTS = 10
    EXPIRY_MINUTES = SessionConfig.MEMORY_EXPIRY_MINUTES  # Memory expires after inactivity
    CONTINUATION_SECONDS = SessionConfig.CONTINUATION_SECONDS  # Messages within this window are continuation
    TIMEOUT_SECONDS = SessionConfig.TIMEOUT_SECONDS  # Session timeout for prompting user
    
    def is_expired(self) -> bool:
        """Check if this memory has expired."""
        return datetime.now() - self.last_activity > timedelta(minutes=self.EXPIRY_MINUTES)
    
    def touch(self):
        """Update last activity time and message time."""
        now = datetime.now()
        self.last_activity = now
        self.last_message_time = now
        self.message_count += 1
    
    def set_current_contact(self, contact: Contact):
        """Set the current contact being discussed."""
        self.current_contact = contact
        self._add_to_recent(contact)
        self.touch()
    
    def _add_to_recent(self, contact: Contact):
        """Add a contact to the recent list."""
        if not contact or not contact.name:
            return
        
        name = contact.name.lower()
        
        # Remove if already exists (will be re-added at end)
        if name in self.recent_contacts:
            del self.recent_contacts[name]
        
        # Add to end (most recent)
        self.recent_contacts[name] = contact
        
        # Trim to max size
        while len(self.recent_contacts) > self.MAX_RECENT_CONTACTS:
            self.recent_contacts.popitem(last=False)
    
    def get_recent_names(self) -> List[str]:
        """Get list of recent contact names (most recent last)."""
        return [c.name for c in self.recent_contacts.values() if c.name]
    
    def find_contact_by_name(self, name: str) -> Optional[Contact]:
        """Find a contact from recent memory by name (case-insensitive partial match)."""
        if not name:
            return None
        
        name_lower = name.lower()
        
        # Exact match first
        if name_lower in self.recent_contacts:
            return self.recent_contacts[name_lower]
        
        # Partial match (first name or last name)
        for stored_name, contact in self.recent_contacts.items():
            if name_lower in stored_name:
                return contact
            # Check if any part of the name matches
            if contact.name:
                name_parts = contact.name.lower().split()
                if any(name_lower == part for part in name_parts):
                    return contact
        
        return None
    
    def clear_current(self):
        """Clear the current contact (but keep in recent)."""
        self.current_contact = None
        self.touch()

    def start_collecting(self, contact: Contact):
        """Start collecting info for a new contact (not saved yet)."""
        self.pending_contact = contact
        self.current_contact = contact  # Also set as current for context
        self.state = ConversationState.COLLECTING
        self._add_to_recent(contact)
        self.touch()

    def update_pending(self, updates: Dict[str, Any]) -> bool:
        """Update the pending contact with new data."""
        contact = self.pending_contact or self.current_contact
        if not contact:
            return False

        for key, value in updates.items():
            if value and hasattr(contact, key):
                setattr(contact, key, value)

        # Keep both in sync
        if self.pending_contact:
            self.current_contact = self.pending_contact

        # Update in recent contacts too
        if contact.name:
            name_lower = contact.name.lower()
            self.recent_contacts[name_lower] = contact

        self.touch()
        return True

    def get_pending_contact(self) -> Optional[Contact]:
        """Get the pending (unsaved) contact."""
        return self.pending_contact

    def clear_pending(self):
        """Clear the pending contact after saving."""
        self.pending_contact = None
        self.state = ConversationState.IDLE
        self.touch()

    def hard_reset(self, saved_contact_name: Optional[str] = None):
        """
        HARD RESET: Clear all active context after a save.
        This prevents data corruption when switching to a new contact.
        """
        # Lock the saved contact
        if saved_contact_name:
            saved_contact_name_lower = saved_contact_name.lower()
            if saved_contact_name_lower in self.recent_contacts:
                self.locked_contacts[saved_contact_name_lower] = self.recent_contacts[saved_contact_name_lower]
            self.last_saved_contact = saved_contact_name
        elif self.pending_contact and self.pending_contact.name:
            name_lower = self.pending_contact.name.lower()
            self.locked_contacts[name_lower] = self.pending_contact
            self.last_saved_contact = self.pending_contact.name
        elif self.current_contact and self.current_contact.name:
            name_lower = self.current_contact.name.lower()
            self.locked_contacts[name_lower] = self.current_contact
            self.last_saved_contact = self.current_contact.name

        # Clear ALL active context
        self.pending_contact = None
        self.current_contact = None
        self.state = ConversationState.IDLE
        self.touch()

    def is_contact_locked(self, name: str) -> bool:
        """Check if a contact is locked (was saved and cannot be modified without explicit unlock)."""
        if not name:
            return False
        return name.lower() in self.locked_contacts

    def unlock_contact(self, name: str) -> Optional[Contact]:
        """Explicitly unlock a contact for editing (user said 'Update [name]')."""
        if not name:
            return None
        name_lower = name.lower()
        if name_lower in self.locked_contacts:
            contact = self.locked_contacts[name_lower]
            # Set as current for editing
            self.current_contact = contact
            self.pending_contact = contact
            self.state = ConversationState.COLLECTING
            return contact
        # Try recent contacts
        if name_lower in self.recent_contacts:
            contact = self.recent_contacts[name_lower]
            self.current_contact = contact
            self.pending_contact = contact
            self.state = ConversationState.COLLECTING
            return contact
        return None

    def get_locked_contact_names(self) -> List[str]:
        """Get list of locked contact names."""
        return [c.name for c in self.locked_contacts.values() if c.name]

    def cancel_pending(self):
        """Cancel and discard the pending contact."""
        if self.pending_contact and self.pending_contact.name:
            # Remove from recent since it was never saved
            name_lower = self.pending_contact.name.lower()
            if name_lower in self.recent_contacts:
                del self.recent_contacts[name_lower]
        self.pending_contact = None
        self.current_contact = None
        self.state = ConversationState.IDLE
        self.touch()

    def is_collecting(self) -> bool:
        """Check if we're currently collecting info for a contact."""
        return self.state == ConversationState.COLLECTING and self.pending_contact is not None

    def is_continuation(self) -> bool:
        """Check if this message is likely a continuation of the previous flow."""
        if not self.last_message_time:
            return False
        elapsed = (datetime.now() - self.last_message_time).total_seconds()
        return elapsed < self.CONTINUATION_SECONDS

    def should_prompt_timeout(self) -> bool:
        """
        Check if the session has timed out and we should prompt the user.
        Returns True if:
        - We're in COLLECTING state
        - We have a pending contact
        - More than TIMEOUT_SECONDS have passed since last message
        """
        if self.state != ConversationState.COLLECTING:
            return False
        if not self.pending_contact:
            return False
        if not self.last_message_time:
            return False
        elapsed = (datetime.now() - self.last_message_time).total_seconds()
        return elapsed >= self.TIMEOUT_SECONDS

    def get_seconds_since_last_message(self) -> float:
        """Get seconds elapsed since last message."""
        if not self.last_message_time:
            return 0.0
        return (datetime.now() - self.last_message_time).total_seconds()

    def get_context_summary(self) -> str:
        """Get a summary of current context for debugging."""
        current = self.current_contact.name if self.current_contact else "None"
        pending = self.pending_contact.name if self.pending_contact else "None"
        recent = ", ".join(self.get_recent_names()[-5:])  # Last 5
        return f"State: {self.state.value} | Current: {current} | Pending: {pending} | Recent: {recent}"


class ContactMemoryService:
    """
    Manages contact memory across all users.
    Persists conversation context between messages.
    """
    
    def __init__(self):
        self._memories: Dict[str, UserMemory] = {}
    
    def get_memory(self, user_id: str) -> UserMemory:
        """Get or create memory for a user."""
        if user_id not in self._memories:
            self._memories[user_id] = UserMemory(user_id=user_id)

        memory = self._memories[user_id]

        # Check for expiry
        if memory.is_expired():
            self._memories[user_id] = UserMemory(user_id=user_id)
            memory = self._memories[user_id]

        # Periodic cleanup: every 50th call, remove expired sessions
        if len(self._memories) > 10:
            self.cleanup_expired()

        return memory
    
    def get_current_contact(self, user_id: str) -> Optional[Contact]:
        """Get the current contact for a user."""
        return self.get_memory(user_id).current_contact
    
    def set_current_contact(self, user_id: str, contact: Contact):
        """Set the current contact for a user."""
        self.get_memory(user_id).set_current_contact(contact)
    
    def get_recent_contacts(self, user_id: str) -> List[str]:
        """Get list of recent contact names for a user."""
        return self.get_memory(user_id).get_recent_names()
    
    def find_contact(self, user_id: str, name: str) -> Optional[Contact]:
        """Find a contact by name from a user's memory."""
        return self.get_memory(user_id).find_contact_by_name(name)
    
    def clear_current(self, user_id: str):
        """Clear the current contact for a user."""
        self.get_memory(user_id).clear_current()
    
    def update_contact(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update the current contact with new data."""
        memory = self.get_memory(user_id)
        contact = memory.current_contact
        
        if not contact:
            return False
        
        # Apply updates to the contact object
        for key, value in updates.items():
            if value and hasattr(contact, key):
                setattr(contact, key, value)
        
        # Also update in recent contacts
        if contact.name:
            name_lower = contact.name.lower()
            if name_lower in memory.recent_contacts:
                memory.recent_contacts[name_lower] = contact
        
        memory.touch()
        return True
    
    def update_contact_by_name(self, user_id: str, name: str, updates: Dict[str, Any]) -> bool:
        """Update a specific contact by name."""
        memory = self.get_memory(user_id)
        contact = memory.find_contact_by_name(name)
        
        if not contact:
            return False
        
        # Apply updates
        for key, value in updates.items():
            if value and hasattr(contact, key):
                setattr(contact, key, value)
        
        # Update in recent contacts
        if contact.name:
            name_lower = contact.name.lower()
            memory.recent_contacts[name_lower] = contact
        
        memory.touch()
        return True
    
    def add_contact_to_memory(self, user_id: str, contact: Contact):
        """Add a new contact to memory (and set as current)."""
        self.get_memory(user_id).set_current_contact(contact)

    def start_collecting(self, user_id: str, contact: Contact):
        """Start collecting info for a new pending contact."""
        self.get_memory(user_id).start_collecting(contact)

    def get_pending_contact(self, user_id: str) -> Optional[Contact]:
        """Get the pending contact for a user."""
        return self.get_memory(user_id).get_pending_contact()

    def update_pending(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update the pending contact with new data."""
        return self.get_memory(user_id).update_pending(updates)

    def clear_pending(self, user_id: str):
        """Clear the pending contact after saving."""
        self.get_memory(user_id).clear_pending()

    def cancel_pending(self, user_id: str):
        """Cancel and discard the pending contact."""
        self.get_memory(user_id).cancel_pending()

    def hard_reset(self, user_id: str, saved_contact_name: Optional[str] = None):
        """
        HARD RESET after save - clears context and locks the saved contact.
        CRITICAL: Prevents data corruption when switching to a new contact.
        """
        self.get_memory(user_id).hard_reset(saved_contact_name)

    def is_contact_locked(self, user_id: str, name: str) -> bool:
        """Check if a contact is locked (saved and cannot be modified without explicit unlock)."""
        return self.get_memory(user_id).is_contact_locked(name)

    def unlock_contact(self, user_id: str, name: str) -> Optional[Contact]:
        """Explicitly unlock a contact for editing."""
        return self.get_memory(user_id).unlock_contact(name)

    def set_last_saved_contact(self, user_id: str, name: Optional[str], company: Optional[str] = None):
        """Store the last saved contact name for potential enrichment."""
        memory = self.get_memory(user_id)
        memory.last_saved_contact = name
        memory.last_saved_company = company

    def get_last_saved_contact(self, user_id: str) -> tuple:
        """Get the last saved contact name and company."""
        memory = self.get_memory(user_id)
        name = memory.last_saved_contact
        company = memory.last_saved_company
        return (name, company)

    def get_locked_contacts(self, user_id: str) -> List[str]:
        """Get list of locked contact names for a user."""
        return self.get_memory(user_id).get_locked_contact_names()

    def get_state(self, user_id: str) -> ConversationState:
        """Get the current conversation state for a user."""
        return self.get_memory(user_id).state

    def set_state(self, user_id: str, state: ConversationState):
        """Set the conversation state for a user."""
        self.get_memory(user_id).state = state

    def is_collecting(self, user_id: str) -> bool:
        """Check if user is currently collecting info for a contact."""
        return self.get_memory(user_id).is_collecting()

    def is_continuation(self, user_id: str) -> bool:
        """Check if this message is likely a continuation of the previous flow."""
        return self.get_memory(user_id).is_continuation()

    def should_prompt_timeout(self, user_id: str) -> bool:
        """Check if the session has timed out and we should prompt the user."""
        return self.get_memory(user_id).should_prompt_timeout()

    def get_seconds_since_last_message(self, user_id: str) -> float:
        """Get seconds elapsed since last message for this user."""
        return self.get_memory(user_id).get_seconds_since_last_message()

    def get_context_for_ai(self, user_id: str) -> tuple[Optional[Contact], List[str], ConversationState]:
        """Get context for AI analysis including state."""
        memory = self.get_memory(user_id)
        # Use pending contact if collecting, otherwise current
        contact = memory.pending_contact or memory.current_contact
        return contact, memory.get_recent_names(), memory.state

    def cleanup_expired(self):
        """Remove expired memories (call periodically)."""
        expired = [uid for uid, mem in self._memories.items() if mem.is_expired()]
        for uid in expired:
            del self._memories[uid]


# Global singleton instance
_memory_service: Optional[ContactMemoryService] = None


def get_memory_service() -> ContactMemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = ContactMemoryService()
    return _memory_service
