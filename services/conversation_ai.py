"""
AI-Powered Conversation Service using Gemini with OpenAI fallback.
Handles intent classification, entity extraction, and contact resolution.
Enhanced with conversation state awareness for smarter multi-message flows.
"""

import json
import re
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from config import APIConfig, AIConfig
from data.schema import Contact
from utils.text_cleaner import clean_entities

# Initialize AI providers
_gemini_available = False
_openai_available = False
_openai_client = None

# Try to initialize Gemini
try:
    import google.generativeai as genai
    if APIConfig.GEMINI_API_KEY:
        genai.configure(api_key=APIConfig.GEMINI_API_KEY)
        _gemini_available = True
except Exception as e:
    print(f"Gemini initialization failed: {e}")

# Try to initialize OpenAI
try:
    from openai import OpenAI
    if APIConfig.OPENAI_API_KEY:
        _openai_client = OpenAI(api_key=APIConfig.OPENAI_API_KEY)
        _openai_available = True
except Exception as e:
    print(f"OpenAI initialization failed: {e}")


# Import ConversationState for type hints
try:
    from services.contact_memory import ConversationState
except ImportError:
    # Fallback if circular import
    class ConversationState(Enum):
        IDLE = "idle"
        COLLECTING = "collecting"
        CONFIRMING = "confirming"


class Intent(Enum):
    """Possible user intents."""
    ADD_CONTACT = "add_contact"
    UPDATE_CONTACT = "update_contact"
    QUERY = "query"
    VIEW = "view"
    FINISH = "finish"
    CANCEL = "cancel"  # Cancel current contact without saving
    SEARCH = "search"  # User wants to search/enrich with web data
    SUMMARIZE = "summarize"  # User wants AI to summarize search results
    CONFIRM = "confirm"  # User confirms something (yes, ok, sure)
    DENY = "deny"  # User denies something (no, nope)
    GENERAL_REQUEST = "general_request"  # ChatGPT-like general request
    GREETING = "greeting"
    THANKS = "thanks"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ConversationResult:
    """Result from AI analysis of a message."""
    intent: Intent
    target_contact: Optional[str] = None  # Who the user is referring to
    entities: Dict[str, Any] = field(default_factory=dict)  # Extracted contact fields
    query_field: Optional[str] = None  # For QUERY intent, what field they're asking about
    action_request: Optional[str] = None  # For GENERAL_REQUEST intent, what action to take
    confidence: float = 1.0
    raw_response: str = ""


