# Rover V01 - Master Project Plan
## Telegram Network Nurturing Agent with Intelligent Enrichment

**Version:** 1.0
**Date:** January 13, 2026
**Status:** Complete

---

## Executive Summary

Rover is an AI-powered Telegram bot that helps users manage their professional network contacts through natural conversation. V01 introduces a comprehensive **Contact Enrichment System** that automatically researches and populates contact profiles with LinkedIn data, company information, industry classification, and contact type categorization.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM BOT                            │
│                      (python-telegram-bot)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MESSAGE HANDLERS                           │
│  • handlers/message_handler.py                                  │
│  • handlers/conversation_engine.py                              │
│  • handlers/enrichment_handlers.py                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ROVER AI AGENT                             │
│  • services/agent.py (OpenAI Function Calling)                  │
│  • services/agent_tools.py (Tool Implementations)               │
│  • 11 Tools: add_contact, update_contact, enrich_contact, etc.  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE SERVICES                              │
│  • services/enrichment.py (SerpAPI Web Search)                  │
│  • services/matchmaker.py (Founder-Investor Matching)           │
│  • services/contact_memory.py (Session State)                   │
│  • services/google_sheets.py (Data Storage)                     │
│  • services/ai_service.py (OpenAI Integration)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  • Google Sheets (Primary Storage)                              │
│  • Local SQLite (Fallback)                                      │
│  • Contact Schema (data/schema.py)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features Implemented in V01

### 1. Contact Management (Core)
- **Add Contact**: Natural language input ("Add Ahmed from Swypex")
- **Update Contact**: Modify fields while editing or after save
- **Save Contact**: Persist to Google Sheets
- **View Contact**: Retrieve contact details
- **List Contacts**: Show all contacts in network
- **Cancel**: Discard unsaved contact

### 2. Enrichment System (NEW in V01)

#### 2.1 Enrichment Tool (`enrich_contact`)
**Location:** `services/agent_tools.py:532-651`

The enrichment tool automatically:
- Searches web for person/company information via SerpAPI
- Finds personal LinkedIn profile (`/in/` URLs)
- Finds company LinkedIn page (`/company/` URLs)
- Extracts: title, company, industry, description, funding, location
- Determines contact_type: **Founder**, **Enabler**, or **Investor**
- **AUTO-APPLIES** data to the pending contact draft

```python
async def enrich_contact(self, name: str = None) -> str:
    """
    Enrich a contact with web research data.
    Returns a SYSTEM_NOTE that FORCES the agent to update the contact.
    """
```

#### 2.2 Enrichment Service (`EnrichmentService`)
**Location:** `services/enrichment.py`

Key methods:
- `enrich_contact_comprehensive()` - Full enrichment with all fields
- `search_linkedin_profile()` - Find personal LinkedIn
- `search_company()` - Find company information
- `_determine_contact_type()` - Classify as Founder/Enabler/Investor
- `_extract_from_linkedin_summary()` - Parse summary for missing data
- `_validate_and_route_linkedin()` - Route URLs to correct fields

#### 2.3 LinkedIn URL Validation
**Location:** `services/enrichment.py:124-159`

```python
def _is_personal_linkedin(self, url: str) -> bool:
    """Check if URL is personal profile (/in/)"""

def _is_company_linkedin(self, url: str) -> bool:
    """Check if URL is company page (/company/)"""

def _validate_and_route_linkedin(self, url: str, result: Dict):
    """Route to contact_linkedin_url or company_linkedin_url"""
```

#### 2.4 Contact Type Classification
**Location:** `services/enrichment.py:451-522`

Classification logic:
| Type | Indicators |
|------|------------|
| **Founder** | "founder", "co-founder", "CEO of startup", "built", "started" |
| **Investor** | "investor", "VC", "venture capital", "angel", "partner at fund" |
| **Enabler** | Everyone else (executives, advisors, consultants, employees) |

### 3. Matchmaker System (NEW in V01)

The Matchmaker analyzes all Founders and Investors in your network and generates compatibility matches.

#### 3.1 Matchmaker Service
**Location:** `services/matchmaker.py`

Key features:
- CrewAI-based analyst agent for pair analysis
- Match scoring algorithm (0-100)
- Stage/sector/geo/thesis alignment evaluation
- Batch processing with progress callbacks
- Automatic saving to "Matches" sheet

