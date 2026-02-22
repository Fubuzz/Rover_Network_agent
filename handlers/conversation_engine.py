"""
AI-Powered Conversation Engine for the Network Nurturing Agent.
Uses Gemini for intent classification and entity extraction.
Maintains persistent contact memory across conversations.
Enhanced with deferred saving and smart conversation flow.
"""

import random
import re
from typing import Optional, Dict, Any

from services.conversation_ai import analyze_message, Intent, ConversationResult
from services.contact_memory import get_memory_service, ConversationState
from services.airtable_service import get_sheets_service
from services.local_storage import get_local_storage
from services.enrichment import get_enrichment_service
from crews.researcher_crew import get_researcher_crew
from handlers.enrichment_handlers import format_enrichment_result
from data.schema import Contact
from utils.text_cleaner import sanitize_input


# ============================================================
# STORAGE OPERATIONS
# ============================================================

def save_contact_to_storage(contact: Contact) -> tuple[bool, str, str]:
    """Save a contact to storage. Returns (success, storage_type, error_message)."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        if sheets.add_contact(contact):
            return True, "airtable", ""
        else:
            # add_contact returned False - check why
            existing = sheets.get_contact_by_name(contact.name)
            if existing:
                return False, "", f"Contact '{contact.name}' already exists. Use update instead."
            # Check if email exists on another contact
            if contact.email:
                email_match = sheets.find_contact_by_email(contact.email)
                if email_match:
                    return False, "", f"Email {contact.email} is already used by '{email_match.name}'."
            return False, "", f"Could not save '{contact.name}'. Please try again."
    except Exception as e:
        print(f"Airtable error: {e}")

    try:
        local = get_local_storage()
        if local.add_contact(contact):
            return True, "local", ""
    except Exception as e:
        print(f"Local storage error: {e}")

    return False, "", "Failed to save contact."


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
        print(f"Google Sheets update error: {e}")
    
    try:
        local = get_local_storage()
        if local.update_contact(name, updates):
            return True
    except Exception as e:
        print(f"Local storage update error: {e}")
    
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
        print(f"Google Sheets find error: {e}")
    
    try:
        local = get_local_storage()
        contact = local.get_contact_by_name(name)
        if contact:
            return contact
    except Exception as e:
        print(f"Local storage find error: {e}")
    
    return None


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def find_potential_duplicate(name: str = None, email: str = None, phone: str = None) -> Optional[Contact]:
    """
    Find a potential duplicate contact by name, email, or phone.
    Returns the existing contact if found, None otherwise.

    Only matches on:
    - Exact name match (case insensitive)
    - Exact email match
    - Exact phone match (normalized)

    Does NOT do fuzzy first-name matching to avoid false positives.
    """
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()

        # Check by exact name match only
        if name:
            existing = sheets.get_contact_by_name(name)
            if existing:
                return existing

        # Check by exact email match
        if email and email.strip():
            existing = sheets.find_contact_by_email(email)
            if existing:
                return existing

        # Check by phone (exact match on normalized digits)
        if phone:
            normalized_phone = ''.join(c for c in phone if c.isdigit())
            if len(normalized_phone) >= 7:
                # Search and verify exact match
                matches = sheets.search_contacts(normalized_phone[-7:])
                if matches:
                    for match in matches:
                        if match.phone:
                            match_normalized = ''.join(c for c in match.phone if c.isdigit())
                            if match_normalized[-7:] == normalized_phone[-7:]:
                                return match

    except Exception as e:
        print(f"Duplicate check error: {e}")

    return None


# ============================================================
# RESPONSE GENERATION - Donna Paulsen Style
# ============================================================

def format_contact_card(contact: Contact) -> str:
    """Format a contact as a nice card."""
    lines = [f"📇 **{contact.name}**", ""]
    
    if contact.title:
        line = f"💼 {contact.title}"
        if contact.company:
            line += f" at {contact.company}"
        lines.append(line)
    elif contact.company:
        lines.append(f"🏢 {contact.company}")
    
    if contact.industry:
        lines.append(f"🏭 {contact.industry}")
    if contact.address:
        lines.append(f"📍 {contact.address}")
    if contact.email:
        lines.append(f"📧 {contact.email}")
    if contact.phone:
        lines.append(f"📱 {contact.phone}")
    if contact.linkedin_url or contact.linkedin_link:
        lines.append(f"🔗 {contact.linkedin_url or contact.linkedin_link}")
    
    return "\n".join(lines)


def get_missing_fields_hint(contact: Contact) -> str:
    """Get a hint about missing fields."""
    missing = []
    if not contact.email:
        missing.append("email")
    if not contact.phone:
        missing.append("phone")
    if not contact.title:
        missing.append("title")
    if not contact.company:
        missing.append("company")
    
    if missing and len(missing) <= 3:
        return f"_({', '.join(missing)} missing)_"
    return ""


def random_ack() -> str:
    """Get a warm, human acknowledgment."""
    acks = [
        "Love it!",
        "Got it, thanks!",
        "Nice, added that",
        "Perfect, noted",
        "Great info!",
        "Awesome, I've got that down",
        "Sweet!",
        "Excellent!",
    ]
    return random.choice(acks)


def random_prompt() -> str:
    """Get a warm, conversational prompt for more info."""
    prompts = [
        "What else can you tell me about them?",
        "Anything else you'd like to add?",
        "Tell me more if you've got it!",
        "Keep going, I'm all ears! Or say 'done' when ready.",
        "Got more details? I'm listening!",
        "Feel free to share more, or say 'done' to save.",
    ]
    return random.choice(prompts)


# ============================================================
# INTENT HANDLERS
# ============================================================

async def handle_add_contact(user_id: str, result: ConversationResult) -> str:
    """Handle adding a new contact. Uses deferred saving - contact is NOT saved until 'done'."""
    memory = get_memory_service()

    # Check if we're already collecting - if so, this might be an update in disguise
    if memory.is_collecting(user_id):
        pending = memory.get_pending_contact(user_id)
        if pending:
            # User might be confused, or adding info to current contact
            # Redirect to update if no new name, or name matches current
            new_name = result.entities.get('name', '').lower()
            if not new_name or new_name in pending.name.lower():
                return await handle_update_contact(user_id, result)
            # Different name - ask for clarification
            return (
                f"Hold on! I'm still working on **{pending.name}**. 🤔\n\n"
                f"Want to:\n"
                f"• Say _'done'_ to save {pending.name} first\n"
                f"• Say _'cancel'_ to discard and start fresh\n"
                f"• Or keep adding info about {pending.name}"
            )

    # Get name from entities
    name = result.entities.get('name')
    if not name:
        return "Who are we adding? Give me a name! 📝\n\nTry: _'Add John Smith'_"

    # Check for potential duplicates - by name, email, or phone
    email = result.entities.get('email')
    phone = result.entities.get('phone')
    existing = find_potential_duplicate(name=name, email=email, phone=phone)

    if existing:
        # Found a potential duplicate - ask user what to do
        is_exact_name_match = existing.name and existing.name.lower() == name.lower()

        if is_exact_name_match:
            # Exact name match - switch to update mode automatically
            memory.start_collecting(user_id, existing)
            return (
                f"**{name}** already exists! 📇\n\n"
                f"{format_contact_card(existing)}\n\n"
                f"What would you like to update? Or say _'done'_ if nothing to change."
            )
        else:
            # Similar name or matching email/phone - ask user
            match_reason = ""
            if email and existing.email and email.lower() == existing.email.lower():
                match_reason = f"same email ({email})"
            elif phone and existing.phone:
                match_reason = f"similar phone number"
            else:
                match_reason = f"similar name"

            return (
                f"Found someone similar - **{existing.name}** ({match_reason}):\n\n"
                f"{format_contact_card(existing)}\n\n"
                f"Is **{name}** the same person?\n"
                f"• Say _'yes'_ or _'update'_ to update this contact\n"
                f"• Say _'no'_ or _'new'_ to create a new one"
            )

    # Create the contact (but DON'T save yet!)
    name_parts = name.split()
    contact = Contact.from_dict({
        'name': name,
        'full_name': name,
        'first_name': name_parts[0] if name_parts else '',
        'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
        'title': result.entities.get('title'),
        'company': result.entities.get('company'),
        'email': result.entities.get('email'),
        'phone': result.entities.get('phone'),
        'address': result.entities.get('location'),
        'industry': result.entities.get('industry'),
        'linkedin_url': result.entities.get('linkedin'),
    })
    contact.user_id = user_id

    # Start collecting - this sets state to COLLECTING
    memory.start_collecting(user_id, contact)

    # Build response
    response = f"📝 Starting a new contact for **{name}**!"

    # Show what we captured so far
    details = []
    if contact.title:
        details.append(f"💼 {contact.title}")
    if contact.company:
        details.append(f"🏢 {contact.company}")
    if contact.email:
        details.append(f"📧 {contact.email}")
    if contact.phone:
        details.append(f"📱 {contact.phone}")

    if details:
        response += "\n" + " | ".join(details)

    # Prompt for more
    missing = get_missing_fields_hint(contact)
    response += f"\n\nTell me more about **{name}**! {missing}"
    response += "\n\n_Say 'done' to save, or 'cancel' to discard._ 💅"

    return response


async def handle_update_contact(user_id: str, result: ConversationResult) -> str:
    """Handle updating a contact with new info. Updates pending contact (not saved yet)."""
    memory = get_memory_service()

    # Get current pending contact
    pending = memory.get_pending_contact(user_id)
    contact = None
    is_pending = False
    context_switched = False

    # CRITICAL: Check if user is referring to a DIFFERENT person
    # This handles: "add Yousra's LinkedIn" while working on Farook
    target_name = result.target_contact
    if target_name:
        # Normalize names for comparison
        target_lower = target_name.lower().strip()
        pending_name_lower = pending.name.lower().strip() if pending else ""

        # Check if target is different from pending contact
        if pending and target_lower and target_lower not in pending_name_lower and pending_name_lower not in target_lower:
            # User is referring to a DIFFERENT person - need to switch context
            # First, try to find the target contact
            target_contact = memory.find_contact(user_id, target_name)
            if not target_contact:
                target_contact = find_contact_in_storage(target_name)

            if target_contact:
                # Found the target! Switch context to them
                # Note: Don't discard pending, just switch focus
                memory.start_collecting(user_id, target_contact)
                contact = target_contact
                is_pending = True
                context_switched = True
            else:
                # Target not found - ask user what they want
                return (
                    f"I don't have **{target_name}** in my records yet. 🤔\n\n"
                    f"I'm currently working on **{pending.name}**.\n\n"
                    f"Would you like to:\n"
                    f"• Add **{target_name}** as a new contact? (say _'add {target_name}'_)\n"
                    f"• Continue with **{pending.name}**? (just tell me more about them)"
                )

    # If no context switch happened, use pending contact
    if not contact and pending:
        contact = pending
        is_pending = True

    # If still no contact, try to find by target name (for when there's no pending)
    if not contact and target_name:
        contact = memory.find_contact(user_id, target_name)
        if not contact:
            contact = find_contact_in_storage(target_name)
            if contact:
                memory.start_collecting(user_id, contact)
                is_pending = True

    # Fall back to current contact
    if not contact:
        current = memory.get_current_contact(user_id)
        if current:
            memory.start_collecting(user_id, current)
            contact = current
            is_pending = True

    if not contact:
        return (
            "Who are we talking about? 🤔\n\n"
            "Start with _'Add [Name]'_ or mention a name!"
        )

    # Get the updates from entities
    entities = result.entities
    updates = {}

    # Map entities to contact fields
    field_mapping = {
        'title': 'title',
        'company': 'company',
        'email': 'email',
        'phone': 'phone',
        'location': 'address',
        'industry': 'industry',
        'linkedin': 'linkedin_url',
        'notes': 'notes',
        'name': 'name',  # Allow name updates too
        'contact_type': 'contact_type',  # founder, investor, enabler, professional
        'company_description': 'company_description',
    }

    for entity_key, contact_field in field_mapping.items():
        if entity_key in entities and entities[entity_key]:
            updates[contact_field] = entities[entity_key]

    if not updates:
        return (
            f"Not sure what to add for **{contact.name}**. 🤔\n\n"
            "Try:\n"
            f"• _'She's the CEO of TechCorp'_\n"
            f"• _'Email is john@test.com'_\n"
            f"• _'Based in New York'_\n\n"
            "Or say _'done'_ to save!"
        )

    # Update the pending contact in memory (NOT storage yet!)
    memory.update_pending(user_id, updates)

    # Get updated contact from memory
    contact = memory.get_pending_contact(user_id) or memory.get_current_contact(user_id)

    # Build response
    if context_switched:
        response = f"Switching to **{contact.name}**! ✨ "
    else:
        response = f"{random_ack()} "

    update_parts = []
    if 'title' in updates:
        update_parts.append(f"**{updates['title']}**")
    if 'company' in updates:
        update_parts.append(f"at **{updates['company']}**")
    if 'email' in updates:
        update_parts.append(f"📧 {updates['email']}")
    if 'phone' in updates:
        update_parts.append(f"📱 {updates['phone']}")
    if 'address' in updates:
        update_parts.append(f"📍 {updates['address']}")
    if 'industry' in updates:
        update_parts.append(f"🏭 {updates['industry']}")
    if 'linkedin_url' in updates:
        update_parts.append(f"🔗 LinkedIn added")
    if 'contact_type' in updates:
        update_parts.append(f"🏷️ Type: **{updates['contact_type']}**")
    if 'company_description' in updates:
        update_parts.append(f"📄 Company info added")
    if 'notes' in updates:
        update_parts.append(f"📝 Note added")

    response += " | ".join(update_parts) if update_parts else "Updated!"

    # Add missing fields hint and prompt
    missing = get_missing_fields_hint(contact) if contact else ""
    response += f"\n\n{random_prompt()} {missing}"

    return response


async def handle_query(user_id: str, result: ConversationResult) -> str:
    """Handle a question about a contact."""
    memory = get_memory_service()
    
    # Find the target contact
    target_name = result.target_contact
    contact = None
    
    if target_name:
        contact = memory.find_contact(user_id, target_name)
        if not contact:
            contact = find_contact_in_storage(target_name)
    
    if not contact:
        contact = memory.get_current_contact(user_id)
    
    if not contact:
        return "Who are you asking about? 🤔\n\nTell me a name!"
    
    # What field are they asking about?
    query_field = result.query_field
    
    if query_field == "email" or "email" in str(result.raw_response).lower():
        if contact.email:
            return f"**{contact.name}**'s email is 📧 {contact.email}"
        else:
            return f"I don't have an email for **{contact.name}**. What is it?"
    
    if query_field == "phone" or "phone" in str(result.raw_response).lower():
        if contact.phone:
            return f"**{contact.name}**'s phone is 📱 {contact.phone}"
        else:
            return f"No phone for **{contact.name}** yet. What is it?"
    
    if query_field == "title" or query_field == "role" or "title" in str(result.raw_response).lower():
        if contact.title:
            response = f"**{contact.name}** is **{contact.title}**"
            if contact.company:
                response += f" at {contact.company}"
            return response
        else:
            return f"I don't have a title for **{contact.name}**. What is it?"
    
    if query_field == "location" or "location" in str(result.raw_response).lower() or "where" in str(result.raw_response).lower():
        if contact.address:
            return f"**{contact.name}** is based in 📍 {contact.address}"
        else:
            return f"I don't have a location for **{contact.name}**. Where are they?"
    
    if query_field == "company" or "company" in str(result.raw_response).lower():
        if contact.company:
            response = f"**{contact.name}** works at 🏢 **{contact.company}**"
            if contact.title:
                response += f" as {contact.title}"
            return response
        else:
            return f"I don't know where **{contact.name}** works."
    
    if query_field == "linkedin":
        linkedin = contact.linkedin_url or contact.linkedin_link
        if linkedin:
            return f"**{contact.name}**'s LinkedIn: 🔗 {linkedin}"
        else:
            return f"No LinkedIn for **{contact.name}** yet."
    
    # Default: show all info
    return format_contact_card(contact)


async def handle_view(user_id: str, result: ConversationResult) -> str:
    """Handle viewing a contact's full info."""
    memory = get_memory_service()
    
    target_name = result.target_contact
    contact = None
    
    if target_name:
        contact = memory.find_contact(user_id, target_name)
        if not contact:
            contact = find_contact_in_storage(target_name)
    
    if not contact:
        contact = memory.get_current_contact(user_id)
    
    if contact:
        return format_contact_card(contact)
    else:
        return "Who should I show you? Give me a name! 🔍"


