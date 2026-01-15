# Plan: Making the Telegram Agent Smarter and More Natural

## Current Problems Identified

After analyzing the codebase, here are the root causes of the "dumb" behavior:

### Problem 1: Immediate Message Processing
**Location:** `handlers/input_handlers.py:215-226`

Each message is processed immediately and independently:
```python
text = update.message.text.strip()
response = await process_message(user_id, text)
```

There's no mechanism to:
- Wait for the user to finish providing all information
- Combine multiple sequential messages about the same contact
- Understand that a multi-message flow is happening

### Problem 2: Eager Contact Creation & Saving
**Location:** `handlers/conversation_engine.py:155-210`

When AI detects "ADD_CONTACT" intent, the bot immediately:
1. Creates a new Contact object
2. Saves it to Google Sheets
3. Then asks "What else?"

This causes issues because:
- User sends: "Add John Smith" → Contact saved immediately
- User sends: "He's the CEO" → AI might misclassify as new contact or fail to update

### Problem 3: Weak Intent Classification
**Location:** `services/conversation_ai.py:46-100`

The Gemini prompt doesn't strongly emphasize:
- That UPDATE_CONTACT should be used when there's a current_contact
- How to handle follow-up messages in a conversation flow
- That short messages like "CEO" or "john@email.com" are additions, not new contacts

### Problem 4: No Conversation State Machine
The bot lacks proper conversation states:
- `IDLE` → No active contact
- `COLLECTING` → Currently gathering info about a contact
- `CONFIRMING` → Waiting for user to confirm before saving
- `DONE` → Ready for next contact

---

## Improvement Plan

### Phase 1: Add Conversation State Management

**File:** `services/contact_memory.py`

Add a conversation state enum and track it per user:

```python
class ConversationState(Enum):
    IDLE = "idle"              # No active contact, waiting for new input
    COLLECTING = "collecting"   # Actively gathering info about a contact
    CONFIRMING = "confirming"   # Showing summary, waiting for confirmation
```

**Changes needed:**
1. Add `state: ConversationState` to `UserMemory` dataclass
2. Add `pending_contact: Contact` for unsaved contact being built
3. Add `last_message_time: datetime` to detect conversation continuity
4. Add methods: `start_collecting()`, `is_still_collecting()`, `confirm_save()`, `cancel()`

---

### Phase 2: Implement Message Buffering

**File:** `handlers/input_handlers.py`

Add a short delay/buffer mechanism:

```python
# Add to UserMemory
message_buffer: List[str] = []
last_message_time: datetime = None
BUFFER_TIMEOUT_SECONDS = 3  # Wait 3 seconds for more input
```

**Logic:**
1. When user sends a message, add to buffer
2. Wait ~2-3 seconds before processing
3. If another message arrives, reset timer and add to buffer
4. When timer expires, combine buffer and process as one message
5. OR: Process immediately but don't save - accumulate in pending_contact

**Simpler alternative (recommended):**
Don't delay, but change the saving behavior:
- Don't save immediately
- Accumulate all info in `pending_contact`
- Only save when user says "done" or "save"
- Or auto-save after 5 minutes of inactivity

---

### Phase 3: Improve AI Intent Classification

**File:** `services/conversation_ai.py`

Rewrite the prompt with stronger context awareness:

```python
ANALYSIS_PROMPT = """You are analyzing a message from a user managing contacts.

CRITICAL CONTEXT:
- Current contact being edited: {current_contact}
- Conversation state: {state}  # NEW: IDLE, COLLECTING, or CONFIRMING
- Recent contacts: {recent_contacts}

USER MESSAGE: "{message}"

INTENT CLASSIFICATION RULES (FOLLOW STRICTLY):

1. If state is COLLECTING or there IS a current contact:
   - Short messages (under 10 words) with contact info → UPDATE_CONTACT
   - Pronouns (he/she/they) → UPDATE_CONTACT for current contact
   - Email, phone, title, company without "add new" → UPDATE_CONTACT
   - "done", "save", "that's all" → FINISH
   - ONLY use ADD_CONTACT if user EXPLICITLY says "add NEW contact" or "add [different name]"

2. If state is IDLE or no current contact:
   - Any message with a person's name → ADD_CONTACT
   - General info without context → ask for clarification (UNKNOWN)

3. Multi-line handling:
   - If message contains multiple lines, extract ALL entities from ALL lines
   - Each line may contain different fields (name, email, title, etc.)

...
"""
```

**Key changes:**
- Add `state` parameter to `analyze_message()`
- Stronger rules for UPDATE vs ADD
- Better multi-line parsing instructions

---

### Phase 4: Refactor Conversation Engine Flow

**File:** `handlers/conversation_engine.py`

Change `handle_add_contact()` to NOT save immediately:

```python
async def handle_add_contact(user_id: str, result: ConversationResult) -> str:
    memory = get_memory_service()

    # Check if we're already collecting for someone
    current = memory.get_current_contact(user_id)
    if current:
        # User might be confused - treat as update instead
        return await handle_update_contact(user_id, result)

    # Create contact but DON'T save yet
    contact = Contact.from_dict({...})

    # Store as PENDING (not saved to sheets yet)
    memory.set_pending_contact(user_id, contact)
    memory.set_state(user_id, ConversationState.COLLECTING)

    response = f"Got it! Starting a new contact for **{name}**.\n\n"
    response += "Tell me more about them - title, company, email, phone, etc.\n"
    response += "_Say 'done' when finished, or 'cancel' to discard._"

    return response
```