```python
class MatchmakerService:
    """Service for matching Founders with Investors."""

    def run_matching(self, progress_callback=None) -> Tuple[List[Match], str]:
        """Run the full matching process."""
```

#### 3.2 Match Scoring Algorithm
**Location:** `services/matchmaker.py:35-80`

| Factor | Max Points | Criteria |
|--------|-----------|----------|
| **Sector Fit** | 30 | Strong/Partial/Weak alignment |
| **Stage Alignment** | 25 | Exact/Typical/Sometimes/Outside |
| **Geo Alignment** | 20 | Local/Regional/Remote |
| **Thesis Alignment** | 25 | Strong/Partial/Tangential |

Only matches with score >= 50 are saved.

#### 3.3 Match Commands
**Location:** `handlers/matchmaker_handlers.py`

| Command | Description |
|---------|-------------|
| `/match` | Run matchmaker - analyze all Founders and Investors |
| `/matches` | View saved matches with scores |
| `/clear_matches` | Clear all matches from sheet |

#### 3.4 Match Data Schema
**Location:** `data/schema.py:448-608`

24 columns in "Matches" sheet (Sheet 2):

| Field | Description |
|-------|-------------|
| `match_id` | Unique match identifier |
| `founder_contact_id` | Link to founder contact |
| `investor_contact_id` | Link to investor contact |
| `founder_email` | Founder's email |
| `startup_name` | Founder's company |
| `investor_email` | Investor's email |
| `investor_firm` | Investor's firm |
| `match_score` | 0-100 compatibility score |
| `primary_match_reason` | Main reason for match |
| `match_rationale` | Intro blurb explanation |
| `thesis_alignment_notes` | Thesis fit analysis |
| `portfolio_synergy` | Portfolio fit notes |
| `anti_portfolio_flag` | Conflict flag (TRUE/FALSE) |
| `sector_overlap` | Sector analysis |
| `stage_alignment` | Match/Reach/Safety |
| `check_size_fit` | Investment size fit |
| `geo_alignment` | Geographic alignment |
| `intro_angle` | Flattery/Momentum/Hard Data/Mutual/Thesis |
| `suggested_subject_line` | Email subject line |
| `recent_news_hook` | News hook for intro |
| `tone_instruction` | Warm/Formal/Urgent |
| `match_date` | When match was created |
| `email_status` | Drafted/Sent/Replied/Meeting Scheduled/Passed |
| `human_approved` | Manual approval flag |

#### 3.5 Enums for Match Fields
**Location:** `data/schema.py:479-509`

```python
class StageAlignment(str, Enum):
    MATCH = "Match"      # Perfect stage fit
    REACH = "Reach"      # Founder stage slightly below
    SAFETY = "Safety"    # Founder stage slightly above

class IntroAngle(str, Enum):
    FLATTERY = "Flattery"    # Compliment achievement
    MOMENTUM = "Momentum"    # Highlight traction
    HARD_DATA = "Hard Data"  # Lead with metrics
    MUTUAL = "Mutual"        # Mutual connection
    THESIS = "Thesis"        # Appeal to thesis

class ToneInstruction(str, Enum):
    WARM = "Warm"
    FORMAL = "Formal"
    URGENT = "Urgent"

class EmailStatus(str, Enum):
    DRAFTED = "Drafted"
    SENT = "Sent"
    REPLIED = "Replied"
    MEETING_SCHEDULED = "Meeting Scheduled"
    PASSED = "Passed"
    MISSING_DATA = "Missing Data"
```

#### 3.6 Google Sheets Integration
**Location:** `services/google_sheets.py:394-574`

New methods for Matches sheet:
- `get_matches_worksheet()` - Get or create "Matches" sheet
- `get_all_contacts_as_json()` - Read all contacts as JSON
- `get_founders_and_investors()` - Filter by contact_type
- `add_match()` / `add_matches_batch()` - Write matches
- `get_all_matches()` - Read all matches
- `clear_matches()` - Clear matches sheet

### 3.5 Outreach Agent System (NEW in V01.2)

The Outreach Agent generates personalized email drafts from high-quality matches and sends approved emails.

#### 3.5.1 Outreach Service
**Location:** `services/outreach.py`

Key features:
- CrewAI-based "Venture Email Copywriter" agent
- Personalized email generation using match context
- SMTP email sending via Gmail or custom server
- Draft status tracking and approval workflow