async def handle_finish(user_id: str) -> str:
    """Handle finishing with the current contact. NOW we actually save to storage!"""
    memory = get_memory_service()

    # Get the pending contact
    pending = memory.get_pending_contact(user_id)

    if not pending:
        # Maybe they have a current contact but not pending (already saved)
        current = memory.get_current_contact(user_id)
        if current:
            # Check if there are updates to save (user might have added info after initial save)
            updates = {}
            for field in ['title', 'company', 'email', 'phone', 'address', 'industry', 'linkedin_url', 'notes']:
                current_value = getattr(current, field, None)
                if current_value:
                    updates[field] = current_value

            # Update the storage with any new info
            if updates:
                update_contact_in_storage(current.name, updates)

            memory.clear_current(user_id)
            return (
                f"✅ **{current.name}** is already saved!\n\n"
                f"{format_contact_card(current)}\n\n"
                f"_Ready for your next contact._ 😊"
            )
        return "Nothing to save! Add a contact first. 😊\n\nTry: _'Add John Smith'_"

    # Check if this is an update to an existing contact or a new contact
    existing = find_contact_in_storage(pending.name)

    if existing:
        # Update existing contact
        updates = {}
        for field in ['title', 'company', 'email', 'phone', 'address', 'industry', 'linkedin_url', 'notes']:
            pending_value = getattr(pending, field, None)
            if pending_value:
                updates[field] = pending_value

        if updates:
            success = update_contact_in_storage(pending.name, updates)
        else:
            success = True  # Nothing to update, but still success
    else:
        # Save new contact
        success, storage, error_msg = save_contact_to_storage(pending)

    if success:
        # Build success response
        closings = [
            f"✅ **{pending.name}** saved to your network!",
            f"**{pending.name}** is locked and loaded! 🎯",
            f"All done with **{pending.name}**! 💅",
        ]

        response = random.choice(closings) + "\n\n"
        response += format_contact_card(pending)

        # Check if contact could benefit from enrichment
        offer_enrichment = _should_offer_enrichment(pending)
        if offer_enrichment:
            response += "\n\n_Would you like me to **enrich** this contact?_"
            response += f"\nI can look up: LinkedIn profile, company details, industry info, and more."
            response += f"\n\nJust say _'enrich'_ or _'/enrich {pending.name}'_"
        else:
            response += "\n\n_Session cleared. Ready for the next one!_ 😉"

        # CRITICAL: Hard reset clears ALL context and LOCKS the saved contact
        # This prevents the "zombie context" bug where old contact data leaks to new contacts
        memory.hard_reset(user_id, pending.name)

        # Store last saved contact name for potential enrichment
        memory.set_last_saved_contact(user_id, pending.name, pending.company)

        return response
    else:
        return (
            f"Hmm, couldn't save **{pending.name}**. 😬\n\n"
            "Try saying _'done'_ again, or check if they already exist."
        )


