"""
Agent Tools for the Rover Network Agent.
These tools are called by the AI agent to perform actions.

Architecture (Session-Based):
- Each user has a UserSession with a ContactDraft "shopping cart"
- Research tools UPDATE the draft directly (not just display text)
- Save tool reads FROM the draft (doesn't guess from LLM)
- This fixes: Amnesia, Nagging, Hallucination
"""

import json
import logging
import os
import re
import time
from typing import Optional, Dict, Any, List

from services.contact_memory import get_memory_service, ConversationState
from services.user_session import get_user_session, ContactDraft, DraftStatus
from services.airtable_service import get_sheets_service
from services.enrichment import get_enrichment_service
from services.ai_service import get_ai_service
from config import AIConfig
from data.schema import Contact


logger = logging.getLogger('network_agent')


# Global storage for search results per user (for summarization)
# TTL-based cleanup prevents unbounded memory growth
_user_search_results: Dict[str, List[Dict]] = {}
_user_summaries: Dict[str, str] = {}
_user_last_contact: Dict[str, str] = {}  # Track last mentioned/viewed contact name
_user_last_action: Dict[str, str] = {}  # Track last action for "Yes" context
_user_search_query: Dict[str, str] = {}  # Track what was searched
_user_last_mentioned_person: Dict[str, str] = {}  # Track last PERSON mentioned (for "Add him/her")
_user_timestamps: Dict[str, float] = {}  # Track last activity per user for TTL cleanup
_USER_DATA_TTL = 3600  # 1 hour TTL for per-user data


def _touch_user(user_id: str):
    """Update user's last activity timestamp."""
    _user_timestamps[user_id] = time.time()


def _cleanup_stale_user_data():
    """Remove per-user data older than TTL."""
    now = time.time()
    stale = [uid for uid, ts in _user_timestamps.items()
             if now - ts > _USER_DATA_TTL]
    for uid in stale:
        _user_search_results.pop(uid, None)
        _user_summaries.pop(uid, None)
        _user_last_contact.pop(uid, None)
        _user_last_action.pop(uid, None)
        _user_search_query.pop(uid, None)
        _user_last_mentioned_person.pop(uid, None)
        _user_timestamps.pop(uid, None)


def _normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', name.strip().lower())


def extract_linkedin_url(text: str) -> Optional[str]:
    """Extract LinkedIn URL from text."""
    pattern = r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_email(text: str) -> Optional[str]:
    """Extract valid email from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    if match:
        email = match.group(0)
        # Validate it's not garbage
        if len(email) > 5 and '.' in email.split('@')[1]:
            return email
    return None


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    # Look for phone patterns
    patterns = [
        r'\+?[\d\s\-\(\)]{10,}',
        r'\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(0).strip()
            # Must have at least 7 digits
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 7:
                return phone
    return None


def save_contact_to_storage(contact: Contact) -> tuple[bool, str, str]:
    """Save a contact to storage. Returns (success, storage_type, error_message)."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        if sheets.add_contact(contact):
            logger.info(f"[STORAGE] Contact '{contact.name}' saved to Airtable")
            return True, "airtable", ""
        else:
            logger.warning(f"[STORAGE] add_contact returned False for '{contact.name}' - checking for duplicates")
            # Check if contact actually exists (might be a name collision)
            existing = sheets.get_contact_by_name(contact.name)
            if existing:
                return False, "", f"Contact '{contact.name}' already exists. Use 'update' to modify it."
            # Check if email exists on another contact
            if contact.email:
                email_match = sheets.find_contact_by_email(contact.email)
                if email_match:
                    return False, "", f"Email {contact.email} is already used by '{email_match.name}'."
            return False, "", f"Could not save '{contact.name}'. Please try again."
    except Exception as e:
        logger.error(f"Airtable error: {e}")

    # Fallback to local storage
    try:
        from services.local_storage import get_local_storage
        local = get_local_storage()
        if local.add_contact(contact):
            logger.info(f"[STORAGE] Contact '{contact.name}' saved to local storage (fallback)")
            return True, "local", ""
    except Exception as e:
        logger.error(f"Local storage error: {e}")

    return False, "", "Failed to save contact to any storage."


def update_contact_in_storage(name: str, updates: Dict[str, Any]) -> bool:
    """Update a contact in storage."""
    if not updates:
        return False

    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        if sheets.update_contact(name, updates):
            return True
    except Exception as e:
        logger.error(f"Google Sheets update error: {e}")

    return False


def find_contact_in_storage(name: str) -> Optional[Contact]:
    """Find a contact by name from storage."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        contact = sheets.get_contact_by_name(name)
        if contact:
            return contact
    except Exception as e:
        logger.error(f"Google Sheets find error: {e}")

    return None


def fuzzy_find_contact(name: str) -> Optional[Contact]:
    """Try to find a contact with fuzzy matching."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()

        # Search for partial matches
        contacts = sheets.search_contacts(name)
        if contacts:
            # Return first match
            return contacts[0]

        # Try first name only
        first_name = name.split()[0] if name else ""
        if first_name:
            contacts = sheets.search_contacts(first_name)
            if contacts:
                return contacts[0]

    except Exception as e:
        logger.error(f"Fuzzy find error: {e}")

    return None