# The prompt template - ChatGPT-like natural language understanding
ANALYSIS_PROMPT = """You are an Elite Networking Assistant helping a user manage their professional network contacts.

===== PERSONA =====
Voice: Sharp, Witty, Professional, Warm.
Rules:
- Never start with "I have successfully..." - it's boring.
- Use emojis sparingly (1 per message max).
- Fix user typos silently. Don't nag.
- Own mistakes with humor (e.g., "My wires got crossed").
- Celebrate big wins (CEO, Investor) with "Boom!" or "Nice catch! or charming, you are!"
- Keep responses under 2 sentences unless summarising complex data.

===== CORE OBJECTIVE =====
Manage and enrich contact information with high accuracy, context awareness, and zero duplication.

===== MEMORY RULES =====
- SHORT TERM MEMORY: Always track the 'active_contact_id' of the person currently being discussed.
- PRONOUN RESOLUTION: If the user says 'his', 'her', 'their', 'the company', or provides an attribute (email, phone) without a name, APPLY IT TO THE ACTIVE CONTACT. Do not create a new contact.
- HARD RESET ON SAVE: When user says 'Save', 'Done', 'Finish', or 'That's all' - the active_contact_id MUST be cleared. Previous contact becomes LOCKED.
- CONTEXT LOCK: After a contact is saved, it enters LOCKED state. Subsequent attributes CANNOT be applied to a locked contact without explicit 'Update [name]' command.

===== AMBIGUITY HANDLING =====
- ENTITY DISAMBIGUATION: If a company name is ambiguous (e.g., 'Synapse', 'Apple', 'Delta'), use context clues (location, industry) to infer the correct entity. If unsure, the response should ASK the user or suggest triggering a search.
- SEARCH FIRST POLICY: Before responding with 'I don't know', use available context to find missing information (LinkedIn, Company Description, Funding).
- PRONOUN GENDER MISMATCH: If user says 'his' but current contact appears female (or vice versa), ASK for clarification. Do NOT fall back to previous locked contacts.

===== STATE MANAGEMENT =====
- CORRECTION OVERRIDE: If the user corrects a field (e.g., 'No, phone is 012...'), the previous value should be overwritten immediately.
- MULTI ENTITY DETECTION: If the user mentions multiple people in one message (e.g., 'Ahmed and Seif from Thndr'), parse and flag that distinct profiles should be created for each.
- POST-SAVE BEHAVIOR: After save/done/finish: 1) Clear active contact, 2) Set state to IDLE, 3) LOCK previous contact.

===== CONTEXT SWITCHING (CRITICAL) =====
- NEW CONTACT AFTER SAVE: When user says 'Add [Name]' after a save, this is a COMPLETELY NEW context. The previous contact is LOCKED and IMMUTABLE.
- ATTRIBUTE WITHOUT CONTEXT: If user provides attribute but NO active contact exists, ASK which contact. Do NOT assume previous contact.
- NEVER MODIFY LOCKED: A saved/locked contact can ONLY be modified if user explicitly says 'Update [name]' or 'Edit [name]'.

You understand NATURAL LANGUAGE and can interpret what the user wants even if they don't use exact commands.

CONTEXT:
- Conversation state: {state}
- Current contact being discussed (ACTIVE CONTACT): {current_contact}
- Recent contacts: {recent_contacts}
- Last search results available: {has_search_results}

USER MESSAGE:
"{message}"

TASK: Analyze this message and respond with JSON containing:

1. "intent": One of:
   - "add_contact": User wants to add a NEW person
   - "update_contact": User is providing/adding info about current or named contact
   - "query": User is ASKING about a contact's info
   - "view": User wants to SEE a contact's full info (e.g., "what do you have on X", "show me X")
   - "finish": User is done ("done", "save", "that's all", "yes" when confirming save)
   - "cancel": User wants to discard ("cancel", "no", "nevermind")
   - "search": User wants to search the web for info
   - "summarize": User wants AI to summarize/analyze search results
   - "confirm": User is confirming something ("yes", "ok", "sure", "correct", "that's right")
   - "deny": User is denying/rejecting ("no", "nope", "wrong", "not that one")
   - "general_request": Complex request that needs AI reasoning (add search results to profile, etc.)
   - "greeting": Hello, hi, good morning, etc.
   - "thanks": Thank you messages
   - "help": Asking what the bot can do
   - "unknown": Truly cannot understand

2. "target_contact": Name of person being discussed, or null

3. "entities": CLEAN extracted values (no filler words):
   - "name": Full name
   - "title": Job title (clean - just "CEO" not "He's the CEO")
   - "company": Company name (clean - just "Google" not "at Google")
   - "email": Email address only
   - "phone": Phone number only
   - "location": City/address (clean - just "New Cairo, Egypt" not "based in...")
   - "industry": Industry sector
   - "linkedin": LinkedIn URL
   - "contact_type": One of: "founder", "investor", "enabler", "professional" (if mentioned)
   - "company_description": Company description/info
   - "notes": Other relevant info

4. "query_field": For query intent, what field? (email, phone, title, all, etc.)

5. "action_request": For general_request intent, describe what user wants (e.g., "add_search_to_description", "summarize_and_save")

===== UNDERSTANDING NATURAL LANGUAGE =====

Be SMART about understanding what users mean:

| User says                                          | Intent           | Explanation                    |
|----------------------------------------------------|------------------|--------------------------------|
| "add him as type enabler"                          | update_contact   | contact_type: "enabler"        |
| "he's an enabler"                                  | update_contact   | contact_type: "enabler"        |
| "mark her as founder"                              | update_contact   | contact_type: "founder"        |
| "she's an investor"                                | update_contact   | contact_type: "investor"       |
| "for now add that the company is in Cairo"         | update_contact   | location: "Cairo"              |
| "add that info to the company description"         | general_request  | action: add_search_to_desc     |
| "company description add what you searched"        | general_request  | action: add_search_to_desc     |
| "summarize what you found"                         | summarize        | wants summary of search        |
| "what do you have on John"                         | view             | wants to see John's info       |
| "show me ibz"                                      | view             | target: "ibz"                  |
| "give me info on Sarah"                            | view             | target: "Sarah"                |
| "yes"                                              | confirm          | confirming previous question   |
| "ok"                                               | confirm          | confirming                     |
| "no"                                               | deny             | denying/rejecting              |
| "search what this company does"                    | search           | search for company info        |
| "who is the CEO at widebot? search"                | search           | search for CEO info            |
| "it's a company based in 5th settlement..."        | update_contact   | location info                  |

===== CONTACT TYPE RECOGNITION =====

When user mentions these words, extract contact_type:
- "enabler", "type enabler", "as enabler" → contact_type: "enabler"
- "founder", "type founder", "is a founder" → contact_type: "founder"
- "investor", "type investor", "VC", "angel" → contact_type: "investor"
- "professional" → contact_type: "professional"

===== STATE-AWARE RULES =====

When state is "collecting" (actively building a contact):
- Any info provided → "update_contact" for current contact
- "done", "save", "finish" → "finish"
- "yes" after save prompt → "finish"
- Names of OTHER people → context switch (set target_contact)

When state is "idle":
- Names with info → "add_contact"
- Requests for existing contacts → "view"

When state is "confirming":
- "yes", "ok", "correct" → "confirm"
- "no", "wrong", "different" → "deny"

===== EXAMPLES =====

PRONOUN RESOLUTION (apply to active contact):
State: collecting (current: "Ahmed Abbas, CRO at SAIB"), Message: "add his email as aabbas@saib.com"
{{"intent": "update_contact", "target_contact": "Ahmed Abbas", "entities": {{"email": "aabbas@saib.com"}}, "query_field": null, "action_request": null}}

State: collecting (current: "Sarah, Apex Ventures"), Message: "her phone is 0123456789"
{{"intent": "update_contact", "target_contact": "Sarah", "entities": {{"phone": "0123456789"}}, "query_field": null, "action_request": null}}

ENTITY DISAMBIGUATION (ask when ambiguous):
State: idle, Message: "Add Mohamed Abaza as head of growth at Synapse Analytics"
{{"intent": "add_contact", "target_contact": "Mohamed Abaza", "entities": {{"name": "Mohamed Abaza", "title": "Head of Growth", "company": "Synapse Analytics"}}, "query_field": null, "action_request": "disambiguate_company", "disambiguation_note": "Synapse Analytics could be the AI company in Egypt or Microsoft product"}}

CORRECTION OVERRIDE (overwrite previous values):
State: collecting (current: "Ziad"), Message: "sorry phone is 0112"
{{"intent": "update_contact", "target_contact": "Ziad", "entities": {{"phone": "0112"}}, "query_field": null, "action_request": "correction_override"}}

State: collecting (current: "Hoda, Founder at Breadfast"), Message: "wait, she is not the founder, she is Head of People"
{{"intent": "update_contact", "target_contact": "Hoda", "entities": {{"title": "Head of People"}}, "query_field": null, "action_request": "correction_override"}}

MULTI-ENTITY DETECTION:
State: idle, Message: "Add Ahmed and Seif from Thndr"
{{"intent": "add_contact", "target_contact": null, "entities": {{"name": "Ahmed", "company": "Thndr"}}, "query_field": null, "action_request": "multi_entity", "additional_entities": [{{"name": "Seif", "company": "Thndr"}}]}}

CONTACT TYPE EXTRACTION:
State: collecting (current: "Ibz"), Message: "add him as type enabler"
{{"intent": "update_contact", "target_contact": "Ibz", "entities": {{"contact_type": "enabler"}}, "query_field": null, "action_request": null}}

State: collecting (current: "Khaled, Algebra Ventures"), Message: "Yes, he is a Partner"
{{"intent": "update_contact", "target_contact": "Khaled", "entities": {{"title": "Partner", "contact_type": "investor"}}, "query_field": null, "action_request": null}}

LOCATION UPDATES:
State: collecting (current: "Ibz"), Message: "for now add that this company is based in 5th settlement in new cairo, egypt"
{{"intent": "update_contact", "target_contact": "Ibz", "entities": {{"location": "5th Settlement, New Cairo, Egypt"}}, "query_field": null, "action_request": null}}

VIEW/QUERY:
State: idle, Message: "what do you have on ibz"
{{"intent": "view", "target_contact": "ibz", "entities": {{}}, "query_field": "all", "action_request": null}}

SEARCH TRIGGERS:
State: collecting (current: "Farook Hassan, CEO at Fimple"), Message: "go ahead"
{{"intent": "search", "target_contact": "Farook Hassan", "entities": {{}}, "query_field": null, "action_request": "search_company"}}

GENERAL REQUESTS:
State: collecting, Message: "company description add what you searched"
{{"intent": "general_request", "target_contact": null, "entities": {{}}, "query_field": null, "action_request": "add_search_to_description"}}

CONFIRMATIONS:
State: confirming, Message: "yes"
{{"intent": "confirm", "target_contact": null, "entities": {{}}, "query_field": null, "action_request": null}}

State: collecting, Message: "summarize what you found about the company"
{{"intent": "summarize", "target_contact": null, "entities": {{}}, "query_field": null, "action_request": "summarize_search"}}

===== CONTEXT SWITCHING (CRITICAL - PREVENTS DATA CORRUPTION) =====

SAVE TRIGGERS HARD RESET:
State: collecting (current: "Ahmed Amr"), Message: "Save"
{{"intent": "finish", "target_contact": "Ahmed Amr", "entities": {{}}, "query_field": null, "action_request": "hard_reset", "context_note": "Contact saved. Context CLEARED. Ahmed Amr is now LOCKED."}}

NEW CONTACT AFTER SAVE (previous contact is LOCKED):
State: idle (previous was "Ahmed Amr" - now LOCKED), Message: "Add Yousra Abdelatif"
{{"intent": "add_contact", "target_contact": "Yousra Abdelatif", "entities": {{"name": "Yousra Abdelatif"}}, "query_field": null, "action_request": "new_context", "context_note": "NEW contact. Ahmed Amr is LOCKED and cannot be modified."}}

ATTRIBUTES APPLY TO NEW CONTACT ONLY:
State: collecting (current: "Yousra Abdelatif", LOCKED: "Ahmed Amr"), Message: "Her type is enabler"
{{"intent": "update_contact", "target_contact": "Yousra Abdelatif", "entities": {{"contact_type": "enabler"}}, "query_field": null, "action_request": null, "context_note": "Applies to Yousra ONLY. Ahmed is LOCKED."}}

PRONOUN MISMATCH WARNING:
State: collecting (current: "Sarah"), Message: "His email is john@test.com"
{{"intent": "update_contact", "target_contact": "Sarah", "entities": {{}}, "query_field": null, "action_request": "pronoun_mismatch", "context_note": "User said 'his' but current contact is Sarah. ASK for clarification. Do NOT fall back to previous contacts."}}

NO ACTIVE CONTACT - ASK USER:
State: idle (no active contact), Message: "Type is investor"
{{"intent": "unknown", "target_contact": null, "entities": {{"contact_type": "investor"}}, "query_field": null, "action_request": "no_active_contact", "context_note": "No active contact. Previous contact is LOCKED. Ask user which contact to update."}}

EXPLICIT UNLOCK REQUIRED:
State: idle (LOCKED: "Mohamed"), Message: "Update Mohamed's email to mo@test.com"
{{"intent": "update_contact", "target_contact": "Mohamed", "entities": {{"email": "mo@test.com"}}, "query_field": null, "action_request": "explicit_unlock", "context_note": "User explicitly said 'Update Mohamed' - unlock allowed."}}

===== DATA INTEGRITY PROTOCOLS =====

JOB CHANGE DETECTION (move old to past_experience):
State: collecting (current: "Omar - CEO at Vodafone"), Message: "Actually, he moved. He is at Etisalat now."
{{"intent": "update_contact", "target_contact": "Omar", "entities": {{"company": "Etisalat", "past_experience": "Vodafone"}}, "query_field": null, "action_request": "job_change", "context_note": "Moving Vodafone to past_experience. Current company is now Etisalat."}}

FIELD DELETION (set to null):
State: collecting (current: "Nadia - email: nadia@fawry.com"), Message: "No, that's wrong. Delete it."
{{"intent": "update_contact", "target_contact": "Nadia", "entities": {{"email": null}}, "query_field": null, "action_request": "field_deletion", "context_note": "User wants to delete the email field. Set to null."}}

HALLUCINATION GUARD (never invent data):
State: collecting (current: "Tarek"), Message: "What's his email?"
{{"intent": "query", "target_contact": "Tarek", "entities": {{}}, "query_field": "email", "action_request": null, "context_note": "NEVER invent email. If unknown, respond 'I don't have Tarek's email on file. Would you like to provide it?'"}}

STALE SESSION HANDLING (auto-clear after long gap):
State: collecting but last_message_time > 2 hours ago, Message: "His email is hany@gmail.com"
{{"intent": "unknown", "target_contact": null, "entities": {{"email": "hany@gmail.com"}}, "query_field": null, "action_request": "stale_session", "context_note": "Session is stale (>2 hours). Ask user to specify which contact."}}

NAME SPELLING CORRECTION:
State: collecting (current: "Tarek"), Message: "Actually, his name is spelled Tariq, not Tarek."
{{"intent": "update_contact", "target_contact": "Tariq", "entities": {{"name": "Tariq"}}, "query_field": null, "action_request": "name_correction", "context_note": "Correcting name spelling from Tarek to Tariq."}}

AUTO-SAVE ON CONTEXT SWITCH:
State: collecting (current: "Mona"), Message: "Done. Now add her colleague Ramy from the same company."
{{"intent": "add_contact", "target_contact": "Ramy", "entities": {{"name": "Ramy"}}, "query_field": null, "action_request": "auto_save_and_switch", "context_note": "AUTO-SAVE Mona. Start NEW session for Ramy. Copy company if 'same company' mentioned."}}

DISCARD/START OVER:
State: collecting (current: "Youssef"), Message: "No wait, delete everything. Start over."
{{"intent": "cancel", "target_contact": "Youssef", "entities": {{}}, "query_field": null, "action_request": "discard_contact", "context_note": "Discard all data for Youssef. Clear session. Ready for new input."}}

NOTES/QUALITATIVE INFO:
State: collecting (current: "Layla"), Message: "She is amazing, super helpful, always responds quickly."
{{"intent": "update_contact", "target_contact": "Layla", "entities": {{"notes": "Amazing, super helpful, always responds quickly"}}, "query_field": null, "action_request": null}}

Respond with ONLY valid JSON, no markdown or explanation.
"""