def _should_offer_enrichment(contact: Contact) -> bool:
    """Check if a contact could benefit from enrichment."""
    # Key fields that enrichment can fill
    enrichable_fields = [
        ('linkedin_url', contact.linkedin_url),
        ('company_description', contact.company_description),
        ('industry', contact.industry),
        ('title', contact.title),
        ('company', contact.company),
    ]

    # Count missing enrichable fields
    missing_count = sum(1 for field, value in enrichable_fields if not value or value == "NA")

    # Offer enrichment if at least 2 enrichable fields are missing
    return missing_count >= 2


async def handle_cancel(user_id: str) -> str:
    """Handle canceling the current contact without saving."""
    memory = get_memory_service()

    pending = memory.get_pending_contact(user_id)

    if not pending:
        current = memory.get_current_contact(user_id)
        if current:
            memory.clear_current(user_id)
            return f"Cleared **{current.name}** from my mind. 🧹\n\n_Ready for your next contact._"
        return "Nothing to cancel! 🤷\n\n_Start with 'Add [Name]' to add a contact._"

    name = pending.name

    # Discard the pending contact
    memory.cancel_pending(user_id)

    responses = [
        f"Discarded **{name}**. Never happened! 🗑️",
        f"**{name}**? Who's that? Never heard of them. 😏",
        f"Poof! **{name}** is gone. 💨",
    ]

    return random.choice(responses) + "\n\n_Ready for your next contact._"


