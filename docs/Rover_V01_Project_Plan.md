# Rover V02 - Master Project Plan
## Telegram Network Nurturing Agent with Intelligent Enrichment

**Version:** 2.2.0
**Date:** January 19, 2026
**Status:** Active Development

---

## Executive Summary

Rover is an AI-powered Telegram bot that helps users manage their professional network contacts through natural conversation. The system leverages CrewAI for agent orchestration, stores data in Airtable, and enables intelligent matching between founders and investors with automated email outreach.

### Core Features

| Feature | Description |
|---------|-------------|
| **Contact Management** | Full CRUD operations with natural language parsing, voice messages, and business card OCR |
| **Contact Enrichment** | Automatically researches and populates contact profiles with LinkedIn data, company information, industry classification, and contact type categorization |
| **Matchmaker System** | Analyzes Founders and Investors to generate compatibility matches with scoring (0-100) |
| **Outreach Agent** | Generates personalized email drafts and sends approved emails via SMTP |
| **Bulk Import** | Upload CSV or Excel files to import multiple contacts with auto header detection |
| **Multi-Input Support** | Voice messages (Whisper), business card photos (GPT-4 Vision), and natural language input |
| **Statistics & Reporting** | Network analytics, contact statistics, and CSV export |
| **Analytics & Monitoring** | Operation tracking, performance metrics, and quality evaluation |
| **Organization Tools** | Notes, tags, and follow-up reminders for contacts |

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Bot Framework** | python-telegram-bot 20.7+ |
| **AI Orchestration** | CrewAI 0.28.0+ |
| **Language Models** | OpenAI GPT-4, Google Gemini 2.0 Flash |
| **Data Storage** | Airtable API, SQLite 3 (analytics) |
| **Web Search** | Tavily API, SerpAPI |
| **Email** | SMTP (Gmail or custom) |
| **Voice Processing** | OpenAI Whisper |
| **Image Processing** | GPT-4 Vision, Pillow |
| **Validation** | Pydantic 2.5+ |

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
│  • services/bulk_import.py (CSV/Excel Bulk Import)              │
│  • services/contact_memory.py (Session State)                   │
│  • services/airtable_service.py (Data Storage)                  │
│  • services/ai_service.py (OpenAI Integration)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  • Airtable (Primary Storage)                                   │
│  • Local SQLite (Fallback)                                      │
│  • Contact Schema (data/schema.py)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features Implemented in V01

### 1. Contact Management (Core)

#### 1.1 Basic Operations
- **Add Contact**: Natural language input ("Add Ahmed from Swypex")
- **Update Contact**: Modify fields while editing or after save
- **Save Contact**: Persist to Airtable
- **View Contact**: Retrieve contact details (`/view <name>`)
- **List Contacts**: Show all contacts in network (`/list`)
- **Search Contacts**: Full-text search across all fields (`/search <query>`)
- **Delete Contact**: Remove contact from network (`/delete <name>`)
- **Cancel**: Discard unsaved contact

#### 1.2 Input Methods

| Method | Description | Handler |
|--------|-------------|---------|
| **Text Input** | Natural language parsing ("Add John from TechCorp as CEO") | `handlers/conversation_engine.py` |
| **Voice Messages** | Transcribed via OpenAI Whisper, parsed intelligently | `handlers/input_handlers.py` |
| **Images (Business Cards)** | OCR extraction using GPT-4 Vision | `handlers/input_handlers.py` |
| **Bulk Import** | CSV/Excel with smart header detection | `services/bulk_import.py` |
| **Conversation Flow** | Multi-turn dialogue with session memory | `handlers/conversation_engine.py` |

#### 1.3 Voice Message Processing
**Location:** `handlers/input_handlers.py`

Voice messages are automatically:
1. Downloaded from Telegram
2. Converted to WAV format (if needed)
3. Transcribed using OpenAI Whisper API
4. Parsed for contact information using AI
5. Processed through normal conversation flow

```python
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process voice messages - transcribe and extract contact info."""
    # Download voice file
    # Transcribe with Whisper
    # Process as text input
```

#### 1.4 Business Card OCR
**Location:** `handlers/input_handlers.py`