```python
class OutreachService:
    """Service for drafting and sending outreach emails."""

    def create_drafts_from_matches(self, min_score=70) -> Tuple[int, str]:
        """Create email drafts from high-quality matches."""

    def send_approved_emails(self) -> Tuple[int, int, str]:
        """Send all approved emails."""
```

#### 3.5.2 Outreach Commands
**Location:** `handlers/outreach_handlers.py`

| Command | Description |
|---------|-------------|
| `/draft` | Generate email drafts from matches (score >= 70) |
| `/draft 80` | Generate drafts from matches with score >= 80 |
| `/send_approved` | Send emails with approval_status = APPROVED |
| `/drafts` | Show draft statistics |
| `/clear_drafts` | Clear all drafts |

#### 3.5.3 Draft Data Schema
**Location:** `data/schema.py:615-713`

13 columns in "Drafts" sheet (Sheet 3):

| Field | Description |
|-------|-------------|
| `draft_id` | Unique draft identifier |
| `match_id` | Link to original match |
| `recipient_email` | Investor's email |
| `recipient_name` | Investor's name |
| `startup_name` | Founder's company |
| `investor_firm` | Investor's firm |
| `email_subject` | Generated subject line |
| `email_body` | Generated email content |
| `approval_status` | PENDING / APPROVED / REJECTED |
| `reviewer_notes` | Human notes/edits |
| `send_status` | Drafted / Sent / Failed |
| `created_date` | Draft creation timestamp |
| `sent_date` | When email was sent |

#### 3.5.4 Approval Workflow

```
/match → Matches Sheet → /draft → Drafts Sheet → User Review → /send_approved → Email Sent
```

1. **Generate Matches**: `/match` analyzes contacts, saves to Sheet 2
2. **Create Drafts**: `/draft` reads high-score matches, generates emails, saves to Sheet 3
3. **Review**: User opens Drafts sheet, reviews `email_body`, sets `approval_status` to "APPROVED"
4. **Send**: `/send_approved` sends approved emails, updates `send_status` to "Sent"

#### 3.5.5 Email Template Structure

The LLM generates emails with this structure:
- **Subject**: Catchy, relevant (e.g., "Intro: [Startup] x [VC] - [Thesis] Fit")
- **Opening**: Warm hook, reference recent news if available
- **Body**: "I met [Founder] recently. They're building [pitch]. I thought of you because [rationale]."
- **Call to Action**: "Check out their deck. Open to an intro?"
- **Sign-off**: "Best, [Sender Name]"

#### 3.5.6 SMTP Configuration

Required environment variables:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_NAME=Your Name
SENDER_EMAIL=your-email@gmail.com
```

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

### 4. Agent System (OpenAI Function Calling)

#### 4.1 System Prompt
**Location:** `services/agent.py:208-343`

Key sections:
- Current context injection (pending contact, last action, state)
- 11 tool capabilities
- **Enrichment Protocol** - Auto-apply enrichment data
- **Context Retention** - Use previous search results
- Pronoun resolution ("Add him" after discussing someone)
- Session termination protocol

#### 4.2 Tools Available
**Location:** `services/agent.py:25-191`

| Tool | Description |
|------|-------------|
| `add_contact` | Create new contact, start editing |
| `update_contact` | Update pending contact fields |
| `update_existing_contact` | Update saved contact by name |
| `save_contact` | Save to Google Sheets |
| `search_web` | SerpAPI web search |
| `summarize_search_results` | AI summary of search |
| `get_contact` | View contact from database |
| `list_contacts` | List all contacts |
| `get_search_links` | Get URLs from search |
| `cancel_current` | Discard pending contact |
| `enrich_contact` | **NEW** - Auto-enrich with web data |

### 5. Memory & State Management

#### 5.1 Contact Memory Service
**Location:** `services/contact_memory.py`

States:
- `IDLE` - No active contact
- `COLLECTING` - Gathering info for pending contact
- `EDITING` - Modifying existing contact

Key features:
- `get_pending_contact()` - Get draft being edited
- `update_pending()` - Apply updates to draft
- `set_last_saved_contact()` - Track for post-save corrections
- `get_last_saved_contact()` - Recall last saved

#### 5.2 Recall Last Saved (Fix #3)
**Location:** `handlers/conversation_engine.py:1100-1154`

Allows user to add info to last saved contact:
```
User: "Save"
Bot: "Saved Ahmed!"
User: "Wait, add his email ahmed@example.com"
Bot: "Re-opening Ahmed for editing..."
```

### 6. Data Schema

#### 6.1 Contact Fields
**Location:** `data/schema.py`

| Field | Description |
|-------|-------------|
| `full_name` | Contact's full name |
| `company` | Company/organization |
| `title` | Job title |
| `linkedin_url` | Personal LinkedIn (`/in/`) |
| `linkedin_link` | Company LinkedIn (`/company/`) |
| `contact_type` | Founder / Enabler / Investor |
| `industry` | Industry classification |
| `company_description` | About the company |
| `company_stage` | Seed, Series A, Growth, etc. |
| `funding_raised` | Funding amount |
| `linkedin_summary` | Bio from LinkedIn |
| `research_quality` | High / Medium / Low |
| `researched_date` | When enrichment was done |

---

## Critical Fixes Implemented

### Fix 1: Auto-Ingest Enrichment Data
**Problem:** Enrichment showed JSON but didn't update the contact draft.

**Solution:** `enrich_contact` tool now AUTO-APPLIES data:
```python
if pending and target_name.lower() in pending.name.lower():
    # Apply updates to pending contact
    self.memory.update_pending(self.user_id, updates)