async def handle_greeting(user_id: str) -> str:
    """Handle greetings."""
    memory = get_memory_service()
    current = memory.get_current_contact(user_id) or memory.get_pending_contact(user_id)

    # Time-aware greetings
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"

    greetings = [
        f"{time_greeting}! How can I help you manage your network today?",
        f"{time_greeting}! Ready to add or look up some contacts?",
        "Hello! I'm here to help with your professional network.",
        "Hey there! What can I do for you today?",
        "Hi! Need to add a contact or look someone up?",
    ]
    response = random.choice(greetings)

    if current:
        response += f"\n\n_Currently working on **{current.name}**. Say 'done' to save or keep adding info._"

    return response


async def handle_thanks() -> str:
    """Handle thank you messages."""
    responses = [
        "You're welcome. _I know, I'm amazing._ 💅",
        "Of course! That's what I'm here for. 😊",
        "Anytime. Now go close that deal! 💪",
        "Don't mention it. Actually, do. I like appreciation. 😏",
    ]
    return random.choice(responses)


async def handle_help() -> str:
    """Handle help requests."""
    return (
        "Here's what I can do: 🌟\n\n"
        "📇 **Add contacts**: _'Add John Smith'_\n"
        "📝 **Add details**: _'He's the CEO of TechCorp'_\n"
        "📧 **Add info**: _'His email is john@tech.com'_\n"
        "🔍 **Query**: _'What's John's title?'_\n"
        "👀 **View**: _'Show me John's info'_\n"
        "🌐 **Search**: _'Search for info on TechCorp'_\n"
        "✅ **Finish**: _'Done'_\n\n"
        "_Just talk to me naturally!_ 💬"
    )