Image processing workflow:
1. User sends photo of business card
2. Image downloaded from Telegram
3. GPT-4 Vision extracts text and structure
4. AI parses into contact fields (name, title, company, email, phone)
5. Contact draft created for user confirmation

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process photos - extract contact info from business cards."""
    # Download image
    # Send to GPT-4 Vision for OCR
    # Parse structured data
    # Create contact draft
```

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

#### 3.6 Airtable Integration
**Location:** `services/airtable_service.py`

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

### 3.6 Bulk Contact Import System (NEW in V2.2)

The Bulk Import system allows users to upload CSV or Excel files to import multiple contacts at once.

#### 3.6.1 Bulk Import Service
**Location:** `services/bulk_import.py`

Key features:
- CSV and XLSX file parsing
- Flexible header auto-detection (maps various column names to Contact fields)
- Smart duplicate handling (updates existing contacts instead of creating duplicates)
- Progress reporting and error tracking
- Validation with detailed import results

```python
class BulkImportService:
    """Service for bulk importing contacts from CSV/Excel files."""

    async def import_file(self, file_bytes: bytes, filename: str) -> ImportResult:
        """Main entry point - routes to correct parser based on extension."""

    def _parse_csv(self, file_bytes: bytes) -> List[Dict]:
        """Parse CSV file into list of contact dicts."""

    def _parse_xlsx(self, file_bytes: bytes) -> List[Dict]:
        """Parse Excel file into list of contact dicts."""

    def _detect_headers(self, headers: List[str]) -> Dict[str, str]:
        """Map file headers to Contact field names."""
```

#### 3.6.2 Header Auto-Detection
**Location:** `services/bulk_import.py:16-62`

The system recognizes various header name variations:

| Your Header | Maps To |
|-------------|---------|
| Name, Full Name, Contact Name | `full_name` |
| Email, E-mail, Email Address | `email` |
| Company, Organization, Firm | `company` |
| Title, Job Title, Position, Role | `title` |
| Phone, Mobile, Tel, Telephone | `phone` |
| LinkedIn, LinkedIn URL | `linkedin_url` |
| Type, Category, Classification | `contact_type` |
| Industry, Sector | `industry` |
| Notes, Comments | `notes` |
| Location, Address, City, Country | `address` |

#### 3.6.3 Duplicate Handling Logic
**Location:** `services/bulk_import.py:140-185`

```python
def _save_contact(self, contact: Contact) -> Tuple[str, bool]:
    """
    Save or update contact.
    Returns: ("added" | "updated" | "skipped", success_bool)
    """
    # 1. Check for existing by email
    if contact.email:
        existing = self.sheets_service.find_contact_by_email(contact.email)
        if existing:
            # Update existing contact with new data
            return "updated", True

    # 2. Check for existing by name
    if contact.name:
        existing = self.sheets_service.get_contact_by_name(contact.name)
        if existing:
            return "updated", True

    # 3. Add as new contact
    return "added", True
```

#### 3.6.4 Import Result Schema
**Location:** `data/schema.py`

```python
@dataclass
class ImportResult:
    """Result of a bulk import operation."""
    total_rows: int = 0
    successful: int = 0      # New contacts added
    updated: int = 0         # Existing contacts updated
    skipped: int = 0         # Rows with no name/email
    failed: int = 0          # Rows that caused errors
    errors: List[str] = field(default_factory=list)
```

#### 3.6.5 Supported File Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| CSV | `.csv` | Python `csv` module |
| Excel 2007+ | `.xlsx` | `openpyxl` library |
| Legacy Excel | `.xls` | `openpyxl` (basic support) |

#### 3.6.6 Usage

Upload a CSV or Excel file directly to the bot chat. The bot will:
1. Detect the file format
2. Parse headers and map to Contact fields
3. Process each row
4. Check for duplicates (by email, then by name)
5. Add new contacts or update existing ones
6. Report results with counts and any errors

Sample CSV:
```csv
Name,Email,Company,Title,Phone,Type
John Doe,john@example.com,TechCorp,CEO,+1234567890,founder
Jane Smith,jane@example.com,InvestCo,Partner,,investor
```

### 3.7 Statistics & Reporting System

The Statistics & Reporting system provides comprehensive analytics about your network.

#### 3.7.1 Statistics Commands
**Location:** `handlers/report_handlers.py`

| Command | Description |
|---------|-------------|
| `/stats` | Overall contact summary |
| `/stats by company` | Group contacts by company |
| `/stats by industry` | Group contacts by industry |
| `/stats by type` | Group contacts by classification |
| `/stats by location` | Group contacts by location |
| `/report <name>` | Detailed individual contact report |
| `/report all` | Network-wide analysis |
| `/export` | Export all contacts to CSV |

#### 3.7.2 Statistics Output

```
User: /stats
Bot:  📊 Network Statistics

      Total Contacts: 45

      By Classification:
      • Founders: 18 (40%)
      • Investors: 15 (33%)
      • Enablers: 12 (27%)

      Data Completeness:
      • With email: 42 (93%)
      • With LinkedIn: 38 (84%)
      • Enriched: 35 (78%)

      Top Industries:
      • Fintech: 12
      • SaaS: 10
      • AI/ML: 8
```

#### 3.7.3 Export Functionality
**Location:** `handlers/report_handlers.py`

The `/export` command generates a CSV file containing all contacts with:
- All contact fields
- Enrichment data
- Classification information
- Tags and notes

### 3.8 Analytics & Monitoring System

The Analytics system tracks all operations, performance metrics, and data quality.

#### 3.8.1 Analytics Commands
**Location:** `handlers/analytics_handlers.py`

| Command | Description |
|---------|-------------|
| `/dashboard` | Real-time system status |
| `/analytics` | Usage analytics overview |
| `/analytics operations` | Operation-specific stats |
| `/analytics features` | Feature usage breakdown |
| `/analytics performance` | Performance metrics |
| `/analytics export <days>` | Export analytics data as JSON |

#### 3.8.2 Evaluation Commands
**Location:** `handlers/evaluation_handlers.py`

| Command | Description |
|---------|-------------|
| `/eval` | Data quality evaluation |
| `/eval operations` | Operation success/failure rates |
| `/eval quality` | Data completeness assessment |
| `/eval agents` | Agent performance metrics |

#### 3.8.3 Analytics Storage
**Location:** `logs/analytics.db` (SQLite)

The analytics system tracks:
- **Operations**: Type, status, user, duration, timestamp, errors
- **Features**: Name, enabled status, usage counts
- **Changes**: Feature modifications, version tracking
- **Performance**: Response times, API latencies

```python
@dataclass
class OperationLog:
    operation_type: str      # add_contact, enrich_contact, etc.
    status: str              # success, failure
    user_id: str
    duration_ms: int
    timestamp: datetime
    error_message: Optional[str]
```

### 3.9 Organization Features

Organization tools help you manage and categorize your contacts.

#### 3.9.1 Notes, Tags, and Reminders
**Location:** `handlers/contact_handlers.py`

| Command | Description |
|---------|-------------|
| `/note <name> <note>` | Add personal notes to contact |
| `/tag <name> <tags>` | Add comma-separated tags |
| `/remind <name> <date>` | Set follow-up reminder |

#### 3.9.2 Natural Language Queries
**Location:** `handlers/conversation_handlers.py`

The `/ask` command allows natural language questions about your network:

```
User: /ask Who works at TechCorp?
Bot:  Found 3 contacts at TechCorp:
      • John Smith (CEO)
      • Sarah Lee (CTO)
      • Mike Johnson (VP Engineering)

User: /ask How many founders do I know?
Bot:  You have 18 contacts classified as Founders.

User: /ask Show me contacts in San Francisco
Bot:  Found 7 contacts in San Francisco:
      [Lists contacts with details]
```

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
| `save_contact` | Save to Airtable |
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

### 5.3 CrewAI Agent System

Rover uses CrewAI for orchestrating specialized AI agents that collaborate to handle complex tasks.

#### 5.3.1 Agent Architecture
**Location:** `agents/` directory

```
┌─────────────────────────────────────────────────────────────────┐
│                      CREWAI ORCHESTRATION                       │
└─────────────────────────────────────────────────────────────────┘
         │
         ├──► Contact Management Agent (CRUD operations)
         ├──► Enrichment Agent (Web research)
         ├──► Input Processing Agent (Text/Voice/Image)
         ├──► Classification Agent (Founder/Investor/Enabler)
         ├──► Reporting Agent (Statistics/Analytics)
         ├──► Evaluation Agent (Quality assessment)
         └──► Troubleshooting Agent (Error handling)
```

#### 5.3.2 Specialized Agents

| Agent | Role | Capabilities |
|-------|------|--------------|
| **Contact Management** | Data Entry Specialist | CRUD operations, field validation, Airtable integration |
| **Enrichment Agent** | Research Specialist | Web search, LinkedIn discovery, company research, data enhancement |
| **Input Processing** | Data Extraction Specialist | Text parsing, voice transcription, OCR extraction, bulk file processing |
| **Classification Agent** | Categorization Specialist | Contact type classification (Founder/Investor/Enabler), industry detection |
| **Reporting Agent** | Analytics Specialist | Statistics generation, report creation, export functionality |
| **Evaluation Agent** | Quality Assurance Specialist | Data quality assessment, completeness checking, validation |
| **Troubleshooting Agent** | Problem Resolution Specialist | Error handling, edge case management, recovery |

#### 5.3.3 Crew Definitions
**Location:** `crews/` directory

Crews are teams of agents that collaborate on complex workflows:

| Crew | Agents | Purpose |
|------|--------|---------|
| **Contact Crew** | Contact Management, Classification | Handle contact add/update operations |
| **Enrichment Crew** | Enrichment, Classification | Research and enhance contact data |
| **Input Processing Crew** | Input Processing, Contact Management | Handle multi-format input |
| **Reporting Crew** | Reporting, Evaluation | Generate analytics and reports |

#### 5.3.4 Agent Tools
**Location:** `services/agent_tools.py`

Each agent has access to specific tools:

```python
# Contact Management Tools
add_contact, update_contact, save_contact, delete_contact

# Enrichment Tools
search_web, search_linkedin, enrich_contact, summarize_results

# Data Tools
get_contact, list_contacts, search_contacts, export_contacts

# Analytics Tools
track_operation, log_feature_usage, evaluate_quality
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
├── main.py                              # Entry point, bot initialization
├── config.py                            # Configuration, environment variables
├── requirements.txt                     # Python dependencies
├── env.template                         # Environment template file
│
├── handlers/                            # Telegram message/command handlers
│   ├── __init__.py
│   ├── message_handler.py               # Main message routing
│   ├── conversation_engine.py           # Multi-turn conversation logic
│   ├── conversation_handlers.py         # /start, /help, /ask
│   ├── contact_handlers.py              # /add, /view, /list, /update, /delete
│   ├── enrichment_handlers.py           # /enrich, /research, /linkedin
│   ├── matchmaker_handlers.py           # /match, /matches, /clear_matches
│   ├── outreach_handlers.py             # /draft, /send_approved, /drafts
│   ├── report_handlers.py               # /stats, /report, /export
│   ├── analytics_handlers.py            # /dashboard, /analytics
│   ├── evaluation_handlers.py           # /eval commands
│   └── input_handlers.py                # Voice, photo, document processing
│
├── services/                            # Business logic services
│   ├── __init__.py
│   ├── agent.py                         # Rover AI Agent (OpenAI function calling)
│   ├── agent_tools.py                   # Agent tool implementations
│   ├── ai_service.py                    # OpenAI/Gemini API wrapper
│   ├── enrichment.py                    # EnrichmentService (Tavily/SerpAPI)
│   ├── matchmaker.py                    # MatchmakerService (CrewAI)
│   ├── outreach.py                      # OutreachService (Email drafting)
│   ├── email_service.py                 # SMTP email sending
│   ├── bulk_import.py                   # BulkImportService (CSV/Excel)
│   ├── contact_memory.py                # Session state management
│   ├── airtable_service.py              # Airtable integration
│   ├── classification.py                # Contact type classification
│   └── conversation_ai.py               # Intent classification
│
├── agents/                              # CrewAI agent definitions
│   ├── __init__.py
│   ├── contact_agent.py                 # Contact management agent
│   ├── enrichment_agent.py              # Research/enrichment agent
│   ├── input_processing_agent.py        # Multi-format input agent
│   ├── classification_agent.py          # Categorization agent
│   ├── reporting_agent.py               # Analytics agent
│   ├── evaluation_agent.py              # Quality assessment agent
│   ├── troubleshooting_agent.py         # Error handling agent
│   └── data_enrichment_agent.py         # Data utilities
│
├── crews/                               # CrewAI crew orchestration
│   ├── __init__.py
│   ├── contact_crew.py                  # Contact operations crew
│   ├── enrichment_crew.py               # Research crew
│   ├── input_processing_crew.py         # Input handling crew
│   └── reporting_crew.py                # Analytics crew
│
├── data/                                # Data models and schemas
│   ├── __init__.py
│   └── schema.py                        # Contact, Match, Draft models (Pydantic)
│
├── analytics/                           # Analytics and monitoring
│   ├── __init__.py
│   └── tracker.py                       # Operation tracking, metrics
│
├── app_logging/                         # Logging utilities
│   ├── __init__.py
│   └── logger.py                        # Structured logging, change tracking
│
├── training/                            # Training data
│   └── enrichment_training_data.jsonl   # Training examples
│
├── docs/                                # Documentation
│   ├── Rover_V01_Project_Plan.md        # This document
│   ├── USAGE.md                         # User guide
│   ├── ARCHITECTURE.md                  # System architecture
│   ├── SETUP.md                         # Installation guide
│   ├── DEVELOPER.md                     # Development guide
│   ├── API.md                           # Service API reference
│   ├── AGENTS.md                        # Agent documentation
│   ├── CREWS.md                         # Crew documentation
│   ├── TOOLS.md                         # Tools documentation
│   ├── TROUBLESHOOTING.md               # Common issues
│   ├── IMPROVEMENT_PLAN.md              # Future roadmap
│   └── CHANGELOG.md                     # Version history
│
├── logs/                                # Runtime logs
│   └── analytics.db                     # SQLite analytics database
│
└── tests/                               # Test files (if applicable)
    └── ...
```

---

## API Dependencies & Configuration

### External APIs

| Service | Purpose | Environment Variable |
|---------|---------|---------------------|
| **Telegram Bot API** | Messaging interface | `TELEGRAM_BOT_TOKEN` |
| **OpenAI API** | Agent reasoning, Whisper, GPT-4 Vision | `OPENAI_API_KEY` |
| **Google Gemini API** | Alternative AI provider | `GEMINI_API_KEY` |
| **Tavily API** | Web search for enrichment | `TAVILY_API_KEY` |
| **SerpAPI** | Alternative web search | `SERPAPI_API_KEY` |
| **Airtable API** | Data storage | `AIRTABLE_PAT`, `AIRTABLE_BASE_ID` |

### Configuration Options
**Location:** `config.py`

#### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | `123456:ABC-DEF...` |
| `AIRTABLE_PAT` | Airtable Personal Access Token | `pat...` |
| `AIRTABLE_BASE_ID` | Airtable Base ID | `app...` |
| `OPENAI_API_KEY` or `GEMINI_API_KEY` | At least one AI provider required | `sk-...` |

#### AI Provider Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Primary AI provider | `openai` |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4` |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.0-flash-exp` |
| `AI_TEMPERATURE` | Response creativity (0-1) | `0.7` |
| `AI_MAX_TOKENS` | Maximum response tokens | `2000` |

#### SMTP Email Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password (use app password for Gmail) | - |
| `SMTP_FROM_EMAIL` | Sender email address | - |
| `SENDER_NAME` | Display name for sender | - |

#### Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTO_ENRICH_ENABLED` | Auto-enrich new contacts | `true` |
| `AUTO_CLASSIFY_ENABLED` | Auto-classify contact type | `true` |
| `VOICE_TRANSCRIPTION_ENABLED` | Enable voice message processing | `true` |
| `IMAGE_OCR_ENABLED` | Enable business card OCR | `true` |
| `EMAIL_ENABLED` | Enable email outreach | `true` |

#### Session Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSION_TIMEOUT_SECONDS` | Session timeout duration | `1800` (30 min) |
| `SESSION_CONTINUATION_SECONDS` | Time to continue session | `300` (5 min) |
| `SESSION_MEMORY_EXPIRY_MINUTES` | Memory retention time | `60` |
| `GUIDED_PROMPTS_ENABLED` | Show guided prompts | `true` |
| `MAX_PROMPTS_PER_CONTACT` | Max prompts per contact | `5` |

#### Analytics Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ANALYTICS_ENABLED` | Enable analytics tracking | `true` |
| `ANALYTICS_DB_PATH` | SQLite database path | `logs/analytics.db` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DEBUG_MODE` | Enable debug mode | `false` |

### Sample `.env` File

```env
# Required
TELEGRAM_BOT_TOKEN=your-bot-token
AIRTABLE_PAT=your-personal-access-token
AIRTABLE_BASE_ID=your-base-id
AIRTABLE_CONTACTS_TABLE=Contacts
AIRTABLE_MATCHES_TABLE=Matches
AIRTABLE_DRAFTS_TABLE=Drafts

# AI Provider (at least one required)
OPENAI_API_KEY=sk-your-openai-key
GEMINI_API_KEY=your-gemini-key

# Web Search
TAVILY_API_KEY=your-tavily-key

# Email (optional - for outreach)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SENDER_NAME=Your Name

# Optional Settings
AI_PROVIDER=openai
DEBUG_MODE=false
```

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

## Complete Commands Reference

### Contact Management Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and overview | `/start` |
| `/help` | Full command reference | `/help` |
| `/add <info>` | Add new contact | `/add John from TechCorp` |
| `/view <name>` | View contact details | `/view John` |
| `/list` | List all contacts (paginated) | `/list` |
| `/search <query>` | Search contacts | `/search fintech` |
| `/update <name> <field> <value>` | Update contact field | `/update John email john@tech.com` |
| `/delete <name>` | Remove contact | `/delete John` |

### Enrichment Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/enrich <name>` | Enrich individual contact | `/enrich John` |
| `/enrich all` | Bulk enrich contacts | `/enrich all` |
| `/research <company>` | Research company info | `/research TechCorp` |
| `/linkedin <name>` | Find LinkedIn profile | `/linkedin John` |

### Matchmaker Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/match` | Run founder-investor matching | `/match` |
| `/matches` | View saved matches | `/matches` |
| `/clear_matches` | Clear all matches | `/clear_matches` |

### Outreach Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/draft` | Generate email drafts (score >= 70) | `/draft` |
| `/draft <score>` | Generate drafts with custom min score | `/draft 80` |
| `/send_approved` | Send approved emails | `/send_approved` |
| `/drafts` | View draft statistics | `/drafts` |
| `/clear_drafts` | Clear all drafts | `/clear_drafts` |

### Statistics & Reporting Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/stats` | Network statistics overview | `/stats` |
| `/stats by <field>` | Group stats by field | `/stats by company` |
| `/report <name>` | Detailed contact report | `/report John` |
| `/report all` | Network-wide analysis | `/report all` |
| `/export` | Export contacts to CSV | `/export` |

### Organization Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/note <name> <note>` | Add note to contact | `/note John Met at conference` |
| `/tag <name> <tags>` | Add tags to contact | `/tag John fintech,investor` |
| `/remind <name> <date>` | Set follow-up reminder | `/remind John 2024-02-15` |
| `/ask <question>` | Natural language query | `/ask Who works at TechCorp?` |

### Analytics Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/dashboard` | System status dashboard | `/dashboard` |
| `/analytics` | Usage analytics | `/analytics` |
| `/analytics operations` | Operation statistics | `/analytics operations` |
| `/analytics features` | Feature usage | `/analytics features` |
| `/analytics performance` | Performance metrics | `/analytics performance` |
| `/analytics export <days>` | Export analytics JSON | `/analytics export 30` |

### Evaluation Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/eval` | Data quality evaluation | `/eval` |
| `/eval operations` | Operation success rates | `/eval operations` |
| `/eval quality` | Completeness assessment | `/eval quality` |
| `/eval agents` | Agent performance | `/eval agents` |

### Input Methods (Non-Command)

| Input Type | Description |
|------------|-------------|
| **Text Message** | Natural language contact info |
| **Voice Message** | Audio transcribed and parsed |
| **Photo** | Business card OCR extraction |
| **Document (CSV/Excel)** | Bulk contact import |

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

### Bulk Import Flow
```
User: [Uploads contacts.csv]
Bot:  📥 Processing contacts.csv...
      This may take a moment for large files.

Bot:  ✅ Import Complete!

      📊 Results:
      • Total rows: 25
      • Added: 18
      • Updated: 5
      • Skipped: 2
      • Failed: 0

      Use /list to see your contacts.
```

---

## Future Enhancements (V03 Roadmap)

### Planned Features
1. **Email Finder** - Integrate email discovery APIs (Hunter.io, Apollo.io)
2. **News Alerts** - Track contact/company news automatically
3. **Relationship Scoring** - Auto-calculate relationship strength based on interactions
4. **Advanced Analytics** - Network visualization and relationship graphs
5. **CRM Integration** - Sync with Salesforce, HubSpot, Pipedrive
6. **Calendar Integration** - Schedule follow-ups directly
7. **LinkedIn Automation** - Auto-connect and message via LinkedIn API
8. **Multi-User Support** - Team collaboration features
9. **Custom Classification** - User-defined contact categories
10. **Webhook Support** - Real-time notifications to external services

### Completed in V2.x

| Feature | Version | Description |
|---------|---------|-------------|
| **Bulk Import** | V2.2.0 | CSV/Excel bulk contact import with auto header detection |
| **Pydantic Validation** | V2.1.0 | Data integrity and validation |
| **Export** | V2.0.0 | CSV export functionality |
| **Voice Input** | V2.0.0 | Voice message transcription via Whisper |
| **Image OCR** | V2.0.0 | Business card extraction via GPT-4 Vision |
| **Analytics Dashboard** | V2.0.0 | Operation tracking and metrics |
| **Natural Language Queries** | V2.0.0 | /ask command for network questions |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **V2.2.0** | 2026-01-15 | Bulk Contact Import - CSV/Excel support with auto header detection, smart duplicate handling |
| **V2.1.0** | 2026-01-15 | Pydantic validation, bug fixes for contact saving, matchmaker markdown fixes |
| **V2.0.0** | 2026-01-11 | Smarter Agent - deferred saving, conversation state machine, cancel support, voice input, OCR, analytics |
| V01.2 | 2026-01-13 | Added Outreach Agent (email drafting & sending via SMTP) |
| V01.1 | 2026-01-13 | Added Matchmaker system (Founder-Investor matching with scoring) |
| V01 | 2026-01-13 | Initial release with enrichment system, contact management |

---

## Summary of All Features

| Category | Feature | Status |
|----------|---------|--------|
| **Contact Management** | Add/View/List/Update/Delete | ✅ |
| **Input Methods** | Text, Voice, Image (OCR), Bulk (CSV/Excel) | ✅ |
| **Enrichment** | Web search, LinkedIn discovery, auto-classification | ✅ |
| **Matchmaker** | Founder-Investor compatibility scoring | ✅ |
| **Outreach** | Email draft generation, SMTP sending | ✅ |
| **Statistics** | Network stats, reports, CSV export | ✅ |
| **Analytics** | Dashboard, operation tracking, performance | ✅ |
| **Organization** | Notes, tags, reminders, natural queries | ✅ |
| **AI Agents** | 7 specialized CrewAI agents | ✅ |
| **Data Storage** | Airtable (3 tables), SQLite analytics | ✅ |

---

**Built with:** Python 3.12, CrewAI 0.28+, OpenAI GPT-4, Google Gemini, Tavily API, SerpAPI, Airtable API, python-telegram-bot 20.7+

**Documentation updated:** January 19, 2026
