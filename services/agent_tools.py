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
import re
from typing import Optional, Dict, Any, List

from services.contact_memory import get_memory_service, ConversationState
from services.user_session import get_user_session, ContactDraft, DraftStatus
from services.airtable_service import get_sheets_service
from services.enrichment import get_enrichment_service
from services.ai_service import get_ai_service
from data.schema import Contact


logger = logging.getLogger('network_agent')


# Global storage for search results per user (for summarization)
_user_search_results: Dict[str, List[Dict]] = {}
_user_summaries: Dict[str, str] = {}
_user_last_contact: Dict[str, str] = {}  # Track last mentioned/viewed contact name
_user_last_action: Dict[str, str] = {}  # Track last action for "Yes" context
_user_search_query: Dict[str, str] = {}  # Track what was searched
_user_last_mentioned_person: Dict[str, str] = {}  # Track last PERSON mentioned (for "Add him/her")


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
        return f"Started new contact: {name}{detail_str}. Add more info or say 'done' to save."

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
            return f"Saved {saved_name} to your network! ✅\n\n{format_contact_card(saved_contact)}"

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
        try:
            from datetime import datetime
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date format. Use YYYY-MM-DD (e.g., 2026-03-15)"
        
        # Update contact with follow-up info
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        updates = {
            "follow_up_date": date,
            "follow_up_reason": reason or ""
        }
        
        success = sheets.update_contact(name, updates)
        
        if success:
            _user_last_action[self.user_id] = f"set follow-up for '{name}'"
            
            reason_str = f": {reason}" if reason else ""
            return f"⏰ Follow-up set for **{name}** on {date}{reason_str}"
        
        return f"Failed to set follow-up for {name}."
    
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
        contacts = tracker.get_contacts_needing_follow_up(self.user_id)
        
        if not contacts:
            return "No pending follow-ups. You're all caught up! ✅"
        
        # Sort by date
        def parse_date(contact):
            try:
                if len(contact.follow_up_date) <= 10:
                    return datetime.strptime(contact.follow_up_date, "%Y-%m-%d")
                else:
                    return datetime.strptime(contact.follow_up_date, "%Y-%m-%d %H:%M:%S")
            except:
                return datetime.max
        
        contacts.sort(key=parse_date)
        
        # Format response
        response = f"**📅 Pending Follow-ups ({len(contacts)}):**\n\n"
        
        today = datetime.now().date()
        for contact in contacts[:10]:  # Limit to 10
            try:
                if len(contact.follow_up_date) <= 10:
                    follow_up = datetime.strptime(contact.follow_up_date, "%Y-%m-%d").date()
                else:
                    follow_up = datetime.strptime(contact.follow_up_date, "%Y-%m-%d %H:%M:%S").date()
                
                days_diff = (follow_up - today).days
                
                if days_diff < 0:
                    urgency = f"⚠️ {abs(days_diff)} days overdue"
                elif days_diff == 0:
                    urgency = "🔥 TODAY"
                elif days_diff == 1:
                    urgency = "📌 Tomorrow"
                elif days_diff <= 7:
                    urgency = f"📆 In {days_diff} days"
                else:
                    urgency = f"📆 {contact.follow_up_date}"
                
                response += f"• **{contact.name}** - {urgency}\n"
                if contact.company:
                    response += f"  {contact.company}"
                if contact.follow_up_reason:
                    response += f"\n  Reason: {contact.follow_up_reason}"
                response += "\n\n"
                
            except Exception as e:
                logger.error(f"Error formatting follow-up for {contact.name}: {e}")
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
            # V3 New Tools
            'log_interaction': self.log_interaction,
            'set_follow_up': self.set_follow_up,
            'get_follow_ups': self.get_follow_ups,
            'get_relationship_health': self.get_relationship_health,
        }

        if tool_name not in tool_map:
            return f"Unknown tool: {tool_name}"

        try:
            result = await tool_map[tool_name](**arguments)
            return result
        except TypeError as e:
            logger.error(f"Tool argument error: {e}")
            return f"Error calling {tool_name}: Invalid arguments"
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Error executing {tool_name}: {str(e)}"