async def handle_search(user_id: str, result: ConversationResult, original_message: str = "") -> str:
    """Handle search/enrichment requests using the dedicated Researcher Agent."""
    memory = get_memory_service()
    enrichment = get_enrichment_service()

    # Get current contact if any
    current = memory.get_current_contact(user_id) or memory.get_pending_contact(user_id)

    # Use the original message for pattern matching
    msg_lower = original_message.lower() if original_message else ""

    # Detect search type: LinkedIn, Person, Company, or General
    search_type = "general"
    search_query = None
    person_name = None
    company_name = None

    # Check for LinkedIn-specific searches
    linkedin_patterns = [
        r"(?:find|search|get|look up|show me).*linkedin.*(?:for|of|on)?\s*([a-zA-Z\s]+)",
        r"([a-zA-Z\s]+?)(?:'s|s)?\s*linkedin",
        r"linkedin.*(?:for|of)\s*([a-zA-Z\s]+)",
    ]
    for pattern in linkedin_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            search_type = "linkedin"
            person_name = match.group(1).strip()
            # Clean up common words
            person_name = re.sub(r'^(for|of|on|about|any|the)\s+', '', person_name)
            person_name = re.sub(r'\s+(profile|page|url|link)$', '', person_name)
            break

    # Check for person-specific searches
    if search_type == "general":
        person_patterns = [
            r"(?:search|find|look up|research).*(?:info|information|details|background).*(?:on|about|for)\s+([a-zA-Z\s]+)",
            r"(?:search|find|look up|research)\s+(?:any\s+)?(?:info|information)?\s*(?:on|about|for)\s+([a-zA-Z\s]+)",
            r"(?:who is|tell me about)\s+([a-zA-Z\s]+)",
        ]
        for pattern in person_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                query = match.group(1).strip()
                # Check if it looks like a person name (has space, or capitalized)
                if ' ' in query or (original_message and any(c.isupper() for c in original_message)):
                    search_type = "person"
                    person_name = query
                    break

    # Check for company-specific searches
    if search_type == "general":
        company_patterns = [
            r"(?:search|find|look up|research).*(?:what|about)?\s*([a-zA-Z\s]+)\s*(?:does|do|is|company|startup)",
            r"(?:what does|what do|what is)\s+([a-zA-Z\s]+)\s+(?:do|does|provide|offer)",
            r"(?:search|find).*company.*(?:called|named)?\s*([a-zA-Z\s]+)",
        ]
        for pattern in company_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                search_type = "company"
                company_name = match.group(1).strip()
                break

    # Extract from entities if not found
    if result.entities.get('name') and not person_name:
        person_name = result.entities.get('name')
        if search_type == "general":
            search_type = "person"
    if result.entities.get('company') and not company_name:
        company_name = result.entities.get('company')
        if search_type == "general":
            search_type = "company"

    # General search fallback
    if search_type == "general":
        general_patterns = [
            r"search (?:for )?(.+)",
            r"look up (.+)",
            r"find (?:out )?(?:about )?(.+)",
            r"what (?:can you find|do you know) about (.+)",
        ]
        for pattern in general_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                search_query = match.group(1).strip()
                # Clean up common words
                search_query = re.sub(r'^(what|exactly|info on|info about|about)\s+', '', search_query)
                search_query = re.sub(r'\s+(does|is|are|do|and add it).*$', '', search_query)
                break

    # Use current contact's info if nothing extracted
    if not person_name and not company_name and not search_query:
        if current:
            if current.company:
                company_name = current.company
                search_type = "company"
            elif current.name:
                person_name = current.name
                search_type = "person"

    # If still nothing, ask for clarification
    if not person_name and not company_name and not search_query:
        if current:
            return (
                f"What should I search for? 🔍\n\n"
                f"I can look up:\n"
                f"• _'{current.name}'s LinkedIn'_\n"
                f"• _'Search for {current.company or 'their company'}'_\n"
                f"• _'Research {current.name}'_"
            )
        return (
            "What would you like me to search for? 🔍\n\n"
            "Try:\n"
            "• _'Find Ahmed Abaza's LinkedIn'_\n"
            "• _'Search for Synapse Analytics'_\n"
            "• _'Research info on John Smith'_"
        )

    # Check if search is available
    if not enrichment.is_available():
        error = enrichment.get_last_error()
        if error and "Invalid API key" in error:
            return "⚠️ Search is currently unavailable - API key issue.\n\n_I can still help you manage contacts!_"
        # Try to reinitialize
        enrichment._tavily_client = None
        enrichment._api_valid = None

    try:
        researcher = get_researcher_crew()

        # Execute search based on type
        if search_type == "linkedin":
            response = f"🔍 Searching for **{person_name}**'s LinkedIn profile...\n\n"
            search_result = researcher.search_linkedin(
                name=person_name,
                company=company_name or (current.company if current else None)
            )

        elif search_type == "person":
            response = f"🔍 Researching **{person_name}**...\n\n"
            search_result = researcher.research_person(
                name=person_name,
                company=company_name or (current.company if current else None)
            )

        elif search_type == "company":
            response = f"🔍 Researching **{company_name}**...\n\n"
            search_result = researcher.research_company(company_name)

        else:
            query = search_query or person_name or company_name
            response = f"🔍 Searching for **{query}**...\n\n"
            search_result = researcher.search_general(query)

        # Format the result
        if search_result:
            # Clean up CrewAI output formatting
            clean_result = str(search_result)
            # Remove agent verbose output patterns
            clean_result = re.sub(r'\[DEBUG\].*?\n', '', clean_result)
            clean_result = re.sub(r'Agent:.*?\n', '', clean_result)
            clean_result = re.sub(r'Task:.*?\n', '', clean_result)
            clean_result = re.sub(r'> Entering.*?\n', '', clean_result)
            clean_result = re.sub(r'> Finished.*?\n', '', clean_result)

            response += clean_result.strip()

            # Store for later summarization
            store_search_results(user_id, person_name or company_name or search_query,
                                 [{'title': 'Search Result', 'snippet': clean_result.strip()}])

            # Extract LinkedIn URL if present
            linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', clean_result)
            if linkedin_match and current:
                linkedin_url = linkedin_match.group(0)
                response += f"\n\n_Want me to add this LinkedIn ({linkedin_url}) to **{current.name}**?_"
        else:
            response += "Couldn't find much information. Try being more specific or check the spelling."

        return response

    except Exception as e:
        import logging
        logger = logging.getLogger('network_agent')
        logger.error(f"Search error: {e}")
        import traceback
        traceback.print_exc()

        # Fallback to basic search
        try:
            query = person_name or company_name or search_query
            results = enrichment._search(query, 5)
            if results:
                response = f"🔍 Results for **{query}**:\n\n"
                for i, r in enumerate(results[:3], 1):
                    response += f"**{i}.** {r.get('title', '')}\n"
                    response += f"_{r.get('snippet', '')[:150]}_\n"
                    response += f"Link: {r.get('link', '')}\n\n"
                return response
        except Exception as fallback_err:
            logger.error(f"Fallback search also failed: {fallback_err}")

        return (
            "Oops! Had trouble with that search. 😅\n\n"
            "Try:\n"
            "• Being more specific with the name\n"
            "• Adding a company name\n"
            "• Checking the spelling"
        )


async def handle_unknown(user_id: str, message: str = "") -> str:
    """Handle unknown intents with friendly guidance."""
    memory = get_memory_service()
    current = memory.get_current_contact(user_id) or memory.get_pending_contact(user_id)

    # Check if this looks like a partial message (ends with "is", "are", etc.)
    msg_lower = message.lower().strip()
    if msg_lower.endswith((' is', ' are', ' at', "'s")):
        if current:
            return f"Got it, go ahead and tell me the rest! I'm listening... 👂"
        else:
            return "I'm listening! What's the rest of that? 👂"

    # Check if it's just a number (might be a phone that followed "his phone is")
    if re.match(r'^[\d\s\-\+\(\)]+$', message.strip()) and len(message.strip()) >= 5:
        if current:
            # Assume it's a phone number
            return f"Hmm, is **{message.strip()}** a phone number for **{current.name}**? Try saying _'phone is {message.strip()}'_"

    if current:
        friendly_responses = [
            f"Hmm, I didn't quite catch that! 😅 I'm still working on **{current.name}**.",
            f"Not sure I understood. Still here with **{current.name}** though!",
            f"Sorry, that went over my head! 🙈 What would you like to add to **{current.name}**?",
        ]
        return (
            f"{random.choice(friendly_responses)}\n\n"
            f"You can:\n"
            f"• Add info: _'She's the CEO at TechCorp'_\n"
            f"• Ask questions: _'What's her email?'_\n"
            f"• Finish: _'Done'_"
        )
    else:
        friendly_responses = [
            "Hmm, I'm not quite sure what you need! 🤔",
            "Sorry, didn't catch that! Let me help you out.",
            "I'm a bit confused! 😅 Here's what I can do:",
        ]
        return (
            f"{random.choice(friendly_responses)}\n\n"
            "Try:\n"
            "• _'Add John Smith'_ to add a contact\n"
            "• _'Show me John's info'_ to view someone\n"
            "• _'/help'_ for all commands"
        )


