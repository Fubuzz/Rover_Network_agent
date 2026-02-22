# Changelog - Rover Network Agent

## Version 2.3.0 - Targeted Outreach

**Date:** 2026-02-22

This update adds a direct outreach pipeline that lets you draft personalized emails to filtered contacts using natural language, with drafts saved to the existing Airtable approval workflow.

---

### New Features

1. **`/outreach` Command**
   - Natural language outreach: `/outreach Email all investors in Egypt about a meeting March 5-12`
   - Parses NL into structured filter criteria (contact type, industry, location)
   - Generates personalized emails per contact via GPT
   - Saves drafts as PENDING in Airtable Drafts table
   - Flows through existing APPROVED → `/send_approved` pipeline

2. **Multi-Criteria Contact Filtering (`filter_contacts()`)**
   - New `AirtableService.filter_contacts(criteria)` method
   - Builds Airtable `AND(FIND(...))` formulas for server-side filtering
   - Field alias support: `type` → `contact_type`, `location` → `address`, etc.
   - Client-side fallback if formula query fails

3. **`draft_emails()` Agent Tool — Now Saves Drafts**
   - Previously returned text-only email previews
   - Now creates Draft objects and saves to Airtable as PENDING
   - Works through natural conversation: "Can you email my fintech investors about meeting next week?"

### Files Added/Modified

| File | Changes |
|------|---------|
| `services/outreach_direct.py` | NEW — parse NL, filter contacts, generate emails, save drafts |
| `services/airtable_service.py` | Added `filter_contacts()` + `_client_side_filter()` methods |
| `services/agent_tools.py` | Rewired `draft_emails()` to call outreach_direct and save drafts |
| `handlers/outreach_handlers.py` | Added `/outreach` command handler |

### Data Flow

```
User: "Email all investors in Egypt about meeting March 5-12"
  │
  ├─ Via /outreach command ─────────┐
  └─ Via conversation (draft_emails)┤
                                    ▼
                      create_outreach_drafts()
                        │
                        ├─ parse_outreach_request() → structured criteria
                        ├─ filter_contacts() → matching contacts
                        ├─ generate_outreach_email() × N contacts
                        └─ add_drafts_batch() → Airtable (PENDING)
                                    │
                                    ▼
                      Review → APPROVED → /send_approved → SMTP
```

---

## Version 2.2.0 - Bulk Contact Import

**Date:** 2026-01-15

This update adds bulk contact import functionality, allowing you to upload CSV or Excel files to import multiple contacts at once.

---

### New Features

1. **Bulk Import from CSV/Excel**
   - Upload CSV or XLSX files directly to the bot
   - Auto-detects column headers (Name, Email, Company, Title, etc.)
   - Supports multiple header variations (e.g., "Full Name", "Contact Name", "Name")
   - Progress reporting during import

2. **Smart Duplicate Handling**
   - Detects existing contacts by email or name
   - Updates existing contacts with new data (merge behavior)
   - Reports count of added vs updated vs skipped

3. **Import Result Summary**
   - Shows total rows processed
   - Counts: Added, Updated, Skipped, Failed
   - Lists first 5 errors with details

### Files Added/Modified

| File | Changes |
|------|---------|
| `services/bulk_import.py` | NEW - Core bulk import service |
| `handlers/input_handlers.py` | Updated document handler |
| `data/schema.py` | Added ImportResult model |
| `requirements.txt` | Added openpyxl for Excel support |

### Supported File Formats

- **CSV** - Comma-separated values
- **XLSX** - Microsoft Excel 2007+
- **XLS** - Legacy Excel (basic support)

### Header Mapping Examples

| Your Header | Maps To |
|-------------|---------|
| Name, Full Name, Contact Name | `full_name` |
| Email, E-mail, Email Address | `email` |
| Company, Organization, Firm | `company` |
| Title, Job Title, Position, Role | `title` |
| Phone, Mobile, Tel | `phone` |
| LinkedIn, LinkedIn URL | `linkedin_url` |
| Type, Category, Classification | `contact_type` |

---

## Version 2.1.0 - Pydantic Validation & Bug Fixes

**Date:** 2026-01-15

This update adds Pydantic validation for data integrity, fixes critical bugs with contact saving, and resolves Telegram markdown parsing errors.

---

### Bug Fixes