```

### Fix 2: LinkedIn URL Validation
**Problem:** Company URLs (`/company/`) were saved as personal profiles.

**Solution:** URL routing validators:
```python
if self._is_personal_linkedin(url):
    result["contact_linkedin_url"] = url
elif self._is_company_linkedin(url):
    result["company_linkedin_url"] = url
```

### Fix 3: Recall Last Saved Contact
**Problem:** After saving, user couldn't add forgotten info.

**Solution:** Detection patterns for post-save corrections:
```python
recall_patterns = [
    "add his ", "add her ", "forgot ", "wait,", "also add"
]
```

### Fix 4: SYSTEM_NOTE Prompt Injection
**Problem:** Agent treated enrichment output as display text.

**Solution:** Return format that forces action:
```
SYSTEM_NOTE: ENRICHMENT DATA FOUND. YOU MUST UPDATE THE CONTACT...
ACTION REQUIRED: Call update_existing_contact with...
```

---

## File Structure

```
Rover_Network_agent/
├── main.py                          # Entry point
├── config.py                        # Configuration
├── Rover_V01_Project_Plan.md        # This document
│
├── handlers/
│   ├── message_handler.py           # Telegram message routing
│   ├── conversation_engine.py       # Legacy conversation processing
│   ├── enrichment_handlers.py       # /enrich command handlers
│   ├── matchmaker_handlers.py       # /match, /matches, /clear_matches
│   └── outreach_handlers.py         # /draft, /send_approved, /drafts
│
├── services/
│   ├── agent.py                     # Rover AI Agent (OpenAI)
│   ├── agent_tools.py               # Tool implementations
│   ├── enrichment.py                # EnrichmentService (SerpAPI)
│   ├── matchmaker.py                # MatchmakerService (CrewAI)
│   ├── outreach.py                  # OutreachService (Email Drafting)
│   ├── contact_memory.py            # Session state management
│   ├── google_sheets.py             # Google Sheets integration
│   ├── ai_service.py                # OpenAI API wrapper
│   └── conversation_ai.py           # Intent classification
│
├── agents/
│   ├── enrichment_agent.py          # CrewAI enrichment agent
│   └── data_enrichment_agent.py     # Data enrichment utilities
│
├── crews/
│   └── enrichment_crew.py           # CrewAI crew orchestration
│
├── data/
│   └── schema.py                    # Contact data model
│
├── training/
│   └── enrichment_training_data.jsonl  # Training examples
│
└── analytics/
    └── tracker.py                   # Usage analytics