# ============================================================
# NEW INTENT HANDLERS (Confirm, Deny, Summarize, General Request)
# ============================================================

# Store last search results for summarization (with timestamps for cleanup)
_last_search_results: dict = {}
_last_search_timestamps: dict = {}
_SEARCH_RESULTS_TTL = 1800  # 30 minutes


def _store_search_results(user_id: str, results):
    """Store search results with timestamp for TTL-based cleanup."""
    import time
    _last_search_results[user_id] = results
    _last_search_timestamps[user_id] = time.time()
    _cleanup_stale_search_results()


def _cleanup_stale_search_results():
    """Remove search results older than TTL."""
    import time
    now = time.time()
    stale = [uid for uid, ts in _last_search_timestamps.items()
             if now - ts > _SEARCH_RESULTS_TTL]
    for uid in stale:
        _last_search_results.pop(uid, None)
        _last_search_timestamps.pop(uid, None)


async def handle_confirm(user_id: str, result: ConversationResult) -> str:
    """Handle confirmation responses (yes, ok, sure)."""
    memory = get_memory_service()
    state = memory.get_state(user_id)

    # If in confirming state (e.g., duplicate detection), handle it
    if state == ConversationState.CONFIRMING:
        # User confirmed updating existing contact
        pending = memory.get_pending_contact(user_id)
        if pending:
            return await handle_finish(user_id)

    # If collecting, treat "yes" as "done/save"
    pending = memory.get_pending_contact(user_id)
    if pending:
        return await handle_finish(user_id)

    # Check if user might be confirming enrichment offer
    last_saved = memory.get_last_saved_contact(user_id)
    if last_saved and last_saved[0]:
        # User said yes after we offered enrichment
        return await handle_enrich_request(user_id, last_saved[0], last_saved[1])

    return "Got it! What would you like to do next?"


async def handle_enrich_request(user_id: str, name: str, company: Optional[str] = None) -> str:
    """Handle enrichment request for a specific contact."""
    from crews.enrichment_crew import get_enrichment_crew
    import json

    memory = get_memory_service()
    crew = get_enrichment_crew()

    # Check if there's a pending contact in memory to enrich
    pending_contact = memory.get_pending_contact(user_id)
    has_pending = pending_contact is not None

    # Get enrichment data
    result = crew.enrich_contact_data(name, company)

    # Format output
    status = result.get("status", "Unknown")
    full_name = result.get("full_name", name)

    # FIX 1: AUTO-INGEST - If there's a pending contact, update it with enrichment data
    if has_pending and status in ["Enriched", "Partial"]:
        _apply_enrichment_to_pending(memory, user_id, result)
        saved = False  # Not saved to DB yet, still in draft
        response = f"Running enrichment for **{full_name}**...\n\n"
    else:
        # No pending contact - save directly to Google Sheets
        save_result = crew.enrich_and_update_contact(name, company)
        result = save_result.get("enrichment", result)
        saved = save_result.get("updated_in_db", False)
        response = f"Running enrichment for **{full_name}**...\n\n"

    # Use clean formatted list instead of JSON
    response += format_enrichment_result(result)

    # Add status-specific outro
    if status == "Enriched":
        if has_pending:
            response += "\n\n_Enrichment data applied to contact draft. Say 'save' when ready._"
        elif saved:
            response += "\n\n_Contact enriched and saved to your network!_"
        else:
            response += "\n\n_Contact enriched successfully!_"
    elif status == "Partial":
        if has_pending:
            response += "\n\n_Partial data applied to contact draft. Say 'save' when ready._"
        elif saved:
            response += "\n\n_Partial data found and saved. Some fields could not be verified._"
        else:
            response += "\n\n_Partial data found. Some fields could not be verified._"
    else:
        response += "\n\n_Could not find sufficient data for enrichment._"

    # Clear the last saved contact after enrichment (if no pending)
    if not has_pending:
        memory.set_last_saved_contact(user_id, None, None)

    return response


def _apply_enrichment_to_pending(memory, user_id: str, enrichment: Dict[str, Any]):
    """
    FIX 1: AUTO-INGEST - Apply enrichment data to the pending contact in memory.
    This ensures enrichment data is written to the draft, not just displayed.
    """
    pending = memory.get_pending_contact(user_id)
    if not pending:
        return

    # Map enrichment fields to Contact fields
    field_mappings = {
        "contact_linkedin_url": "linkedin_url",
        "company_linkedin_url": "linkedin_link",
        "linkedin_summary": "linkedin_summary",
        "company": "company",
        "title": "title",
        "industry": "industry",
        "company_description": "company_description",
        "company_stage": "company_stage",
        "funding_raised": "funding_raised",
        "contact_type": "contact_type",
        "website": "website",
        "address": "address",
        "key_strengths": "key_strengths",
        "founder_score": "founder_score",
        "sector_fit": "sector_fit",
        "research_quality": "research_quality",
        "researched_date": "researched_date",
    }

    # Build updates dictionary with non-NA values
    updates = {}
    for enrich_field, contact_field in field_mappings.items():
        value = enrichment.get(enrich_field)
        if value and value != "NA":
            updates[contact_field] = value

    # Apply updates to pending contact
    if updates:
        memory.update_pending(user_id, updates)
        print(f"[ENRICHMENT] Applied {len(updates)} fields to pending contact: {list(updates.keys())}")


def _check_recall_last_saved(memory, user_id: str, msg_lower: str) -> Optional[str]:
    """
    FIX 3: RECALL LAST - Check if user is trying to add info to the last saved contact.
    If so, re-open it for editing.

    Detects patterns like:
    - "add his email"
    - "you forgot the linkedin"
    - "wait, add email@example.com"
    - "also add his phone"
    """
    # Get the last saved contact
    last_saved = memory.get_last_saved_contact(user_id)
    if not last_saved or not last_saved[0]:
        return None

    last_name = last_saved[0]
    last_company = last_saved[1]

    # Check if there's currently a pending contact (if yes, don't recall)
    if memory.get_pending_contact(user_id):
        return None

    # Patterns that indicate user wants to add to last saved contact
    # Each pattern requires a contact-info keyword to reduce false positives
    recall_patterns = [
        "add his ", "add her ", "add their ",
        "you forgot", "i forgot",
        "wait,", "also add", "also include",
        "update his ", "update her ",
        "his email", "her email", "his phone", "her phone",
        "his linkedin", "her linkedin",
        "add email", "add phone", "add linkedin"
    ]

    # Contact-info keywords that must be present for ambiguous patterns
    contact_info_keywords = [
        "email", "phone", "linkedin", "title", "company",
        "address", "number", "position", "role"
    ]

    # Check if message matches recall patterns
    is_recall = any(pattern in msg_lower for pattern in recall_patterns)

    # For "wait " alone (without comma), require a contact-info keyword
    if not is_recall and "wait " in msg_lower:
        is_recall = any(kw in msg_lower for kw in contact_info_keywords)

    if not is_recall:
        return None

    # Re-open the last saved contact for editing
    print(f"[RECALL] Re-opening last saved contact: {last_name}")

    # Find the contact in storage
    existing = find_contact_in_storage(last_name)
    if not existing:
        return None

    # Start editing this contact again
    memory.set_current_contact(user_id, existing)

    # Clear the last saved so we don't keep recalling
    memory.set_last_saved_contact(user_id, None, None)

    return f"Re-opening **{last_name}** for editing. What would you like to add?"