1. **Fixed Silent Contact Save Failure**
   - **Issue:** Contacts with duplicate emails were silently not saved, but bot reported success
   - **Fix:** Smart duplicate detection now only blocks if same name AND same email
   - Different people can share the same email (warns but allows)
   - Proper error messages when save fails

2. **Fixed Matchmaker Markdown Parsing Errors**
   - **Issue:** "Can't parse entities: can't find end of the entity starting at byte offset 244"
   - **Cause:** `<->` and `<>` characters were interpreted as HTML entities
   - **Fix:** Replaced with unicode arrows (↔) and removed markdown parsing from all matchmaker messages

### New Features

1. **Pydantic Data Validation**
   - Converted `Match` and `Draft` from dataclasses to Pydantic BaseModels
   - Field validators for automatic data coercion and cleaning
   - Match scores automatically clamped to 0-100 range
   - Email validation and cleaning
   - Placeholder text rejection in drafts

2. **Sheet Name Constants**
   - Added `CONTACTS_SHEET_NAME = "contacts"` (Sheet 1)
   - Added `MATCHES_SHEET_NAME = "Matches"` (Sheet 2)
   - Added `DRAFTS_SHEET_NAME = "Drafts"` (Sheet 3)
   - All services now use constants instead of hardcoded strings

3. **Tool Argument Schemas**
   - `WriteMatchToolArgs` - Validates LLM output for match writing
   - `WriteDraftToolArgs` - Validates LLM output for draft writing
   - `ContactLookupArgs` - Validates contact lookup requests

### Files Modified

| File | Changes |
|------|---------|
| `data/schema.py` | Pydantic models, sheet constants, tool schemas |
| `services/google_sheets.py` | Smart duplicate email check, sheet constants |
| `services/agent_tools.py` | Better error feedback for save operations |
| `services/matchmaker.py` | Unicode arrows, safer subject lines |
| `handlers/matchmaker_handlers.py` | Plain text messages (no markdown parsing) |
| `handlers/conversation_engine.py` | Updated save function signature |

---

## Version 2.0.0 - Smarter Agent Update

**Date:** 2026-01-11

This update makes the Telegram agent significantly smarter and more natural in conversation. The agent now properly handles multi-message flows, understands context, and doesn't prematurely save contacts.

---

## Summary of Changes

### Core Improvements
1. **Deferred Saving** - Contacts are no longer saved immediately. They're collected in memory and only saved when user says "done"
2. **Conversation State Machine** - Added IDLE, COLLECTING, CONFIRMING states to track conversation flow
3. **Smart Intent Override** - Prevents accidental new contact creation when user is still adding info to current contact
4. **Cancel Support** - Users can now cancel and discard unsaved contacts
5. **Better AI Prompt** - Enhanced Gemini prompt with state awareness and stricter intent rules

---

## Detailed Changes by File

### 1. `services/contact_memory.py`

**Added ConversationState Enum:**
```python
class ConversationState(Enum):
    IDLE = "idle"              # No active contact
    COLLECTING = "collecting"  # Gathering info (not saved yet)
    CONFIRMING = "confirming"  # Waiting for save confirmation
```

**New UserMemory Fields:**
- `pending_contact: Optional[Contact]` - Contact being built (not yet saved)
- `state: ConversationState` - Current conversation state
- `last_message_time: datetime` - For detecting rapid messages
- `auto_saved: bool` - Flag for auto-save notification
- `CONTINUATION_SECONDS = 30` - Window for continuation detection

**New UserMemory Methods:**
- `start_collecting(contact)` - Begin collecting for a new contact
- `update_pending(updates)` - Update the pending contact
- `get_pending_contact()` - Get unsaved contact
- `clear_pending()` - Clear after saving
- `cancel_pending()` - Discard without saving
- `is_collecting()` - Check if in collecting mode
- `is_continuation()` - Check if message is part of same flow

**New ContactMemoryService Methods:**
- `start_collecting(user_id, contact)`
- `get_pending_contact(user_id)`
- `update_pending(user_id, updates)`
- `clear_pending(user_id)`
- `cancel_pending(user_id)`
- `get_state(user_id)`
- `set_state(user_id, state)`
- `is_collecting(user_id)`
- `is_continuation(user_id)`
- `get_context_for_ai(user_id)` - Now returns tuple with state

---

### 2. `services/conversation_ai.py`

**Added CANCEL Intent:**
```python
class Intent(Enum):
    ...
    CANCEL = "cancel"  # Cancel current contact without saving
```