```

---

## API Dependencies

| Service | Purpose | Key |
|---------|---------|-----|
| **Telegram Bot API** | Messaging interface | `TELEGRAM_BOT_TOKEN` |
| **OpenAI API** | Agent reasoning (GPT-4) | `OPENAI_API_KEY` |
| **SerpAPI** | Web search for enrichment | `SERPAPI_API_KEY` |
| **Google Sheets API** | Data storage | Service account JSON |

---

## Training Data

**Location:** `training/enrichment_training_data.jsonl`

Contains 33 training examples covering:
- Single contact enrichment
- Bulk enrichment
- Partial/failed enrichment
- Company vs person enrichment
- Post-save corrections
- Auto-apply scenarios

Sample:
```json
{
  "messages": [
    {"role": "user", "content": "Add Ahmed from Swypex."},
    {"role": "assistant", "content": "Added Ahmed (Swypex)."},
    {"role": "user", "content": "Enrich him."},
    {"role": "assistant", "content": "Found: LinkedIn, Company LinkedIn, Bio...
     I have AUTO-APPLIED these fields to the profile."}
  ]
}
```

---

## Usage Examples

### Basic Flow
```
User: Add Ahmed Mokhtar as CEO of Swypex
Bot:  Started new contact: Ahmed Mokhtar (Title: CEO, Company: Swypex)

User: Enrich
Bot:  ENRICHMENT COMPLETE for Ahmed Mokhtar.
      I found and AUTO-APPLIED these fields:
      • linkedin_url: linkedin.com/in/ahmed-mokhtar
      • company_linkedin: linkedin.com/company/swypex
      • industry: Fintech
      • contact_type: Founder
      Say 'save' when ready.

User: Save
Bot:  Saved Ahmed Mokhtar to your network! ✅
```

### Post-Save Correction
```
User: Save
Bot:  Saved Ahmed Mokhtar!

User: Wait, add his email ahmed@swypex.com
Bot:  Re-opening Ahmed Mokhtar for editing. Updated email.
```

### Matchmaker Flow
```
User: /match
Bot:  Starting the Matchmaker...
      Analyzing Founders and Investors in your network.
      This may take a few minutes.

Bot:  MATCHMAKER COMPLETE

      Contacts Analyzed:
      - Founders: 5
      - Investors: 8
      - Total pairs evaluated: 40

      Results:
      - High-quality matches (80+): 3
      - Medium-quality matches (50-79): 7
      - Total matches saved: 10

      Top Matches:
      1. Swypex <-> Algebra Ventures
         Score: 85/100
         Sector: Strong - Fintech focus

      Saved 10 matches to 'Matches' sheet.
```

### View Matches
```
User: /matches
Bot:  Saved Matches (10 total)

      1. ⭐ Swypex <-> Algebra Ventures
         Score: 85/100 | Match

      2. ⭐ TechStartup <-> Sequoia
         Score: 82/100 | Match

      3. DataCo <-> A16Z
         Score: 75/100 | Reach

      ...and 7 more matches in your Sheets.
```

### Draft Emails Flow
```
User: /draft
Bot:  Starting the Drafter...
      Looking for matches with score >= 70
      This may take a few minutes.

Bot:  DRAFTER COMPLETE

      Matches processed: 10
      Drafts created: 8

      Next steps:
      1. Open the 'Drafts' sheet in your Google Spreadsheet
      2. Review each email in the 'email_body' column
      3. Edit as needed in 'reviewer_notes'
      4. Set 'approval_status' to "APPROVED" for emails ready to send
      5. Run /send_approved to send approved emails
```

### Send Approved Emails
```
User: /send_approved
Bot:  Checking for approved emails...
      Looking for drafts with approval_status = APPROVED

Bot:  SENDER COMPLETE

      Emails sent: 5
      Emails failed: 0

      Check the 'Drafts' sheet for send_status updates.
```

### Draft Statistics
```
User: /drafts
Bot:  Draft Statistics

      Total drafts: 8
      Pending review: 3
      Approved: 2
      Sent: 3
      Failed: 0

      Commands:
      - /draft - Create new drafts from matches
      - /send_approved - Send approved drafts
      - /clear_drafts - Clear all drafts
```

---

## Future Enhancements (V02 Roadmap)

1. **Bulk Enrichment** - Enrich all contacts with missing data
2. **Email Finder** - Integrate email discovery APIs
3. **News Alerts** - Track contact/company news
4. **Relationship Scoring** - Auto-calculate relationship strength
5. **Export** - CSV/Excel export functionality
6. **Voice Input** - Voice message support for adding contacts

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| V01 | 2026-01-13 | Initial release with enrichment system |
| V01.1 | 2026-01-13 | Added Matchmaker system (Founder-Investor matching) |
| V01.2 | 2026-01-13 | Added Outreach Agent (email drafting & sending) |

---

**Built with:** Python 3.12, CrewAI, OpenAI GPT-4, SerpAPI, Google Sheets API, python-telegram-bot