async def handle_deny(user_id: str, result: ConversationResult) -> str:
    """Handle denial responses (no, nope, wrong)."""
    memory = get_memory_service()
    state = memory.get_state(user_id)

    # If in confirming state, cancel the operation
    if state == ConversationState.CONFIRMING:
        memory.set_state(user_id, ConversationState.IDLE)
        return "No problem! What would you like to do instead?"

    # Otherwise, just acknowledge
    pending = memory.get_pending_contact(user_id)
    if pending:
        return f"Okay! Still working on **{pending.name}**. What would you like to change?"

    return "Alright! What can I help you with?"


async def handle_summarize(user_id: str, result: ConversationResult) -> str:
    """Handle requests to summarize search results."""
    memory = get_memory_service()
    current = memory.get_current_contact(user_id) or memory.get_pending_contact(user_id)

    # Check if we have recent search results
    search_data = _last_search_results.get(user_id)
    if not search_data:
        return (
            "I don't have any recent search results to summarize.\n\n"
            "Try searching first: _'search for [company name]'_"
        )

    # Use AI to summarize the search results
    try:
        from services.ai_service import get_ai_service
        ai = get_ai_service()

        # Build context for summarization
        search_results = search_data.get('results', [])
        query = search_data.get('query', 'Unknown')

        if not search_results:
            return "The search didn't return enough results to summarize."

        # Create summary prompt
        results_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in search_results[:5]
        ])

        summary_prompt = f"""Summarize the following search results about "{query}" in 2-3 concise sentences:

{results_text}

Provide a brief, informative summary suitable for a contact management system."""

        # Get summary from AI
        summary = ai.generate_response(summary_prompt)

        response = f"📊 **Summary for {query}:**\n\n{summary}"

        if current:
            response += f"\n\n_Want me to add this to **{current.name}**'s company description?_"

        return response

    except Exception as e:
        import logging
        logger = logging.getLogger('network_agent')
        logger.error(f"Summarize error: {e}")
        return "Sorry, I had trouble summarizing. Try again?"


async def handle_general_request(user_id: str, result: ConversationResult, message: str) -> str:
    """Handle complex general requests that need AI reasoning."""
    memory = get_memory_service()
    current = memory.get_current_contact(user_id) or memory.get_pending_contact(user_id)

    action = result.action_request or ""

    # Handle "add search results to description"
    if 'search' in action.lower() and 'description' in action.lower():
        search_data = _last_search_results.get(user_id)
        if not search_data or not current:
            return (
                "I need to have search results and an active contact to do that.\n\n"
                "Try: _'search for [company]'_ first, then ask me to add it."
            )

        # Build company description from search results
        results = search_data.get('results', [])
        if results:
            # Take first result's snippet as description
            description = results[0].get('snippet', '')
            if len(results) > 1:
                description += " " + results[1].get('snippet', '')

            # Clean up description
            description = description.strip()
            if len(description) > 500:
                description = description[:497] + "..."

            # Update the contact
            memory.update_pending(user_id, {'company_description': description})

            return (
                f"📄 Added company info to **{current.name}**'s profile!\n\n"
                f"_{description[:150]}..._\n\n"
                f"Say _'done'_ to save or keep adding info."
            )

        return "I don't have enough search data. Try searching first."

    # Handle other general requests - try to be helpful
    if current:
        return (
            f"I understand you want something specific, but I'm not quite sure what.\n\n"
            f"Currently working on **{current.name}**. You can:\n"
            f"• Add info directly: _'email is john@test.com'_\n"
            f"• Search: _'search for {current.company or 'their company'}'_\n"
            f"• Save: _'done'_"
        )

    return (
        "I want to help but I'm not sure exactly what you need.\n\n"
        "Try being more specific:\n"
        "• _'Add John Smith'_ to add a contact\n"
        "• _'Search for TechCorp'_ to look up info\n"
        "• _'Show me Sarah's info'_ to view a contact"
    )


def store_search_results(user_id: str, query: str, results: list):
    """Store search results for later summarization (with TTL cleanup)."""
    _store_search_results(user_id, {
        'query': query,
        'results': results,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    })


# ============================================================
# SMART INTENT DETECTION HELPERS
# ============================================================

def contains_contact_info(message: str) -> bool:
    """Check if message contains obvious contact information."""
    text = message.lower()

    # Email pattern
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message):
        return True

    # Phone pattern
    if re.search(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3,4}[-\s\.]?[0-9]{3,4}', message):
        return True

    # LinkedIn pattern
    if 'linkedin.com' in text or 'linkedin' in text:
        return True

    # Common job titles
    titles = ['ceo', 'cto', 'cfo', 'coo', 'vp', 'director', 'manager', 'engineer',
              'developer', 'founder', 'president', 'head of', 'lead']
    if any(title in text for title in titles):
        return True

    # Company indicators
    if ' at ' in text or ' works at ' in text or ' from ' in text:
        return True

    return False