**Enhanced ANALYSIS_PROMPT:**
- Added `{state}` placeholder for conversation state
- Added strict intent rules for COLLECTING state:
  - Short messages (under 10 words) with contact info → UPDATE_CONTACT
  - Pronouns → UPDATE_CONTACT for current contact
  - "done/save" → FINISH
  - "cancel/nevermind" → CANCEL
- Added multi-line handling instructions
- Added example responses for different states

**Updated `analyze_message()` Function:**
- Added `state: Optional[ConversationState]` parameter
- Passes state to prompt for context-aware analysis
- Includes email in current_contact context string

**Updated `_fallback_analysis()` Function:**
- Added state parameter
- Added cancel word detection
- Added smarter pattern matching for collecting mode:
  - Phone number detection
  - LinkedIn URL detection
  - Job title detection
- Only suggests ADD_CONTACT if not already collecting

---

### 3. `handlers/conversation_engine.py`

**Updated Imports:**
```python
from services.contact_memory import get_memory_service, ConversationState
import re  # Added for pattern matching
```

**Rewritten `handle_add_contact()`:**
- Now checks if already collecting - redirects to update if appropriate
- Asks for clarification if user mentions different name while collecting
- Checks if contact already exists in storage
- Uses `memory.start_collecting()` instead of immediate save
- Does NOT save to storage - just stores in memory

**Rewritten `handle_update_contact()`:**
- First checks for pending contact (collecting mode)
- Uses `memory.update_pending()` instead of `update_contact_in_storage()`
- Updates only happen in memory until "done"
- Added support for name updates and notes

**Rewritten `handle_finish()`:**
- NOW actually saves to storage (was deferred)
- Handles both new contacts and updates to existing
- Calls `save_contact_to_storage()` or `update_contact_in_storage()`
- Calls `memory.clear_pending()` after successful save

**New `handle_cancel()` Function:**
- Discards pending contact without saving
- Clears current contact from memory
- Returns fun confirmation messages

**New Helper Functions:**
```python
def contains_contact_info(message: str) -> bool:
    """Check if message contains email, phone, LinkedIn, titles, etc."""

def should_override_to_update(message, result, state) -> bool:
    """Determine if ADD_CONTACT should be overridden to UPDATE_CONTACT."""
```

**Updated `process_message()`:**
- Gets state from `memory.get_context_for_ai(user_id)` (now returns 3 values)
- Passes state to `analyze_message()`
- Applies smart intent override when in COLLECTING state
- Added CANCEL intent handling

---

## Behavior Changes

### Before (Old Behavior)
```
User: Add John Smith
Bot: John Smith is in my vault! [SAVED IMMEDIATELY]
User: He's the CEO
Bot: [Might create new contact or fail]
User: Of TechCorp
Bot: [Confused]
```

### After (New Behavior)
```
User: Add John Smith
Bot: Starting a new contact for John Smith! Tell me more...
User: He's the CEO
Bot: Got it! CEO. What else?
User: Of TechCorp
Bot: Got it! at TechCorp. What else?
User: john@techcorp.com
Bot: Got it! john@techcorp.com. What else?
User: Done
Bot: John Smith saved to your network! [SAVED NOW]
     John Smith
     CEO at TechCorp
     john@techcorp.com
```

### Cancel Flow
```
User: Add Sarah Chen
Bot: Starting a new contact for Sarah Chen!
User: Actually, cancel
Bot: Discarded Sarah Chen. Never happened!
```

### Existing Contact Detection
```
User: Add John Smith
Bot: John Smith already exists!
     [Shows existing contact card]
     What would you like to update?
```

---

## Testing Checklist

After deployment, test these scenarios:

- [ ] Add new contact with multiple messages
- [ ] Use pronouns ("he's", "she's", "their email")
- [ ] Multi-line paste (business card text)
- [ ] Cancel flow ("cancel", "nevermind")
- [ ] Finish flow ("done", "save")
- [ ] Try to add second contact while collecting first
- [ ] Update existing contact
- [ ] Quick sequence of messages about same person
- [ ] Voice message transcription flow
- [ ] Business card photo flow

---

## Rollback Instructions

If issues occur, revert these files to their previous versions:
1. `services/contact_memory.py`
2. `services/conversation_ai.py`
3. `handlers/conversation_engine.py`

The changes are backwards compatible with existing data in Google Sheets.