def _parse_ai_response(response_text: str) -> Dict[str, Any]:
    """Parse the AI response, handling potential JSON issues."""
    # Clean up the response
    text = response_text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}


async def analyze_message(
    message: str,
    current_contact: Optional[Contact] = None,
    recent_contacts: Optional[List[str]] = None,
    state: Optional[ConversationState] = None
) -> ConversationResult:
    """
    Use Gemini to analyze a user message and extract intent + entities.

    Args:
        message: The user's message
        current_contact: The contact currently being discussed (if any)
        recent_contacts: List of recently discussed contact names
        state: Current conversation state (IDLE, COLLECTING, CONFIRMING)

    Returns:
        ConversationResult with intent, target contact, and extracted entities
    """
    if recent_contacts is None:
        recent_contacts = []

    # Default state to IDLE if not provided
    if state is None:
        state = ConversationState.IDLE

    # Build context strings
    current_contact_str = "None"
    if current_contact:
        parts = [current_contact.name or "Unknown"]
        if current_contact.title:
            parts.append(f"({current_contact.title})")
        if current_contact.company:
            parts.append(f"at {current_contact.company}")
        if current_contact.email:
            parts.append(f"[{current_contact.email}]")
        current_contact_str = " ".join(parts)

    recent_contacts_str = ", ".join(recent_contacts) if recent_contacts else "None"
    state_str = state.value if state else "idle"

    # Build the prompt
    prompt = ANALYSIS_PROMPT.format(
        state=state_str,
        current_contact=current_contact_str,
        recent_contacts=recent_contacts_str,
        has_search_results="no",  # Search results are tracked separately in agent_tools
        message=message
    )
    
    raw_text = None
    parsed = None

    # Try Gemini first
    if _gemini_available:
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
            raw_text = response.text
            parsed = _parse_ai_response(raw_text)
            if parsed:
                print(f"[AI] Gemini success")
        except Exception as e:
            print(f"[AI] Gemini error: {e}")

    # Try OpenAI as fallback
    if not parsed and _openai_available and _openai_client:
        try:
            print("[AI] Trying OpenAI fallback...")
            response = _openai_client.chat.completions.create(
                model=AIConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON-only assistant that analyzes messages for a contact management system. Always respond with valid JSON only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            raw_text = response.choices[0].message.content
            parsed = _parse_ai_response(raw_text)
            if parsed:
                print(f"[AI] OpenAI success")
        except Exception as e:
            print(f"[AI] OpenAI error: {e}")

    # If no AI worked, use fallback
    if not parsed:
        print("[AI] Using regex fallback")
        return _fallback_analysis(message, current_contact, state)

    # Map intent string to enum
    intent_str = parsed.get("intent", "unknown").lower()
    intent_map = {
        "add_contact": Intent.ADD_CONTACT,
        "update_contact": Intent.UPDATE_CONTACT,
        "query": Intent.QUERY,
        "view": Intent.VIEW,
        "finish": Intent.FINISH,
        "cancel": Intent.CANCEL,
        "search": Intent.SEARCH,
        "enrich": Intent.SEARCH,  # alias
        "summarize": Intent.SUMMARIZE,
        "confirm": Intent.CONFIRM,
        "deny": Intent.DENY,
        "general_request": Intent.GENERAL_REQUEST,
        "greeting": Intent.GREETING,
        "thanks": Intent.THANKS,
        "help": Intent.HELP,
        "unknown": Intent.UNKNOWN,
    }
    intent = intent_map.get(intent_str, Intent.UNKNOWN)

    # Keyword-based fallbacks for common patterns
    msg_lower = message.lower().strip()

    # Search triggers
    if intent == Intent.UNKNOWN:
        search_triggers = ['search for', 'look up', 'find info', 'find out about', 'what can you find', 'enrich', 'research', 'search what']
        if any(trigger in msg_lower for trigger in search_triggers):
            intent = Intent.SEARCH

    # View triggers - "what do you have on X", "show me X"
    if intent == Intent.UNKNOWN:
        view_triggers = ['what do you have on', 'show me', 'give me info on', 'tell me about']
        if any(trigger in msg_lower for trigger in view_triggers):
            intent = Intent.VIEW

    # Confirm triggers
    if intent == Intent.UNKNOWN and msg_lower in ['yes', 'ok', 'okay', 'sure', 'correct', 'yep', 'yeah', 'yea']:
        intent = Intent.CONFIRM

    # Deny triggers
    if intent == Intent.UNKNOWN and msg_lower in ['no', 'nope', 'wrong', 'nah', 'not that']:
        intent = Intent.DENY

    # Extract target contact
    target_contact = parsed.get("target_contact")
    if target_contact and current_contact and not target_contact.strip():
        target_contact = current_contact.name

    # Extract entities
    entities = parsed.get("entities", {})
    # Clean up entities - remove None/empty values
    entities = {k: v for k, v in entities.items() if v}
    # Apply text cleaning to all entity values
    entities = clean_entities(entities)

    # Get query field and action request
    query_field = parsed.get("query_field")
    action_request = parsed.get("action_request")

    return ConversationResult(
        intent=intent,
        target_contact=target_contact,
        entities=entities,
        query_field=query_field,
        action_request=action_request,
        raw_response=raw_text or ""
    )


def _fallback_analysis(message: str, current_contact: Optional[Contact], state: Optional[ConversationState] = None) -> ConversationResult:
    """Basic fallback if AI fails. Enhanced with state awareness."""
    text_lower = message.lower().strip()
    is_collecting = state == ConversationState.COLLECTING if state else (current_contact is not None)

    # Check for cancel signals
    cancel_words = ['cancel', 'nevermind', 'never mind', 'forget it', 'discard', 'abort']
    if any(text_lower.startswith(w) or text_lower == w for w in cancel_words):
        return ConversationResult(intent=Intent.CANCEL)

    # Check for done signals
    done_words = ['done', 'finished', 'complete', "that's all", 'thats all', 'save', 'save it']
    if any(text_lower.startswith(w) or text_lower == w for w in done_words):
        return ConversationResult(intent=Intent.FINISH)

    # Check for greetings
    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon']
    if any(text_lower.startswith(g) for g in greetings):
        return ConversationResult(intent=Intent.GREETING)

    # Check for thanks
    if 'thank' in text_lower:
        return ConversationResult(intent=Intent.THANKS)

    # Check for help
    if text_lower in ['help', '/help', 'what can you do']:
        return ConversationResult(intent=Intent.HELP)

    # Check for add contact (only if not already collecting)
    if text_lower.startswith('add ') and not is_collecting:
        name_match = re.search(r'add\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', message, re.IGNORECASE)
        if name_match:
            return ConversationResult(
                intent=Intent.ADD_CONTACT,
                entities={'name': name_match.group(1)}
            )

    # If collecting, check for common contact info patterns
    if is_collecting:
        entities = {}

        # Check for email
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message)
        if email_match:
            entities['email'] = email_match.group()

        # Check for phone
        phone_match = re.search(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', message)
        if phone_match:
            entities['phone'] = phone_match.group()

        # Check for LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', message, re.IGNORECASE)
        if linkedin_match:
            entities['linkedin'] = linkedin_match.group()

        # Check for common titles
        title_patterns = ['ceo', 'cto', 'cfo', 'coo', 'vp', 'director', 'manager', 'engineer', 'developer', 'founder', 'president']
        for title in title_patterns:
            if title in text_lower:
                # Extract the full title phrase
                title_match = re.search(rf'\b({title}(?:\s+of\s+\w+)?)\b', text_lower, re.IGNORECASE)
                if title_match:
                    entities['title'] = title_match.group(1).title()
                    break

        if entities:
            # Clean extracted entities
            entities = clean_entities(entities)
            return ConversationResult(
                intent=Intent.UPDATE_CONTACT,
                target_contact=current_contact.name if current_contact else None,
                entities=entities
            )

    # Check for email even if not collecting
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message)
    if email_match:
        return ConversationResult(
            intent=Intent.UPDATE_CONTACT,
            target_contact=current_contact.name if current_contact else None,
            entities={'email': email_match.group()}
        )

    # Default to unknown
    return ConversationResult(intent=Intent.UNKNOWN)


# Synchronous wrapper for non-async contexts
def analyze_message_sync(
    message: str,
    current_contact: Optional[Contact] = None,
    recent_contacts: Optional[List[str]] = None,
    state: Optional[ConversationState] = None
) -> ConversationResult:
    """Synchronous version of analyze_message."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop for sync context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    analyze_message(message, current_contact, recent_contacts, state)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                analyze_message(message, current_contact, recent_contacts, state)
            )
    except RuntimeError:
        return asyncio.run(analyze_message(message, current_contact, recent_contacts, state))