def get_similar_contacts(name: str) -> List[str]:
    """Get names of contacts that might match."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()

        # Search for partial matches
        contacts = sheets.search_contacts(name)
        if contacts:
            return [c.name for c in contacts[:3]]

        # Try first name
        first_name = name.split()[0] if name else ""
        if first_name and len(first_name) > 2:
            contacts = sheets.search_contacts(first_name)
            if contacts:
                return [c.name for c in contacts[:3]]

    except Exception as e:
        logger.error(f"Similar contacts error: {e}")

    return []


def format_contact_card(contact: Contact) -> str:
    """Format a contact as a nice card for display."""
    lines = [f"**{contact.name}**", ""]

    if contact.title:
        line = f"Title: {contact.title}"
        if contact.company:
            line += f" at {contact.company}"
        lines.append(line)
    elif contact.company:
        lines.append(f"Company: {contact.company}")

    if contact.contact_type:
        lines.append(f"Type: {contact.contact_type}")
    if contact.industry:
        lines.append(f"Industry: {contact.industry}")
    if contact.address:
        lines.append(f"Location: {contact.address}")
    if contact.email:
        lines.append(f"Email: {contact.email}")
    if contact.phone:
        lines.append(f"Phone: {contact.phone}")
    if contact.linkedin_url or contact.linkedin_link:
        lines.append(f"LinkedIn: {contact.linkedin_url or contact.linkedin_link}")
    if contact.company_description:
        desc = contact.company_description[:100] + "..." if len(contact.company_description) > 100 else contact.company_description
        lines.append(f"Company Info: {desc}")

    return "\n".join(lines)


class AgentTools:
    """
    Tool implementations for the Rover Agent.
    Each method is a tool that can be called by the agent.

    Uses Session-Based Architecture:
    - ContactDraft acts as a "shopping cart" for contact data
    - Research tools update the draft directly
    - Save reads from draft, NOT from LLM arguments
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = get_memory_service()
        self.session = get_user_session(user_id)
        _touch_user(user_id)
        _cleanup_stale_user_data()

    async def add_contact(self, name: str, title: str = None, company: str = None,
                         email: str = None, phone: str = None, linkedin: str = None,
                         contact_type: str = None, company_description: str = None,
                         location: str = None, notes: str = None) -> str:
        """Add a new contact and start editing it."""
        logger.info(f"[TOOL] add_contact called: name={name}")

        # Check if already editing someone in session
        if self.session.has_draft():
            existing_name = self.session.draft.name
            return f"Already editing {existing_name}. Say 'save' to save first, or 'cancel' to discard."

        # Early duplicate detection
        existing = find_contact_in_storage(name)
        if existing:
            return f"'{existing.name}' already exists. Say 'update {existing.name}' to modify."

        if email:
            sheets = get_sheets_service()
            email_match = sheets.find_contact_by_email(email)
            if email_match:
                return f"Email {email} already belongs to '{email_match.name}'."

        # Create new draft in session
        draft = self.session.start_new_contact(name)

        # Apply any provided fields
        if title:
            draft.update_field('title', title)
        if company:
            draft.update_field('company', company)
        if email:
            draft.update_field('email', email)
        if phone:
            draft.update_field('phone', phone)
        if linkedin:
            draft.update_field('linkedin_url', linkedin)
        if contact_type:
            draft.update_field('contact_type', contact_type)
        if location:
            draft.update_field('location', location)
        if notes:
            draft.append_notes(notes)
        if company_description:
            draft.update_field('company_description', company_description)

        # Split name
        name_parts = name.split()
        draft.first_name = name_parts[0] if name_parts else ''
        draft.last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        # Also update old memory system for compatibility
        contact = Contact(
            full_name=name,
            first_name=draft.first_name,
            last_name=draft.last_name,
            title=title,
            company=company,
            email=email,
            phone=phone,
            linkedin_url=linkedin,
            contact_type=contact_type,
            company_description=company_description,
            address=location,
            notes=notes,
            user_id=self.user_id
        )
        self.memory.start_collecting(self.user_id, contact)

        # Track context
        _user_last_contact[self.user_id] = name
        _user_last_action[self.user_id] = f"started adding contact '{name}'"

        # Build response
        details = []
        if title:
            details.append(f"Title: {title}")
        if company:
            details.append(f"Company: {company}")
        if contact_type:
            details.append(f"Type: {contact_type}")

        detail_str = f" ({', '.join(details)})" if details else ""
        response = f"Started new contact: {name}{detail_str}. Add more info or say 'done' to save."

        missing = draft.get_missing_fields()
        if missing:
            response += f"\n\nStill missing: {', '.join(missing)}"

        return response

    async def update_contact(self, title: str = None, company: str = None,
                            email: str = None, phone: str = None, linkedin: str = None,
                            contact_type: str = None, company_description: str = None,
                            location: str = None, notes: str = None) -> str:
        """Update fields on the current contact being edited."""
        # Check session draft first
        draft = self.session.draft if self.session.has_draft() else None
        pending = self.memory.get_pending_contact(self.user_id)

        if not draft and not pending:
            return "No contact being edited. Start with 'Add [name]' first."

        target_name = draft.name if draft else pending.name

        # Build updates dict
        updates = {}
        if title:
            updates['title'] = title
        if company:
            updates['company'] = company
        if email:
            updates['email'] = email
        if phone:
            updates['phone'] = phone
        if linkedin:
            updates['linkedin_url'] = linkedin
        if contact_type:
            updates['contact_type'] = contact_type
        if company_description:
            updates['company_description'] = company_description
        if location:
            updates['address'] = location
            updates['location'] = location  # For draft
        if notes:
            updates['notes'] = notes

        if not updates:
            return f"No updates provided for {target_name}."

        # Update session draft
        if draft:
            for field, value in updates.items():
                if field == 'notes':
                    draft.append_notes(value)
                elif field == 'linkedin_url':
                    draft.update_field('linkedin_url', value)
                elif field == 'address':
                    draft.update_field('location', value)
                elif hasattr(draft, field):
                    draft.update_field(field, value)

        # Also update old memory system
        if pending:
            self.memory.update_pending(self.user_id, updates)

        # Format response
        update_parts = [f"{k}='{v}'" for k, v in updates.items()]
        logger.info(f"[TOOL] update_contact: {target_name} -> {update_parts}")

        return f"Updated {target_name}: {', '.join(update_parts)}"

    async def save_contact(self) -> str:
        """
        Save the current contact to the database.

        CRITICAL: This reads from the SESSION DRAFT, not from LLM arguments.
        This prevents the "hallucination" bug where garbage data gets saved.
        """
        # First, check the session draft (new architecture)
        if not self.session.has_draft():
            # Fallback to old memory system for compatibility
            pending = self.memory.get_pending_contact(self.user_id)
            if not pending:
                return "No contact to save. Add a contact first."
        else:
            # Use session draft as the source of truth
            draft = self.session.draft
            logger.info(f"[TOOL] save_contact: Saving from session draft: {draft.name}")

            # Convert draft to Contact object
            pending = Contact(
                full_name=draft.name,
                first_name=draft.first_name or (draft.name.split()[0] if draft.name else ''),
                last_name=draft.last_name or (' '.join(draft.name.split()[1:]) if draft.name and ' ' in draft.name else ''),
                title=draft.title,
                company=draft.company,
                email=draft.email,  # Already validated in draft
                phone=draft.phone,
                linkedin_url=draft.linkedin_url,
                contact_type=draft.contact_type,
                industry=draft.industry,
                company_description=draft.company_description,
                address=draft.location,
                notes=draft.notes + ("\n\n" + draft.research_summary if draft.research_summary else ""),
                user_id=self.user_id
            )

            # Also sync to old memory system
            self.memory.start_collecting(self.user_id, pending)

        # Check if contact already exists
        existing = find_contact_in_storage(pending.name)

        error_msg = ""
        if existing:
            # Update existing contact
            updates = {}
            for field in ['title', 'company', 'email', 'phone', 'address', 'industry',
                         'linkedin_url', 'notes', 'contact_type', 'company_description']:
                value = getattr(pending, field, None)
                if value:
                    updates[field] = value

            if updates:
                success = update_contact_in_storage(pending.name, updates)
            else:
                success = True
        else:
            # Save new contact
            success, storage_type, error_msg = save_contact_to_storage(pending)
            if success:
                logger.info(f"[TOOL] save_contact: Saved to {storage_type}")

        if success:
            saved_contact = pending
            saved_name = saved_contact.name

            # CRITICAL: Clear BOTH session and old memory
            self.session.mark_saved()  # Clear session draft
            self.memory.hard_reset(self.user_id, saved_name)  # Clear old memory

            # Track last contact for reference
            _user_last_contact[self.user_id] = saved_name
            _user_last_action[self.user_id] = f"saved contact '{saved_name}'"

            logger.info(f"[TOOL] save_contact: Saved {saved_name}. Session cleared.")
            
            # Trigger auto-enrichment in background (if enabled)
            import os
            if os.getenv("AUTO_ENRICH_ENABLED", "true").lower() == "true":
                try:
                    import asyncio
                    from services.auto_enrichment import auto_enrich_contact
                    linkedin = getattr(saved_contact, 'linkedin_url', None)
                    asyncio.create_task(auto_enrich_contact(saved_name, saved_contact.company, linkedin_url=linkedin))
                    logger.info(f"[TOOL] Auto-enrichment triggered for {saved_name}" + (" (with LinkedIn)" if linkedin else ""))
                except Exception as e:
                    logger.warning(f"[TOOL] Auto-enrichment trigger failed: {e}")
            
            return f"Saved {saved_name} to your network! ✅ Enriching in background...\n\n{format_contact_card(saved_contact)}"

        # Return actual error message if available
        if error_msg:
            return f"⚠️ {error_msg}"
        return f"Failed to save {pending.name}. Please try again."

    async def search_web(self, query: str) -> str:
        """Search the web for information about a company or person."""
        logger.info(f"[TOOL] search_web: query='{query}'")

        enrichment = get_enrichment_service()

        # Check if search is available
        if not enrichment.is_available():
            error = enrichment.get_last_error()
            if error and "Invalid API key" in error:
                return "Search unavailable - API key needs to be configured."
            return "Search service is currently unavailable."

        try:
            results = enrichment.search_company(query)
            search_results = results.get('search_results', [])[:5]

            if not search_results:
                return f"No results found for '{query}'."

            # Store for later summarization and context
            _user_search_results[self.user_id] = search_results
            _user_search_query[self.user_id] = query
            _user_last_action[self.user_id] = f"searched for '{query}'"

            # If query looks like a person's name (has space, not a common company pattern), track it
            if ' ' in query and not any(corp in query.lower() for corp in ['inc', 'llc', 'corp', 'ltd', 'analytics', 'ventures', 'capital']):
                _user_last_mentioned_person[self.user_id] = query
                logger.info(f"[TOOL] Tracking last mentioned person: {query}")

            # Format results with links
            formatted = []
            for i, r in enumerate(search_results, 1):
                title = r.get('title', 'No title')
                snippet = r.get('snippet', '')
                link = r.get('link', '')
                if link:
                    formatted.append(f"{i}. {title}\n   {snippet}\n   Link: {link}")
                else:
                    formatted.append(f"{i}. {title}\n   {snippet}")

            return f"Search results for '{query}':\n\n" + "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Error searching for '{query}': {str(e)}"

    async def list_contacts(self, limit: int = 10) -> str:
        """List all contacts in the database."""
        logger.info(f"[TOOL] list_contacts: limit={limit}")

        try:
            sheets = get_sheets_service()
            sheets._ensure_initialized()

            # Get all contacts
            contacts = sheets.get_all_contacts()

            if not contacts:
                return "No contacts found in your network yet."

            # Limit results
            contacts = contacts[:limit]

            # Format list
            lines = [f"**Your contacts ({len(contacts)} shown):**\n"]
            for c in contacts:
                line = f"• **{c.name}**"
                if c.title:
                    line += f" - {c.title}"
                if c.company:
                    line += f" at {c.company}"
                if c.contact_type:
                    line += f" [{c.contact_type}]"
                lines.append(line)

            _user_last_action[self.user_id] = "listed contacts"
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"List contacts error: {e}")
            return f"Error listing contacts: {str(e)}"

    async def get_search_links(self) -> str:
        """Get the links from the last search results."""
        search_results = _user_search_results.get(self.user_id, [])
        query = _user_search_query.get(self.user_id, "")

        if not search_results:
            return "No recent search results. Search for something first."

        lines = [f"Links from search '{query}':\n"]
        for i, r in enumerate(search_results, 1):
            title = r.get('title', 'No title')
            link = r.get('link', 'No link')
            lines.append(f"{i}. {title}\n   {link}")

        return "\n".join(lines)

    async def summarize_search_results(self) -> str:
        """Create a summary of the most recent search results."""
        search_results = _user_search_results.get(self.user_id, [])

        if not search_results:
            return "No search results to summarize. Search for something first."

        try:
            ai = get_ai_service()

            # Build text from search results
            text = "\n".join([
                f"- {r.get('title', '')}: {r.get('snippet', '')}"
                for r in search_results
            ])

            prompt = f"""Summarize the following search results in 2-3 concise sentences:

{text}

Provide a brief, informative summary suitable for a contact profile."""

            summary = ai.generate_response(prompt)

            # Store summary for later use
            _user_summaries[self.user_id] = summary

            logger.info(f"[TOOL] summarize_search_results: Generated summary")
            return f"Summary: {summary}"

        except Exception as e:
            logger.error(f"Summarize error: {e}")
            return f"Error creating summary: {str(e)}"

    async def get_contact(self, name: str) -> str:
        """Get details about a contact by name."""
        logger.info(f"[TOOL] get_contact: name='{name}'")

        # Try memory first
        contact = self.memory.find_contact(self.user_id, name)

        # Then try storage
        if not contact:
            contact = find_contact_in_storage(name)

        # Try fuzzy match if exact match failed
        if not contact:
            contact = fuzzy_find_contact(name)

        if contact:
            # Track this as the last viewed contact
            _user_last_contact[self.user_id] = contact.name
            _user_last_action[self.user_id] = f"viewed contact '{contact.name}'"
            return format_contact_card(contact)

        # Suggest similar contacts
        suggestions = get_similar_contacts(name)
        if suggestions:
            return f"Contact '{name}' not found. Did you mean: {', '.join(suggestions)}?"

        return f"Contact '{name}' not found in your network. Would you like to add them?"

    async def cancel_current(self) -> str:
        """Cancel the current contact without saving."""
        # Check both session and old memory
        draft = self.session.draft if self.session.has_draft() else None
        pending = self.memory.get_pending_contact(self.user_id)

        if not draft and not pending:
            return "Nothing to cancel."

        name = draft.name if draft else pending.name

        # Clear both session and old memory
        self.session.clear()
        self.memory.cancel_pending(self.user_id)

        logger.info(f"[TOOL] cancel_current: Cancelled {name}")
        return f"Cancelled {name}. Ready for a new contact."

    async def get_last_summary(self) -> str:
        """Get the last generated summary (for adding to descriptions)."""
        summary = _user_summaries.get(self.user_id, "")
        if summary:
            return summary
        return "No summary available. Summarize search results first."

    async def update_existing_contact(self, name: str, title: str = None, company: str = None,
                                      email: str = None, phone: str = None, linkedin: str = None,
                                      contact_type: str = None, company_description: str = None,
                                      location: str = None, notes: str = None) -> str:
        """Update an existing contact in the database by name."""
        logger.info(f"[TOOL] update_existing_contact: name='{name}'")

        # Find the contact in storage
        contact = find_contact_in_storage(name)
        if not contact:
            return f"Contact '{name}' not found in your network. Try 'Add {name}' to create them first."

        # Build updates dict
        updates = {}
        if title:
            updates['title'] = title
        if company:
            updates['company'] = company
        if email:
            updates['email'] = email
        if phone:
            updates['phone'] = phone
        if linkedin:
            updates['linkedin_url'] = linkedin
        if contact_type:
            updates['contact_type'] = contact_type
        if company_description:
            updates['company_description'] = company_description
        if location:
            updates['address'] = location
        if notes:
            updates['notes'] = notes

        if not updates:
            return f"No updates provided for {name}."

        # Update in storage
        success = update_contact_in_storage(name, updates)

        if success:
            update_parts = [f"{k}='{v}'" for k, v in updates.items()]
            logger.info(f"[TOOL] update_existing_contact: Updated {name} -> {update_parts}")
            return f"Updated {name}: {', '.join(update_parts)}"

        return f"Failed to update {name}. Please try again."

    async def enrich_contact(self, name: str = None) -> str:
        """
        Enrich a contact with DEEP research data using the new research engine.

        This performs comprehensive multi-source research:
        1. LinkedIn profile search
        2. Company intelligence
        3. Person background research
        4. Cross-validation of data

        CRITICAL: Stores research data in the SESSION DRAFT for persistence.
        """
        # Import the new research engine
        from services.research_engine import get_research_engine
        from data.research_schema import ResearchRequest, ConfidenceLevel
        
        # Determine which contact to enrich
        draft = self.session.draft if self.session.has_draft() else None
        pending = self.memory.get_pending_contact(self.user_id)

        if name:
            target_name = name
            target_company = None
            known_title = None
            known_location = None
            if draft and name.lower() in draft.name.lower():
                target_company = draft.company
                known_title = draft.title
                known_location = draft.location
            elif pending and name.lower() in pending.name.lower():
                target_company = pending.company
                known_title = pending.title
                known_location = pending.address
        elif draft:
            target_name = draft.name
            target_company = draft.company
            known_title = draft.title
            known_location = draft.location
        elif pending:
            target_name = pending.name
            target_company = pending.company
            known_title = pending.title
            known_location = pending.address
        else:
            last = _user_last_contact.get(self.user_id)
            if last:
                target_name = last
                target_company = None
                known_title = None
                known_location = None
            else:
                return "Who should I enrich? Add a contact first or specify a name."

        logger.info(f"[TOOL] enrich_contact: Deep research for '{target_name}' (company: {target_company})")

        # Use the new deep research engine
        engine = get_research_engine()
        
        request = ResearchRequest(
            name=target_name,
            company=target_company,
            known_title=known_title,
            known_location=known_location,
            depth="standard"
        )
        
        result = engine.research(request)
        
        # Track context
        _user_last_action[self.user_id] = f"enriched '{target_name}'"
        _user_last_contact[self.user_id] = target_name

        # Get structured field mappings
        field_mappings = result.get_contact_field_mapping()
        
        # CRITICAL: Store research data in SESSION DRAFT
        if draft and target_name.lower() in draft.name.lower():
            fields_updated = []
            
            # Apply field mappings to draft
            for field, value in field_mappings.items():
                if not value:
                    continue
                    
                # Map to draft field names
                draft_field = field
                if field == 'address':
                    draft_field = 'location'
                    
                # Only update if field is empty in draft
                current_val = getattr(draft, draft_field, None) if hasattr(draft, draft_field) else None
                if not current_val:
                    if draft_field in ['linkedin_url', 'title', 'company', 'email', 'phone', 
                                       'location', 'industry', 'contact_type']:
                        draft.update_field(draft_field, value)
                        fields_updated.append(draft_field)
            
            # Store research summary
            if result.person and result.person.professional_summary:
                draft.set_research_summary(result.person.professional_summary)
            
            # Add research notes
            notes = []
            if result.linkedin_profile and result.linkedin_profile.profile_url:
                notes.append(f"LinkedIn verified: {result.linkedin_profile.profile_url}")
            if result.company and result.company.industry:
                notes.append(f"Industry: {result.company.industry}")
            if result.company and result.company.funding_stage:
                notes.append(f"Company stage: {result.company.funding_stage}")
            if result.research_notes:
                notes.extend(result.research_notes)
            
            if notes:
                draft.append_notes("Deep Research Findings:\n" + "\n".join(notes))
            
            logger.info(f"[TOOL] enrich_contact: Stored {len(fields_updated)} fields in session draft: {fields_updated}")

        # Also update old memory system for compatibility
        if pending and target_name.lower() in pending.name.lower():
            updates = {}
            if field_mappings.get("linkedin_url"):
                updates["linkedin_url"] = field_mappings["linkedin_url"]
            if field_mappings.get("title") and not pending.title:
                updates["title"] = field_mappings["title"]
            if field_mappings.get("company") and not pending.company:
                updates["company"] = field_mappings["company"]
            if field_mappings.get("industry"):
                updates["industry"] = field_mappings["industry"]
            if field_mappings.get("contact_type") and not pending.contact_type:
                updates["contact_type"] = field_mappings["contact_type"]
            if field_mappings.get("address") and not pending.address:
                updates["address"] = field_mappings["address"]

            if updates:
                self.memory.update_pending(self.user_id, updates)

        # Build comprehensive response
        response = f"**🔍 Deep Research Complete for {target_name}**\n\n"
        
        # Quality indicators
        response += f"**Research Quality:** {result.overall_confidence.value.upper()}\n"
        response += f"**Completeness:** {result.completeness_score:.0%}\n"
        response += f"**Sources Consulted:** {result.sources_consulted}\n\n"
        
        # Person findings
        if result.person:
            response += "**👤 Person Information:**\n"
            if result.person.current_title:
                response += f"- Title: {result.person.current_title}\n"
            if result.person.current_company:
                response += f"- Company: {result.person.current_company}\n"
            if result.person.location:
                response += f"- Location: {result.person.location}\n"
            if result.person.contact_type:
                response += f"- Type: {result.person.contact_type}\n"
            if result.person.seniority:
                response += f"- Seniority: {result.person.seniority}\n"
        
        # LinkedIn
        if result.linkedin_profile and result.linkedin_profile.profile_url:
            response += f"\n**🔗 LinkedIn:** {result.linkedin_profile.profile_url}\n"
        elif result.person and result.person.linkedin_url:
            response += f"\n**🔗 LinkedIn:** {result.person.linkedin_url}\n"
        
        # Company findings
        if result.company:
            response += f"\n**🏢 Company: {result.company.name}**\n"
            if result.company.industry:
                response += f"- Industry: {result.company.industry}\n"
            if result.company.funding_stage:
                response += f"- Stage: {result.company.funding_stage}\n"
            if result.company.total_funding:
                response += f"- Funding: {result.company.total_funding}\n"
            if result.company.website:
                response += f"- Website: {result.company.website}\n"
        
        # Summary
        if result.person and result.person.professional_summary:
            summary = result.person.professional_summary[:250] + "..." if len(result.person.professional_summary) > 250 else result.person.professional_summary
            response += f"\n**📝 Summary:**\n_{summary}_\n"
        
        # Warnings
        if result.warnings:
            response += f"\n**⚠️ Notes:**\n"
            for w in result.warnings:
                response += f"- {w}\n"
        
        # Accuracy indicators
        if result.accuracy_indicators:
            response += f"\n**✅ Verified:**\n"
            for a in result.accuracy_indicators:
                response += f"- {a}\n"
        
        # Show current draft state
        if draft:
            response += f"\n\n**Current draft for {draft.name}:**\n{draft.get_display_card()}"

        return response

    async def deep_research(self, query: str) -> str:
        """
        Perform deep, comprehensive research using multi-source research engine.

        This tool:
        1. Runs comprehensive multi-source research
        2. Cross-validates data from different sources
        3. Uses AI to synthesize findings
        4. Stores structured data in session draft
        5. Returns detailed findings

        This is the most thorough research option available.
        """
        logger.info(f"[TOOL] deep_research: query='{query}'")

        # Import the new research engine
        from services.research_engine import get_research_engine
        from services.ai_research_synthesizer import get_synthesizer
        from data.research_schema import ResearchRequest
        
        draft = self.session.draft if self.session.has_draft() else None
        
        # Parse query to extract name and company
        # Query might be "John Smith" or "John Smith at Google" or "John Smith, CEO of Acme"
        name = query
        company = None
        
        # Try to extract company from query
        company_patterns = [
            r"(.+?)\s+at\s+(.+)$",
            r"(.+?)\s+from\s+(.+)$",
            r"(.+?),\s*(?:CEO|CTO|Founder|Director|VP|Manager)\s+(?:of|at)\s+(.+)$",
        ]
        
        import re
        for pattern in company_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                company = match.group(2).strip()
                break
        
        # If we have a draft, use its company as context
        if not company and draft:
            company = draft.company
        
        try:
            # Use the deep research engine
            engine = get_research_engine()
            
            request = ResearchRequest(
                name=name,
                company=company,
                depth="deep"  # Request deep research
            )
            
            result = engine.research(request)
            
            # Track context
            _user_search_query[self.user_id] = query
            _user_last_action[self.user_id] = f"deep researched '{name}'"
            
            # Store in raw results for later reference
            _user_search_results[self.user_id] = result.raw_search_results
            
            # Get field mappings
            field_mappings = result.get_contact_field_mapping()
            
            # CRITICAL: Store extracted data in session draft
            if draft:
                fields_updated = []
                
                for field, value in field_mappings.items():
                    if not value:
                        continue
                    
                    draft_field = field
                    if field == 'address':
                        draft_field = 'location'
                    
                    # Update draft field
                    if hasattr(draft, draft_field) or draft_field in ['linkedin_url', 'title', 'company', 
                                                                        'email', 'phone', 'location', 
                                                                        'industry', 'contact_type']:
                        current = getattr(draft, draft_field, None) if hasattr(draft, draft_field) else None
                        if not current:
                            draft.update_field(draft_field, value)
                            fields_updated.append(draft_field)
                
                # Store research summary
                if result.person and result.person.professional_summary:
                    draft.set_research_summary(result.person.professional_summary)
                
                # Add comprehensive research notes
                notes = [f"\n=== Deep Research on {name} ==="]
                
                if result.linkedin_profile and result.linkedin_profile.profile_url:
                    notes.append(f"LinkedIn: {result.linkedin_profile.profile_url}")
                
                if result.person:
                    if result.person.current_title:
                        notes.append(f"Title: {result.person.current_title}")
                    if result.person.contact_type:
                        notes.append(f"Type: {result.person.contact_type}")
                    if result.person.expertise_areas:
                        notes.append(f"Expertise: {', '.join(result.person.expertise_areas[:3])}")
                
                if result.company:
                    notes.append(f"\nCompany: {result.company.name}")
                    if result.company.industry:
                        notes.append(f"Industry: {result.company.industry}")
                    if result.company.funding_stage:
                        notes.append(f"Stage: {result.company.funding_stage}")
                
                if result.accuracy_indicators:
                    notes.append(f"\nVerified: {', '.join(result.accuracy_indicators)}")
                
                draft.append_notes("\n".join(notes))
                
                logger.info(f"[TOOL] deep_research: Stored {len(fields_updated)} fields in draft: {fields_updated}")

            # Build comprehensive response
            response = f"**🔬 Deep Research Complete: {name}**\n\n"
            
            # Research metadata
            response += f"**Quality:** {result.overall_confidence.value.upper()} "
            response += f"| **Completeness:** {result.completeness_score:.0%} "
            response += f"| **Duration:** {result.research_duration_seconds:.1f}s\n\n"
            
            # Person findings
            if result.person:
                response += "**👤 Person:**\n"
                if result.person.full_name:
                    response += f"- **Name:** {result.person.full_name}\n"
                if result.person.current_title:
                    response += f"- **Title:** {result.person.current_title}\n"
                if result.person.current_company:
                    response += f"- **Company:** {result.person.current_company}\n"
                if result.person.location:
                    response += f"- **Location:** {result.person.location}\n"
                if result.person.contact_type:
                    response += f"- **Type:** {result.person.contact_type}\n"
                if result.person.seniority:
                    response += f"- **Seniority:** {result.person.seniority}\n"
                if result.person.expertise_areas:
                    response += f"- **Expertise:** {', '.join(result.person.expertise_areas[:4])}\n"
                if result.person.email:
                    response += f"- **Email:** {result.person.email}\n"
                response += "\n"
            
            # LinkedIn
            if result.linkedin_profile and result.linkedin_profile.profile_url:
                response += f"**🔗 LinkedIn:** {result.linkedin_profile.profile_url}\n"
                if result.linkedin_profile.headline:
                    response += f"   _{result.linkedin_profile.headline}_\n"
                response += "\n"
            
            # Company
            if result.company:
                response += f"**🏢 Company: {result.company.name}**\n"
                if result.company.website:
                    response += f"- Website: {result.company.website}\n"
                if result.company.industry:
                    response += f"- Industry: {result.company.industry}\n"
                if result.company.company_size:
                    response += f"- Size: {result.company.company_size}\n"
                if result.company.funding_stage:
                    response += f"- Stage: {result.company.funding_stage}\n"
                if result.company.total_funding:
                    response += f"- Funding: {result.company.total_funding}\n"
                if result.company.headquarters:
                    response += f"- HQ: {result.company.headquarters}\n"
                if result.company.linkedin_url:
                    response += f"- LinkedIn: {result.company.linkedin_url}\n"
                if result.company.description:
                    desc = result.company.description[:200] + "..." if len(result.company.description) > 200 else result.company.description
                    response += f"\n_{desc}_\n"
                response += "\n"
            
            # Summary
            if result.person and result.person.professional_summary:
                summary = result.person.professional_summary[:300] + "..." if len(result.person.professional_summary) > 300 else result.person.professional_summary
                response += f"**📝 Background:**\n_{summary}_\n\n"
            
            # Data quality indicators
            if result.accuracy_indicators:
                response += "**✅ Verified:**\n"
                for indicator in result.accuracy_indicators:
                    response += f"- {indicator}\n"
                response += "\n"
            
            # Warnings
            if result.warnings:
                response += "**⚠️ Warnings:**\n"
                for w in result.warnings:
                    response += f"- {w}\n"
                response += "\n"
            
            # Field mappings for transparency
            if field_mappings:
                response += "**📋 Fields Found:**\n"
                for field, value in field_mappings.items():
                    if value:
                        response += f"- {field}: {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}\n"
                response += "\n"
            
            # Draft status
            if draft:
                response += f"_All data has been stored in draft for **{draft.name}**. Say 'save' when ready._"
            else:
                response += f"_Tip: Use 'add {name}' to create a contact and save this research._"

            return response

        except Exception as e:
            logger.error(f"Deep research error: {e}")
            import traceback
            traceback.print_exc()
            return f"Error during deep research: {str(e)}"

    async def get_draft_status(self) -> str:
        """Get the current status of the contact draft."""
        if not self.session.has_draft():
            return "No contact draft in progress."

        draft = self.session.draft
        return f"**Draft Status for {draft.name}:**\n\n{draft.get_display_card()}"
    
    async def log_interaction(self, name: str, interaction_type: str, context: str = None) -> str:
        """
        Log an interaction with a contact.
        
        Args:
            name: Contact name
            interaction_type: Type of interaction (met, called, emailed, introduced, messaged)
            context: Optional context about the interaction
        
        Returns:
            Confirmation message
        """
        from services.interaction_tracker import get_interaction_tracker
        
        logger.info(f"[TOOL] log_interaction: name={name}, type={interaction_type}")
        
        # Find the contact
        contact = find_contact_in_storage(name)
        if not contact:
            return f"Contact '{name}' not found. Add them first."
        
        # Log the interaction
        tracker = get_interaction_tracker()
        success = tracker.log_interaction(self.user_id, contact.name, interaction_type, context)
        
        if success:
            # Also update Airtable: last_interaction_date + increment interaction_count
            try:
                from datetime import datetime
                sheets = get_sheets_service()
                sheets._ensure_initialized()
                
                # Get current interaction count
                current_count = contact.interaction_count or 0
                sheets.update_contact(contact.name, {
                    "last_interaction_date": datetime.now().strftime("%Y-%m-%d"),
                    "interaction_count": current_count + 1,
                })
            except Exception as e:
                logger.warning(f"[TOOL] Could not update Airtable interaction fields: {e}")
            
            _user_last_action[self.user_id] = f"logged {interaction_type} with '{name}'"
            
            context_str = f" ({context})" if context else ""
            return f"✅ Logged {interaction_type} with **{name}**{context_str}"
        
        return f"Failed to log interaction with {name}."
    
    async def set_follow_up(self, name: str, date: str, reason: str = None) -> str:
        """
        Set a follow-up reminder for a contact.
        
        Args:
            name: Contact name
            date: Follow-up date (YYYY-MM-DD format)
            reason: Optional reason for follow-up
        
        Returns:
            Confirmation message
        """
        logger.info(f"[TOOL] set_follow_up: name={name}, date={date}, reason={reason}")
        
        # Find the contact
        contact = find_contact_in_storage(name)
        if not contact:
            return f"Contact '{name}' not found. Add them first."
        
        # Validate date format
        from datetime import datetime
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date format. Use YYYY-MM-DD (e.g., 2026-03-15)"
        
        # Store follow-up in both SQLite and Airtable
        from services.interaction_tracker import get_interaction_tracker
        tracker = get_interaction_tracker()
        
        contact_name = contact.name or name
        
        # SQLite (local backup)
        tracker.set_follow_up(self.user_id, contact_name, date, reason)
        
        # Airtable (primary)
        try:
            sheets = get_sheets_service()
            sheets._ensure_initialized()
            sheets.update_contact(contact_name, {
                "follow_up_date": date,
                "follow_up_reason": reason or ""
            })
        except Exception as e:
            logger.warning(f"[TOOL] Could not update Airtable follow-up: {e}")
        
        _user_last_action[self.user_id] = f"set follow-up for '{name}'"
        reason_str = f": {reason}" if reason else ""
        return f"⏰ Follow-up set for **{contact_name}** on {date}{reason_str}"
    
    async def get_follow_ups(self) -> str:
        """
        Get all pending follow-ups sorted by date.
        
        Returns:
            List of contacts with pending follow-ups
        """
        logger.info(f"[TOOL] get_follow_ups")
        
        from services.interaction_tracker import get_interaction_tracker
        from datetime import datetime
        
        tracker = get_interaction_tracker()
        follow_ups = tracker.get_pending_follow_ups(self.user_id)
        
        if not follow_ups:
            return "No pending follow-ups. You're all caught up! ✅"
        
        # Format response
        response = f"**📅 Pending Follow-ups ({len(follow_ups)}):**\n\n"
        
        today = datetime.now().date()
        for fu in follow_ups[:10]:  # Limit to 10
            try:
                follow_up_date = datetime.strptime(fu['follow_up_date'], "%Y-%m-%d").date()
                days_diff = (follow_up_date - today).days
                
                if days_diff < 0:
                    urgency = f"⚠️ {abs(days_diff)} days overdue"
                elif days_diff == 0:
                    urgency = "🔥 TODAY"
                elif days_diff == 1:
                    urgency = "📌 Tomorrow"
                elif days_diff <= 7:
                    urgency = f"📆 In {days_diff} days"
                else:
                    urgency = f"📆 {fu['follow_up_date']}"
                
                response += f"• **{fu['contact_name']}** - {urgency}\n"
                if fu.get('reason'):
                    response += f"  Reason: {fu['reason']}\n"
                response += "\n"
                
            except Exception as e:
                logger.error(f"Error formatting follow-up: {e}")
                continue
        
        _user_last_action[self.user_id] = "viewed follow-ups"
        
        return response.strip()
    
    async def get_relationship_health(self, name: str = None) -> str:
        """
        Calculate and return relationship score for a contact.
        
        Args:
            name: Contact name (optional - uses current contact if not specified)
        
        Returns:
            Relationship health report
        """
        from services.interaction_tracker import get_interaction_tracker
        
        # Determine which contact to analyze
        if not name:
            draft = self.session.draft if self.session.has_draft() else None
            pending = self.memory.get_pending_contact(self.user_id)
            
            if draft:
                name = draft.name
            elif pending:
                name = pending.name
            else:
                last = _user_last_contact.get(self.user_id)
                if last:
                    name = last
                else:
                    return "Which contact? Specify a name or add a contact first."
        
        logger.info(f"[TOOL] get_relationship_health: name={name}")
        
        # Find the contact
        contact = find_contact_in_storage(name)
        if not contact:
            return f"Contact '{name}' not found."
        
        # Calculate relationship score
        tracker = get_interaction_tracker()
        score = tracker.calculate_relationship_score(contact.name)
        
        # Determine relationship stage
        if score >= 80:
            stage = "💎 Strong"
            stage_emoji = "💪"
        elif score >= 60:
            stage = "🌱 Building"
            stage_emoji = "📈"
        elif score >= 40:
            stage = "⚡ Active"
            stage_emoji = "👍"
        elif score >= 20:
            stage = "⚠️ Cooling"
            stage_emoji = "❄️"
        else:
            stage = "💀 Dormant"
            stage_emoji = "⏰"
        
        # Build response
        response = f"**{stage_emoji} Relationship Health: {contact.name}**\n\n"
        response += f"**Score:** {score}/100 - {stage}\n\n"
        
        # Breakdown
        response += "**Breakdown:**\n"
        response += f"• Base score: 50\n"
        
        if contact.research_quality or contact.linkedin_summary or contact.company_description:
            response += f"• Enriched: +20\n"
        
        interaction_count = contact.interaction_count or 0
        if interaction_count > 0:
            bonus = min(interaction_count * 10, 40)
            response += f"• Interactions ({interaction_count}): +{bonus}\n"
        
        if contact.introduced_to:
            response += f"• Introduced to someone: +15\n"
        
        if contact.introduced_by:
            response += f"• Introduced by {contact.introduced_by}: +10\n"
        
        # Decay
        if contact.last_interaction_date:
            from datetime import datetime
            try:
                last_interaction = datetime.strptime(contact.last_interaction_date, "%Y-%m-%d %H:%M:%S")
                weeks_since = (datetime.now() - last_interaction).days / 7
                
                if weeks_since > 0:
                    decay = int(weeks_since * 5)
                    response += f"• Decay ({int(weeks_since)} weeks): -{decay}\n"
                
                if weeks_since > 12:
                    response += f"• Dormant penalty: -20\n"
            except:
                pass
        
        # Recommendations
        response += f"\n**💡 Recommendations:**\n"
        
        if score < 40:
            response += f"⚠️ This relationship needs attention!\n"
            response += f"• Schedule a follow-up soon\n"
            response += f"• Reach out with a genuine check-in\n"
        elif score < 60:
            response += f"Keep nurturing this relationship:\n"
            response += f"• Regular check-ins help maintain momentum\n"
        else:
            response += f"✅ This is a healthy relationship!\n"
            response += f"• Keep up the regular contact\n"
        
        _user_last_action[self.user_id] = f"viewed relationship health for '{name}'"
        _user_last_contact[self.user_id] = name
        
        return response

    # === PHASE 2 TOOLS ===

    async def create_introduction(self, connector: str, target: str, reason: str = None) -> str:
        """
        Create an introduction between two contacts.
        
        Args:
            connector: Person who can make/facilitate the intro
            target: Person to be introduced
            reason: Why this intro makes sense
        """
        logger.info(f"[TOOL] create_introduction: {connector} → {target}")
        
        from services.introduction_service import get_introduction_service
        intro_svc = get_introduction_service()
        
        # Draft an intro message
        message = intro_svc.draft_intro_message(connector, target, reason)
        
        # Create the record in Airtable
        record_id = intro_svc.create_introduction(
            connector_name=connector,
            target_name=target,
            reason=reason,
            status="suggested",
            intro_message=message
        )
        
        if record_id:
            # Also update the contacts' introduced_by/introduced_to fields
            try:
                sheets = get_sheets_service()
                sheets._ensure_initialized()
                sheets.update_contact(connector, {"introduced_to": target})
                sheets.update_contact(target, {"introduced_by": connector})
            except Exception as e:
                logger.warning(f"Could not update intro fields: {e}")
            
            response = f"🤝 **Introduction created!**\n\n"
            response += f"**{connector}** → **{target}**\n"
            if reason:
                response += f"Reason: {reason}\n"
            response += f"\n**Draft message:**\n_{message}_\n"
            response += f"\nStatus: suggested. Say 'confirm intro' to proceed."
            return response
        
        return f"Failed to create introduction between {connector} and {target}."

    async def get_introductions(self, status: str = None) -> str:
        """
        Get all introductions, optionally filtered by status.
        
        Args:
            status: Filter by status (suggested/requested/made/declined). Optional.
        """
        logger.info(f"[TOOL] get_introductions: status={status}")
        
        from services.introduction_service import get_introduction_service
        intro_svc = get_introduction_service()
        
        intros = intro_svc.get_introductions(status)
        
        if not intros:
            filter_str = f" with status '{status}'" if status else ""
            return f"No introductions found{filter_str}."
        
        response = f"**🤝 Introductions ({len(intros)}):**\n\n"
        for intro in intros:
            status_emoji = {"suggested": "💡", "requested": "📨", "made": "✅", "declined": "❌"}.get(intro['status'], "❓")
            response += f"{status_emoji} **{intro['connector']}** → **{intro['target']}**\n"
            if intro['reason']:
                response += f"   Reason: {intro['reason']}\n"
            response += f"   Status: {intro['status']} | Date: {intro.get('requested_date', 'N/A')}\n"
            if intro.get('intro_message'):
                response += f"   Draft: _{intro['intro_message'][:80]}..._\n"
            response += "\n"
        
        return response.strip()

    async def suggest_introductions(self) -> str:
        """Suggest potential introductions based on your network."""
        logger.info(f"[TOOL] suggest_introductions")
        
        from services.introduction_service import get_introduction_service
        intro_svc = get_introduction_service()
        
        suggestions = intro_svc.suggest_introductions()
        
        if not suggestions:
            return "No introduction suggestions right now. Add more contacts with industry/type info to get better suggestions!"
        
        response = f"**💡 Suggested Introductions ({len(suggestions)}):**\n\n"
        for i, s in enumerate(suggestions[:5], 1):
            response += f"{i}. **{s['connector']}** ↔ **{s['target']}**\n"
            response += f"   {s['reason']}\n\n"
        
        response += "Say 'introduce [person A] to [person B]' to make it happen!"
        return response

    async def get_daily_digest(self) -> str:
        """Get your daily network briefing with follow-ups, decaying relationships, and stats."""
        logger.info(f"[TOOL] get_daily_digest")
        
        from services.digest_service import generate_daily_digest
        return generate_daily_digest(self.user_id)

    async def get_weekly_report(self) -> str:
        """Get your weekly network activity report."""
        logger.info(f"[TOOL] get_weekly_report")
        
        from services.digest_service import generate_weekly_report
        return generate_weekly_report(self.user_id)

    async def search_contacts(self, query: str) -> str:
        """
        Search contacts with natural language queries.
        
        Args:
            query: Natural language search like "founders in fintech", "people at Google", "investors I met this month"
        """
        logger.info(f"[TOOL] search_contacts: query={query}")
        
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        all_contacts = sheets.get_all_contacts()
        
        if not all_contacts:
            return "No contacts in your network yet."
        
        # Use OpenAI to parse the query and filter
        import openai, os, json
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build a compact contact list for the LLM
        contact_summaries = []
        for c in all_contacts:
            parts = [c.name or "Unknown"]
            if c.title: parts.append(c.title)
            if c.company: parts.append(f"at {c.company}")
            if c.contact_type: parts.append(f"[{c.contact_type}]")
            if c.industry: parts.append(f"({c.industry})")
            if c.email: parts.append(f"<{c.email}>")
            contact_summaries.append(" | ".join(parts))
        
        contacts_text = "\n".join(contact_summaries)
        
        try:
            response = client.chat.completions.create(
                model=AIConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a contact search assistant. Given a list of contacts and a search query, return the names of matching contacts as a JSON array. Only return names that genuinely match the query. If none match, return an empty array."},
                    {"role": "user", "content": f"Contacts:\n{contacts_text}\n\nQuery: {query}\n\nReturn matching contact names as JSON array:"}
                ],
                temperature=0,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            # Parse JSON from response
            if "```" in result_text:
                result_text = result_text.split("```")[1].replace("json", "").strip()
            
            matching_names = json.loads(result_text)
            
            if not matching_names:
                return f"No contacts found matching '{query}'."
            
            # Build detailed results
            results = []
            for name in matching_names:
                contact = sheets.get_contact_by_name(name)
                if contact:
                    from services.interaction_tracker import get_interaction_tracker
                    tracker = get_interaction_tracker()
                    score = tracker.calculate_relationship_score(contact.name)
                    
                    info = f"**{contact.name}**"
                    if contact.title and contact.company:
                        info += f" — {contact.title} at {contact.company}"
                    elif contact.company:
                        info += f" — {contact.company}"
                    if contact.contact_type:
                        info += f" [{contact.contact_type}]"
                    info += f" (score: {score}/100)"
                    if contact.email:
                        info += f"\n  📧 {contact.email}"
                    if contact.phone:
                        info += f" | 📱 {contact.phone}"
                    results.append(info)
            
            response_text = f"**🔍 Found {len(results)} contacts matching '{query}':**\n\n"
            response_text += "\n\n".join(results)
            return response_text
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            # Fallback: simple text matching
            query_lower = query.lower()
            matches = [c for c in all_contacts if 
                      query_lower in (c.name or "").lower() or
                      query_lower in (c.company or "").lower() or
                      query_lower in (c.industry or "").lower() or
                      query_lower in (c.contact_type or "").lower()]
            
            if not matches:
                return f"No contacts found matching '{query}'."
            
            results = [f"• **{c.name}** — {c.company or 'N/A'} ({c.contact_type or 'N/A'})" for c in matches[:10]]
            return f"**Found {len(matches)} contacts:**\n" + "\n".join(results)

    # === PHASE 2.5 TOOLS ===

    async def draft_emails(self, contacts_query: str, purpose: str, date_range: str = None) -> str:
        """
        Draft personalized outreach emails and save them as PENDING drafts in Airtable.

        Args:
            contacts_query: Natural language description of who to email (e.g., "founders in Egypt", "all investors")
            purpose: Purpose of the email (e.g., "set up a meeting", "catch up", "introduce myself")
            date_range: Optional date range for meetings (e.g., "March 8-18")
        """
        logger.info(f"[TOOL] draft_emails: query='{contacts_query}', purpose='{purpose}', dates='{date_range}'")

        try:
            from services.outreach_direct import create_outreach_drafts

            count, summary, previews = create_outreach_drafts(
                contacts_query=contacts_query,
                purpose=purpose,
                date_range=date_range,
            )

            if count == 0:
                return f"No drafts created.\n\n{summary}"

            # Build user-facing response with previews
            response = f"**{count} email draft(s) saved to Airtable (PENDING).**\n\n"
            response += f"{summary}\n\n"

            # Show first 5 previews
            for i, p in enumerate(previews[:5], 1):
                response += (
                    f"**{i}. To: {p['to']}** ({p['email']})\n"
                    f"   Subject: {p['subject']}\n"
                    f"   {p['body_preview']}\n\n"
                )
            if len(previews) > 5:
                response += f"_...and {len(previews) - 5} more._\n\n"

            response += "Review in Airtable, set approval_status to APPROVED, then /send_approved."
            return response

        except Exception as e:
            logger.error(f"Draft emails error: {e}")
            import traceback
            traceback.print_exc()
            return f"Error drafting emails: {str(e)}"

    # === PHASE 3 TOOLS ===

    async def process_business_card(self, image_path: str) -> str:
        """
        Extract contact info from a business card photo and create a new contact.
        
        Args:
            image_path: Path to the business card image
        """
        logger.info(f"[TOOL] process_business_card: {image_path}")
        
        from services.auto_enrichment import extract_business_card
        
        extracted = await extract_business_card(image_path)
        
        if not extracted or not extracted.get("name"):
            return "Couldn't extract contact info from this image. Try a clearer photo."
        
        name = extracted["name"]
        
        # Create the contact via add_contact
        result = await self.add_contact(
            name=name,
            title=extracted.get("title"),
            company=extracted.get("company"),
            email=extracted.get("email"),
            phone=extracted.get("phone"),
            linkedin=extracted.get("linkedin_url"),
            notes=extracted.get("notes")
        )
        
        # Auto-save it
        save_result = await self.save_contact()
        
        # Build response
        fields_found = [k for k, v in extracted.items() if v and k != "name"]
        return f"📸 Extracted from business card!\n\n**{name}**\n" + \
               "\n".join(f"• {k}: {v}" for k, v in extracted.items() if v and k != "name") + \
               f"\n\n{save_result}"

    async def linkedin_lookup(self, url: str) -> str:
        """
        Look up a LinkedIn profile and return a rich summary.
        Requires the LinkedIn scraper service running on Ahmed's Mac.
        
        Args:
            url: LinkedIn profile URL (e.g. https://linkedin.com/in/username)
        """
        logger.info(f"[TOOL] linkedin_lookup: {url}")
        
        if "linkedin.com/in/" not in url:
            return "That doesn't look like a LinkedIn profile URL. Need something like linkedin.com/in/username"
        
        from services.auto_enrichment import deep_enrich_from_linkedin
        
        result = await deep_enrich_from_linkedin("lookup", url)
        
        if not result:
            # Fallback: extract name from URL slug and do targeted Tavily search
            logger.info("[TOOL] Scraper offline, falling back to targeted Tavily lookup")
            try:
                import re
                slug = url.split("/in/")[-1].split("?")[0].rstrip("/")
                name_from_slug = re.sub(r'-[a-f0-9]{6,}$', '', slug).replace("-", " ").title()
                
                from services.auto_enrichment import _search_person
                search_results = await _search_person(name_from_slug, linkedin_url=url)
                
                if search_results:
                    import openai
                    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    search_text = "\n".join([
                        f"- {r.get('title', '')}: {r.get('content', '')[:300]}"
                        for r in search_results[:5]
                    ])
                    
                    response = client.chat.completions.create(
                        model=AIConfig.OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": f"Based on these search results about {name_from_slug} (LinkedIn: {url}), write a concise professional profile. Include: current role, company, location, skills, and background. Only include info about THIS specific person — ignore anyone else with a similar name. Be concise."},
                            {"role": "user", "content": search_text}
                        ],
                        temperature=0,
                        max_tokens=500
                    )
                    
                    profile_text = response.choices[0].message.content.strip()
                    return f"🔍 **{name_from_slug}**\n🔗 {url}\n\n{profile_text}\n\nWant me to save them as a contact?"
                    
            except Exception as e:
                logger.warning(f"[TOOL] Tavily fallback failed: {e}")
            
            return f"Couldn't pull data for that profile right now. Want me to just add them with the LinkedIn URL?"
        
        raw = result.get("_raw_linkedin", {})
        summary = result.get("_linkedin_summary", "")
        
        if not raw:
            return "Got a response but no profile data. The profile might be private."
        
        # Build a rich response
        parts = [f"🔍 **{raw.get('name', 'Unknown')}**"]
        if raw.get("headline"):
            parts.append(f"_{raw['headline']}_")
        if raw.get("location"):
            parts.append(f"📍 {raw['location']}")
        
        parts.append("")
        
        if raw.get("about"):
            parts.append(raw["about"][:500])
            parts.append("")
        
        if raw.get("experience"):
            parts.append("💼 **Experience:**")
            for exp in raw["experience"][:5]:
                line = f"• {exp.get('title', '?')} at {exp.get('company', '?')}"
                if exp.get("duration"):
                    line += f" ({exp['duration']})"
                parts.append(line)
            if len(raw["experience"]) > 5:
                parts.append(f"  ...+{len(raw['experience']) - 5} more roles")
            parts.append("")
        
        if raw.get("skills"):
            parts.append(f"🛠 **Skills ({len(raw['skills'])}):** {', '.join(raw['skills'][:15])}")
            parts.append("")
        
        if raw.get("education"):
            parts.append("🎓 **Education:**")
            for edu in raw["education"]:
                parts.append(f"• {edu.get('degree', '')} — {edu.get('school', '')}")
            parts.append("")
        
        # Ask if they want to save
        parts.append("Want me to save them as a contact? 👀")
        
        return "\n".join(parts)

    # Utility method to execute a tool by name
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name with arguments."""
        tool_map = {
            'add_contact': self.add_contact,
            'update_contact': self.update_contact,
            'update_existing_contact': self.update_existing_contact,
            'save_contact': self.save_contact,
            'search_web': self.search_web,
            'summarize_search_results': self.summarize_search_results,
            'get_contact': self.get_contact,
            'cancel_current': self.cancel_current,
            'list_contacts': self.list_contacts,
            'get_search_links': self.get_search_links,
            'enrich_contact': self.enrich_contact,
            'deep_research': self.deep_research,
            'get_draft_status': self.get_draft_status,
            # V3 Phase 1 Tools
            'log_interaction': self.log_interaction,
            'set_follow_up': self.set_follow_up,
            'get_follow_ups': self.get_follow_ups,
            'get_relationship_health': self.get_relationship_health,
            # V3 Phase 2 Tools
            'create_introduction': self.create_introduction,
            'get_introductions': self.get_introductions,
            'suggest_introductions': self.suggest_introductions,
            'get_daily_digest': self.get_daily_digest,
            'get_weekly_report': self.get_weekly_report,
            'search_contacts': self.search_contacts,
            'draft_emails': self.draft_emails,
            # V3 Phase 3 Tools
            'process_business_card': self.process_business_card,
            'linkedin_lookup': self.linkedin_lookup,
        }

        if tool_name not in tool_map:
            return f"Unknown tool: {tool_name}"

        try:
            result = await tool_map[tool_name](**arguments)
            return result
        except TypeError as e:
            logger.error(f"[TOOL] {tool_name} argument error: {e}")
            return f"Error calling {tool_name}: Invalid arguments"
        except Exception as e:
            logger.error(f"[TOOL] {tool_name} execution error: {e}")
            return f"Error executing {tool_name}: {str(e)}"