def should_override_to_update(message: str, result: ConversationResult, state: ConversationState, user_id: str = None) -> bool:
    """
    Determine if we should override an ADD_CONTACT intent to UPDATE_CONTACT.
    This prevents the bot from starting a new contact when user is still talking about current one.

    Uses multiple signals:
    - Conversation state (must be COLLECTING)
    - Message timing (recent messages are likely updates)
    - Message length (short messages are likely updates)
    - Pronouns (referring to current contact)
    - Presence of contact info without "new person" signals
    """
    if state != ConversationState.COLLECTING:
        return False

    if result.intent != Intent.ADD_CONTACT:
        return False

    text_lower = message.lower()

    # Check for explicit "new contact" signals - if present, don't override
    new_person_signals = [
        'add new', 'new contact', 'another person', 'someone else',
        'different person', 'also add', 'another contact', 'new person'
    ]
    if any(signal in text_lower for signal in new_person_signals):
        return False

    # Check timing - messages within 30 seconds are very likely updates
    if user_id:
        memory = get_memory_service()
        if memory.is_continuation(user_id):
            # Recent message while collecting = almost certainly an update
            return True

    # Short to medium messages while collecting are almost always updates
    # But skip override if the message looks like "Add <Name>" (new contact)
    word_count = len(message.split())
    if word_count <= 15:
        # Check if message starts with "add" followed by a capitalized name
        words = message.split()
        if (len(words) >= 2 and words[0].lower() == "add" and
                words[1][0].isupper() and not contains_contact_info(message)):
            return False
        return True

    # Contains pronouns referring to current contact
    pronouns = ['he', 'she', 'they', 'his', 'her', 'their', 'him', "he's", "she's", "they're"]
    if any(f' {p} ' in f' {text_lower} ' or text_lower.startswith(f'{p} ') for p in pronouns):
        return True

    # Has contact info (email, phone, title, etc.) - likely adding details
    if contains_contact_info(message):
        return True

    # Long message with a name but no "new" signal - still likely an update
    # (User might be providing detailed info about the current contact)
    return False


# ============================================================
# MAIN CONVERSATION HANDLER
# ============================================================

async def process_message(user_id: str, message: str) -> str:
    """
    Main entry point for processing user messages.
    Uses the new agentic architecture with OpenAI function calling.
    """
    import logging
    logger = logging.getLogger('network_agent')

    # Sanitize input for security (XSS, injection, length limits)
    message = sanitize_input(message)
    if not message:
        return "I didn't catch that. Could you try again?"

    try:
        # Use the new agent-based architecture
        from services.agent import process_with_agent

        logger.info(f"[AGENT] Processing message from user {user_id}: {message[:50]}...")
        response = await process_with_agent(user_id, message)
        logger.info(f"[AGENT] Response: {response[:100]}...")

        return response

    except Exception as e:
        logger.warning(f"[AGENT] Agent failed, falling back to legacy system: {e}")

        # Fallback to old system if agent fails
        return await process_message_legacy(user_id, message)


async def process_message_legacy(user_id: str, message: str) -> str:
    """
    Legacy message processing using intent classification.
    Kept as fallback if the agent fails.
    """
    memory = get_memory_service()
    msg_lower = message.lower().strip()

    # FIX 3: RECALL LAST - Check if user is trying to add info to last saved contact
    recall_result = _check_recall_last_saved(memory, user_id, msg_lower)
    if recall_result:
        return recall_result
    if msg_lower.startswith("enrich") or msg_lower == "yes enrich" or msg_lower == "yes please enrich":
        # Check if there's a last saved contact to enrich
        last_saved = memory.get_last_saved_contact(user_id)
        if last_saved and last_saved[0]:
            return await handle_enrich_request(user_id, last_saved[0], last_saved[1])
        # Otherwise, let the enrichment handler parse the name
        elif msg_lower.startswith("enrich "):
            name_to_enrich = message[7:].strip()  # Remove "enrich "
            if name_to_enrich:
                return await handle_enrich_request(user_id, name_to_enrich, None)

    # Get context for AI (now includes state)
    current_contact, recent_names, state = memory.get_context_for_ai(user_id)

    # Analyze with AI (pass state for better context)
    result = await analyze_message(message, current_contact, recent_names, state)

    print(f"[AI-LEGACY] State: {state.value}, Intent: {result.intent.value}, Target: {result.target_contact}, Entities: {result.entities}")

    # Smart intent override: prevent accidental new contact creation while collecting
    if should_override_to_update(message, result, state, user_id):
        print(f"[OVERRIDE] Changing ADD_CONTACT to UPDATE_CONTACT (collecting mode)")
        result.intent = Intent.UPDATE_CONTACT
        if current_contact:
            result.target_contact = current_contact.name

    # Context switching: if user mentioned a DIFFERENT name, try to switch context
    if result.target_contact and current_contact:
        target_lower = result.target_contact.lower()
        current_lower = current_contact.name.lower()
        # Check if target is different from current
        if target_lower not in current_lower and current_lower not in target_lower:
            # User mentioned a different person - try to find them
            print(f"[CONTEXT] User mentioned different person: '{result.target_contact}' (current: '{current_contact.name}')")
            existing = find_contact_in_storage(result.target_contact)
            if existing:
                # Found the contact - switch to them
                print(f"[CONTEXT] Found existing contact, switching context to: {existing.name}")
                memory.set_current_contact(user_id, existing)
                # Adjust intent for the new context
                if result.intent == Intent.UPDATE_CONTACT:
                    # Add their pending info
                    if result.entities.get('linkedin') or result.entities.get('linkedin_url'):
                        memory.start_pending(user_id, existing.name)
                        memory.update_pending(user_id, result.entities)

    # Route to appropriate handler
    if result.intent == Intent.ADD_CONTACT:
        return await handle_add_contact(user_id, result)

    elif result.intent == Intent.UPDATE_CONTACT:
        return await handle_update_contact(user_id, result)

    elif result.intent == Intent.QUERY:
        return await handle_query(user_id, result)

    elif result.intent == Intent.VIEW:
        return await handle_view(user_id, result)

    elif result.intent == Intent.FINISH:
        return await handle_finish(user_id)

    elif result.intent == Intent.CANCEL:
        return await handle_cancel(user_id)

    elif result.intent == Intent.SEARCH:
        return await handle_search(user_id, result, message)

    elif result.intent == Intent.GREETING:
        return await handle_greeting(user_id)

    elif result.intent == Intent.THANKS:
        return await handle_thanks()

    elif result.intent == Intent.HELP:
        return await handle_help()

    elif result.intent == Intent.CONFIRM:
        return await handle_confirm(user_id, result)

    elif result.intent == Intent.DENY:
        return await handle_deny(user_id, result)

    elif result.intent == Intent.SUMMARIZE:
        return await handle_summarize(user_id, result)

    elif result.intent == Intent.GENERAL_REQUEST:
        return await handle_general_request(user_id, result, message)

    else:
        return await handle_unknown(user_id, message)
