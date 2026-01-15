"""
Agent Tools for the Rover Network Agent.
These tools are called by the AI agent to perform actions.
"""

import json
import logging
from typing import Optional, Dict, Any, List

from services.contact_memory import get_memory_service, ConversationState
from services.google_sheets import get_sheets_service
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


def save_contact_to_storage(contact: Contact) -> tuple[bool, str, str]:
    """Save a contact to storage. Returns (success, storage_type, error_message)."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        if sheets.add_contact(contact):
            logger.info(f"[STORAGE] Contact '{contact.name}' saved to Google Sheets")
            return True, "google_sheets", ""
        else:
            # add_contact returned False - likely duplicate email with same-name contact
            logger.warning(f"[STORAGE] add_contact returned False for '{contact.name}' - checking for duplicates")
            # Check if contact actually exists (might be a name collision)
            existing = sheets.get_contact_by_name(contact.name)
            if existing:
                return False, "", f"Contact '{contact.name}' already exists. Use 'update' to modify it."
            return False, "", f"Could not save '{contact.name}' - check for duplicate email."
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")

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
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = get_memory_service()

    async def add_contact(self, name: str, title: str = None, company: str = None,
                         email: str = None, phone: str = None, linkedin: str = None,
                         contact_type: str = None, company_description: str = None,
                         location: str = None, notes: str = None) -> str:
        """Add a new contact and start editing it."""
        logger.info(f"[TOOL] add_contact called: name={name}")

        # Check if already editing someone
        pending = self.memory.get_pending_contact(self.user_id)
        if pending:
            return f"Already editing {pending.name}. Say 'done' to save first, or 'cancel' to discard."

        # Create the contact
        name_parts = name.split()
        contact = Contact(
            full_name=name,
            first_name=name_parts[0] if name_parts else '',
            last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
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

        # Start collecting mode
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
        pending = self.memory.get_pending_contact(self.user_id)
        if not pending:
            return "No contact being edited. Start with 'Add [name]' first."

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
            return f"No updates provided for {pending.name}."

        # Apply updates
        self.memory.update_pending(self.user_id, updates)

        # Format response
        update_parts = [f"{k}='{v}'" for k, v in updates.items()]
        logger.info(f"[TOOL] update_contact: {pending.name} -> {update_parts}")

        return f"Updated {pending.name}: {', '.join(update_parts)}"

    async def save_contact(self) -> str:
        """Save the current contact to the database."""
        pending = self.memory.get_pending_contact(self.user_id)
        if not pending:
            return "No contact to save."

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

            # CRITICAL: Hard reset clears ALL context and LOCKS the saved contact
            # This prevents the "zombie context" bug where old contact data leaks to new contacts
            self.memory.hard_reset(self.user_id, saved_name)

            # Track last contact for reference (but it's now LOCKED)
            _user_last_contact[self.user_id] = saved_name
            _user_last_action[self.user_id] = f"saved and LOCKED contact '{saved_name}'"

            logger.info(f"[TOOL] save_contact: Saved and LOCKED {saved_name}. Context cleared.")
            return f"Saved {saved_name} to your network! ✅ Session cleared.\n\n{format_contact_card(saved_contact)}"

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
        pending = self.memory.get_pending_contact(self.user_id)

        if not pending:
            return "Nothing to cancel."

        name = pending.name
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
        Enrich a contact with web research data.
        Returns a SYSTEM_NOTE that FORCES the agent to update the contact.
        """
        # Determine which contact to enrich
        pending = self.memory.get_pending_contact(self.user_id)

        if name:
            target_name = name
            target_company = None
            # Check if we're enriching the pending contact or an existing one
            if pending and name.lower() in pending.name.lower():
                target_company = pending.company
        elif pending:
            target_name = pending.name
            target_company = pending.company
        else:
            # Check last mentioned contact
            last = _user_last_contact.get(self.user_id)
            if last:
                target_name = last
                target_company = None
            else:
                return "Who should I enrich? Add a contact first or specify a name."

        logger.info(f"[TOOL] enrich_contact: Enriching '{target_name}' (company: {target_company})")

        # Get enrichment data
        enrichment = get_enrichment_service()
        result = enrichment.enrich_contact_comprehensive(target_name, target_company)

        status = result.get("status", "Failed")
        if status == "Failed":
            return f"Could not find enrichment data for {target_name}. {result.get('notes', '')}"

        # Build the SYSTEM_NOTE format to force the agent to apply the data
        # This is the critical fix - we're telling the agent this is DATA TO APPLY, not just text to show

        # Prepare the fields that were found
        found_fields = {}
        field_mappings = {
            "contact_linkedin_url": "linkedin",
            "company_linkedin_url": "company_linkedin",
            "title": "title",
            "company": "company",
            "industry": "industry",
            "company_description": "company_description",
            "contact_type": "contact_type",
            "linkedin_summary": "linkedin_summary",
            "website": "website",
            "address": "location",
            "funding_raised": "funding_raised",
            "key_strengths": "key_strengths",
            "research_quality": "research_quality",
        }

        for enrich_key, tool_key in field_mappings.items():
            value = result.get(enrich_key)
            if value and value != "NA":
                found_fields[tool_key] = value

        # Track context
        _user_last_action[self.user_id] = f"enriched '{target_name}'"
        _user_last_contact[self.user_id] = target_name

        # If we have a pending contact, AUTO-APPLY the enrichment data
        if pending and target_name.lower() in pending.name.lower():
            # Apply updates to pending contact
            updates = {}
            if found_fields.get("linkedin"):
                updates["linkedin_url"] = found_fields["linkedin"]
            if found_fields.get("company_linkedin"):
                updates["linkedin_link"] = found_fields["company_linkedin"]
            if found_fields.get("title") and not pending.title:
                updates["title"] = found_fields["title"]
            if found_fields.get("company") and not pending.company:
                updates["company"] = found_fields["company"]
            if found_fields.get("industry"):
                updates["industry"] = found_fields["industry"]
            if found_fields.get("company_description"):
                updates["company_description"] = found_fields["company_description"]
            if found_fields.get("contact_type") and not pending.contact_type:
                updates["contact_type"] = found_fields["contact_type"]
            if found_fields.get("linkedin_summary"):
                updates["linkedin_summary"] = found_fields["linkedin_summary"]
            if found_fields.get("website"):
                updates["website"] = found_fields["website"]
            if found_fields.get("location") and not pending.address:
                updates["address"] = found_fields["location"]
            if found_fields.get("research_quality"):
                updates["research_quality"] = found_fields["research_quality"]

            if updates:
                self.memory.update_pending(self.user_id, updates)
                logger.info(f"[TOOL] enrich_contact: AUTO-APPLIED {len(updates)} fields to pending contact")

            # Build response
            applied_list = list(updates.keys())
            response = f"""ENRICHMENT COMPLETE for {target_name}.

**I found and AUTO-APPLIED these fields to the profile:**
"""
            for field in applied_list:
                response += f"• {field}: {updates[field][:50]}{'...' if len(str(updates[field])) > 50 else ''}\n"

            response += f"\n**Research Quality:** {result.get('research_quality', 'Medium')}"
            response += "\n\n_Say 'save' when ready to save this contact._"

            return response

        else:
            # No pending contact - return the data for the agent to use with update_existing_contact
            import json
            return f"""SYSTEM_NOTE: ENRICHMENT DATA FOUND. YOU MUST UPDATE THE CONTACT '{target_name}' WITH THIS DATA:

{json.dumps(found_fields, indent=2)}

ACTION REQUIRED: Call update_existing_contact with name="{target_name}" and the fields above.
DO NOT just display this data - you must APPLY it to the contact."""

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