Change `handle_finish()` to do the actual save:

```python
async def handle_finish(user_id: str) -> str:
    memory = get_memory_service()
    pending = memory.get_pending_contact(user_id)

    if not pending:
        return "Nothing to save!"

    # NOW we save to storage
    success, storage = save_contact_to_storage(pending)

    if success:
        memory.clear_pending(user_id)
        memory.set_state(user_id, ConversationState.IDLE)
        return f"Saved **{pending.name}** to your network!"
    else:
        return "Failed to save. Try again?"
```

---

### Phase 5: Handle Multi-line Messages

**File:** `services/conversation_ai.py`

The AI should already handle multi-line input, but improve the prompt:

```python
# Add to prompt:
"""
MULTI-LINE HANDLING:
If the message contains multiple lines, parse ALL lines together as info about ONE person.
Example:
"John Smith
CEO at TechCorp
john@techcorp.com
+1 555 123 4567"

→ This is ONE contact with name, title, company, email, and phone.
→ Return intent: add_contact (or update_contact if continuing)
→ Return all entities: {name: "John Smith", title: "CEO", company: "TechCorp", ...}
"""
```

---

### Phase 6: Add Smart Continuity Detection

**File:** `handlers/conversation_engine.py`

Add logic to detect conversation continuity:

```python
async def process_message(user_id: str, message: str) -> str:
    memory = get_memory_service()

    # Get current state
    state = memory.get_state(user_id)
    current = memory.get_current_contact(user_id)

    # Check for continuation signals
    is_short_message = len(message.split()) <= 5
    has_pronoun = any(p in message.lower() for p in ['he', 'she', 'they', 'his', 'her', 'their'])
    has_contact_info = contains_contact_info(message)  # email, phone, etc.

    # Force UPDATE intent if we're in collecting mode and this looks like more info
    if state == ConversationState.COLLECTING:
        if is_short_message and (has_contact_info or has_pronoun):
            # Override AI - this is definitely an update
            result = await analyze_message(message, current, recent_names)
            if result.intent == Intent.ADD_CONTACT:
                # AI got confused - force to UPDATE
                result.intent = Intent.UPDATE_CONTACT
                result.target_contact = current.name

    # Continue with normal processing...
```

---

### Phase 7: Add Confirmation Flow (Optional Enhancement)

Before saving, show a summary and ask for confirmation:

```python
async def handle_pre_save_confirmation(user_id: str) -> str:
    memory = get_memory_service()
    pending = memory.get_pending_contact(user_id)

    memory.set_state(user_id, ConversationState.CONFIRMING)

    response = "Here's what I've got:\n\n"
    response += format_contact_card(pending)
    response += "\n\n**Save this?** (yes/no/add more)"

    return response
```

---

### Phase 8: Add Smart Auto-Save

If user goes silent or starts talking about something else:

```python
# In UserMemory
AUTO_SAVE_TIMEOUT_MINUTES = 5

async def check_auto_save(user_id: str):
    memory = get_memory_service()
    user_mem = memory.get_memory(user_id)

    if user_mem.state == ConversationState.COLLECTING:
        if datetime.now() - user_mem.last_activity > timedelta(minutes=5):
            # Auto-save the pending contact
            await handle_finish(user_id)
            # Notify user on next interaction
            user_mem.auto_saved = True
```

---

## Implementation Priority

1. **High Priority (Core fixes):**
   - Phase 1: Conversation state management
   - Phase 3: Improve AI prompt for better intent detection
   - Phase 4: Deferred saving (pending contact)

2. **Medium Priority (Better UX):**
   - Phase 5: Multi-line message handling
   - Phase 6: Smart continuity detection

3. **Nice to Have:**
   - Phase 2: Message buffering
   - Phase 7: Confirmation flow
   - Phase 8: Auto-save

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `services/contact_memory.py` | Add state enum, pending_contact, state tracking methods |
| `services/conversation_ai.py` | Improve prompt, add state parameter, better multi-line handling |
| `handlers/conversation_engine.py` | Deferred saving, state transitions, continuity detection |
| `handlers/input_handlers.py` | Optional: message buffering |

---

## Example of Improved Flow

**Before (Current Behavior):**
```
User: Add John Smith
Bot: John Smith saved! What else?
User: He's the CEO
Bot: [might create new contact or fail to update]
User: Of TechCorp
Bot: [confused, might think this is a new contact]
```

**After (Improved Behavior):**
```
User: Add John Smith
Bot: Starting contact for John Smith. Tell me more!
User: He's the CEO
Bot: Got it - CEO. What else?
User: Of TechCorp
Bot: John Smith - CEO at TechCorp. What else?
User: john@techcorp.com
Bot: Added email. Anything else?
User: Done
Bot: Saved John Smith to your network!
     📇 John Smith
     💼 CEO at TechCorp
     📧 john@techcorp.com
```

---

## Testing Scenarios

After implementation, test these scenarios:

1. **Multi-line input:** Paste a full business card as text
2. **Pronoun resolution:** "Add Sarah" → "She's the CTO" → "Her email is..."
3. **Interrupted flow:** "Add John" → "Actually, add Mike instead"
4. **Continuation:** "Add John" → (long message with multiple details)
5. **Cancel flow:** "Add John" → "Cancel" (should discard pending)
6. **Quick sequence:** Send 3 messages rapidly about same person
