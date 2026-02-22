# Rover Network Agent — Architecture

## System Overview

Rover is a modular, AI-powered network management agent built on CrewAI for agent orchestration. Users interact via Telegram (text, voice, images) or a web dashboard. Data is stored in Airtable (primary) with SQLite for analytics and interactions, and JSON as a fallback.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                │
│                                                                             │
│   ┌─────────────┐    ┌──────────────────┐    ┌───────────────────────────┐  │
│   │  Telegram    │    │  Web Dashboard   │    │  Bulk Import (CSV/Excel) │  │
│   │  Bot API     │    │  localhost:8080   │    │  /import command         │  │
│   └──────┬──────┘    └────────┬─────────┘    └────────────┬──────────────┘  │
└──────────┼────────────────────┼────────────────────────────┼─────────────────┘
           │                    │                            │
           ▼                    ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          ENTRY POINTS & ROUTING                             │
│                                                                             │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│   │    main.py        │    │  dashboard/      │    │  services/           │  │
│   │  Telegram bot     │    │  server.py       │    │  bulk_import.py      │  │
│   │  message router   │    │  REST API server │    │  CSV/Excel parser    │  │
│   └────────┬─────────┘    └──────────────────┘    └──────────────────────┘  │
└────────────┼────────────────────────────────────────────────────────────────-┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        CONVERSATION ENGINE                                  │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │  handlers/conversation_engine.py                                      │ │
│   │  • Intent classification (add, update, search, view, enrich, etc.)   │ │
│   │  • Entity extraction from natural language                           │ │
│   │  • Session-based contact drafting ("shopping cart" model)             │ │
│   │  • Context-aware follow-up prompts                                   │ │
│   └───────────────────────────┬───────────────────────────────────────────┘ │
│                               │                                             │
│   Routes to specialized handlers:                                           │
│   ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐ │
│   │ Contact  │ │ Enrichment│ │ Matchmaker │ │ Outreach │ │ Analytics    │ │
│   │ Handlers │ │ Handlers  │ │ Handlers   │ │ Handlers │ │ Handlers     │ │
│   └────┬─────┘ └─────┬─────┘ └─────┬──────┘ └────┬─────┘ └──────┬───────┘ │
└────────┼─────────────┼─────────────┼─────────────┼───────────────┼──────────┘
         │             │             │             │               │
         ▼             ▼             ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          AI AGENT LAYER (CrewAI)                            │
│                                                                             │
│   ┌─── Crews (orchestration) ──────────────────────────────────────────┐   │
│   │  Contact Crew │ Enrichment Crew │ Research Crew │ Reporting Crew   │   │
│   │  Input Crew   │ Researcher Crew                                    │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─── Agents (specialized workers) ──────────────────────────────────┐   │
│   │                                                                    │   │
│   │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐   │   │
│   │  │ Contact      │  │ Enrichment       │  │ Classification     │   │   │
│   │  │ Agent        │  │ Agent            │  │ Agent              │   │   │
│   │  │ CRUD ops     │  │ Web research     │  │ Type assignment    │   │   │
│   │  └──────────────┘  └──────────────────┘  └────────────────────┘   │   │
│   │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐   │   │
│   │  │ Research     │  │ Input            │  │ Reporting          │   │   │
│   │  │ Agent        │  │ Agent            │  │ Agent              │   │   │
│   │  │ Deep search  │  │ Text/voice/image │  │ Stats & reports    │   │   │
│   │  └──────────────┘  └──────────────────┘  └────────────────────┘   │   │
│   │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐   │   │
│   │  │ Researcher   │  │ Data Enrichment  │  │ Evaluation         │   │   │
│   │  │ Agent        │  │ Agent            │  │ Agent              │   │   │
│   │  │ Multi-source │  │ Structured data  │  │ Quality checks     │   │   │
│   │  └──────────────┘  └──────────────────┘  └────────────────────┘   │   │
│   │  ┌──────────────┐                                                  │   │
│   │  │ Trouble-     │                                                  │   │
│   │  │ shooting     │                                                  │   │
│   │  │ Agent        │                                                  │   │
│   │  └──────────────┘                                                  │   │
│   └────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SERVICES LAYER                                    │
│                                                                             │
│   ┌─── Core Services ─────────────────────────────────────────────────┐   │
│   │                                                                    │   │
│   │  ┌────────────────────┐  ┌────────────────────┐                   │   │
│   │  │ ai_service.py      │  │ conversation_ai.py │                   │   │
│   │  │ GPT-4 / Gemini     │  │ Intent & entity    │                   │   │
│   │  │ orchestration      │  │ extraction         │                   │   │
│   │  └────────────────────┘  └────────────────────┘                   │   │
│   │  ┌────────────────────┐  ┌────────────────────┐                   │   │
│   │  │ airtable_service   │  │ local_storage.py   │                   │   │
│   │  │ Primary data store │  │ Fallback storage   │                   │   │
│   │  └────────────────────┘  └────────────────────┘                   │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─── Feature Services ──────────────────────────────────────────────┐   │
│   │                                                                    │   │
│   │  enrichment.py         research_engine.py       classification.py  │   │
│   │  auto_enrichment.py    ai_research_synthesizer   linkedin_scraper/ │   │
│   │  matchmaker.py         introduction_service.py   outreach.py       │   │
│   │  email_service.py      digest_service.py         transcription.py  │   │
│   │  interaction_tracker   contact_memory.py         user_session.py   │   │
│   │  conversation_store    bulk_import.py                              │   │
│   └────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           TOOLS LAYER                                       │
│                                                                             │
│   ai_tool.py          airtable_tool.py       deep_research_tool.py         │
│   linkedin_scraper    serpapi_tool.py         transcription_tool.py         │
│   validation_tool.py                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL APIS & STORAGE                              │
│                                                                             │
│   ┌─── AI Models ──────┐  ┌─── Search ─────┐  ┌─── Communication ──────┐  │
│   │  OpenAI GPT-4      │  │  Tavily API     │  │  Telegram Bot API      │  │
│   │  OpenAI Whisper     │  │  LinkedIn       │  │  SMTP (Gmail)          │  │
│   │  GPT-4 Vision      │  │  Scraper        │  │                        │  │
│   │  Google Gemini      │  │                 │  │                        │  │
│   └────────────────────┘  └─────────────────┘  └────────────────────────┘  │
│                                                                             │
│   ┌─── Data Stores ────────────────────────────────────────────────────┐   │
│   │                                                                    │   │
│   │  ┌─────────────────────────────────────────────────────────────┐   │   │
│   │  │                    Airtable (Primary)                       │   │   │
│   │  │   Contacts Table  │  Matches Table  │  Drafts Table        │   │   │
│   │  └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                    │   │
│   │  ┌─────────────────────────────────────────────────────────────┐   │   │
│   │  │                    SQLite (Local)                            │   │   │
│   │  │   analytics.db  │  interactions.db  │  conversations.db    │   │   │
│   │  └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                    │   │
│   │  JSON fallback (when Airtable unavailable)                        │   │
│   └────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY & LOGGING                                 │
│                                                                             │
│   ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐ ┌────────────┐ │
│   │ operation_logger │ │ agent_logger    │ │ error_logger │ │ change_log │ │
│   │ operations.log   │ │ agents.log      │ │ errors.log   │ │ changes.log│ │
│   └─────────────────┘ └─────────────────┘ └──────────────┘ └────────────┘ │
│                                                                             │
│   analytics/tracker.py  │  analytics/metrics.py  │  performance_monitor.py  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
  User Message (text/voice/image)
       │
       ▼
  Telegram Bot → main.py
       │
       ▼
  Conversation Engine (intent classification)
       │
       ├──→ /add    → Contact Agent  → Airtable
       ├──→ /enrich → Enrichment Agent → Tavily/LinkedIn → Airtable
       ├──→ /match  → Matchmaker → GPT-4 scoring → Airtable (Matches)
       ├──→ /draft  → Outreach Service → GPT-4 → Airtable (Drafts)
       ├──→ /send   → Email Service → SMTP → Gmail
       ├──→ /stats  → Reporting Agent → Airtable + SQLite
       ├──→ /view   → Contact Agent → Airtable → formatted card
       ├──→ /remind → Interaction Tracker → SQLite
       └──→ /digest → Digest Service → Airtable + SQLite → summary
```

## Relationship Scoring Algorithm

```
  Base Score: 50 (new contact)
       │
       ├── +20  if enriched (has LinkedIn/company data)
       ├── +10  per interaction (capped at +40)
       ├── +15  if introduced someone
       ├── +10  if introduced by someone
       ├── -5   per week of no interaction
       ├── -20  if >3 months dormant
       └── min: 10, max: 100

  Stage thresholds:
       0-20:  lost
      21-40:  dormant
      41-60:  new
      61-80:  building
     81-100:  strong
```

## Component Details

### 1. User Interfaces

| Interface | Technology | Purpose |
|-----------|------------|---------|
| Telegram Bot | python-telegram-bot | Primary user interaction (text, voice, images) |
| Web Dashboard | Vanilla HTML/JS + Chart.js | Analytics visualization, contact browsing |
| Bulk Import | CSV/Excel parser | Mass contact ingestion |

### 2. Conversation Engine

The conversation engine (`handlers/conversation_engine.py`) is the central router:

- **Intent Classification**: Determines user intent via GPT-4 (add, update, search, view, enrich, match, etc.)
- **Entity Extraction**: Pulls contact fields from natural language
- **Session Management**: "Shopping cart" model — accumulates data across messages before saving
- **Duplicate Detection**: Checks name/email/phone before creating new contacts

### 3. CrewAI Agent Layer

#### Crews (Orchestration)
| Crew | Agents Used | Purpose |
|------|------------|---------|
| Contact Crew | Contact, Classification | CRUD with auto-classification |
| Enrichment Crew | Enrichment, Data Enrichment | Web research + structured extraction |
| Research Crew | Research | Deep multi-source investigation |
| Researcher Crew | Researcher | Fast single-source lookups |
| Input Crew | Input | Text/voice/image processing |
| Reporting Crew | Reporting | Stats and report generation |

#### Agents (10 total)
| Agent | Role | Primary Tools |
|-------|------|---------------|
| Contact Agent | Data Entry Specialist | Airtable, Validation |
| Enrichment Agent | Research Specialist | Tavily, AI |
| Data Enrichment Agent | Structured Data | Tavily, LinkedIn |
| Classification Agent | Categorization | AI, Validation |
| Research Agent | Deep Search | Tavily, LinkedIn, AI |
| Researcher Agent | Multi-Source | Deep Research, AI |
| Input Agent | Data Extraction | Transcription, OCR, AI |
| Reporting Agent | Analytics | Airtable, AI |
| Evaluation Agent | Quality Assurance | Validation, Airtable |
| Troubleshooting Agent | Problem Resolution | All tools |

### 4. Services Layer

#### Core Services
- **ai_service.py**: Orchestrates GPT-4 and Gemini API calls with fallback
- **airtable_service.py**: Primary CRUD for Contacts, Matches, Drafts tables
- **local_storage.py**: JSON fallback when Airtable is unavailable
- **conversation_ai.py**: Intent classification and entity extraction

#### Feature Services
| Service | File | Purpose |
|---------|------|---------|
| Enrichment | enrichment.py | Single/bulk contact enrichment |
| Auto-Enrichment | auto_enrichment.py | Automatic enrichment on new contacts |
| Research Engine | research_engine.py | Multi-source deep research |
| AI Synthesizer | ai_research_synthesizer.py | Cross-validates research findings |
| LinkedIn Scraper | linkedin_scraper/ | Profile and company data extraction |
| Classification | classification.py | Contact type assignment |
| Matchmaker | matchmaker.py | Founder-investor pairing algorithm |
| Introduction | introduction_service.py | Intro suggestions and tracking |
| Outreach | outreach.py | Email draft generation |
| Email | email_service.py | SMTP sending |
| Digest | digest_service.py | Daily/weekly briefings |
| Interaction Tracker | interaction_tracker.py | Logs touchpoints, manages follow-ups |
| Transcription | transcription.py | Whisper voice-to-text |
| Bulk Import | bulk_import.py | CSV/Excel ingestion |
| Contact Memory | contact_memory.py | Per-user session state |
| User Session | user_session.py | Session lifecycle management |
| Conversation Store | conversation_store.py | Message history persistence |

### 5. Tools Layer

Thin wrappers that expose services to CrewAI agents:

| Tool | Wraps |
|------|-------|
| ai_tool.py | ai_service (GPT-4/Gemini) |
| airtable_tool.py | airtable_service |
| deep_research_tool.py | research_engine |
| linkedin_scraper_tool.py | linkedin_scraper |
| serpapi_tool.py | Tavily web search |
| transcription_tool.py | Whisper transcription |
| validation_tool.py | Data validation rules |

### 6. Data Stores

#### Airtable (Primary — 3 tables)
- **Contacts**: 35+ fields per contact (identity, professional, relationship, research)
- **Matches**: Founder-investor pairings with scores and analysis
- **Drafts**: Email templates with approval workflow

#### SQLite (Local — 3 databases)
- **analytics.db**: Operation tracking, feature usage, agent activity
- **interactions.db**: Interaction history, follow-ups
- **conversations.db**: Telegram message history

#### JSON Fallback
- Activated when Airtable is unreachable
- Syncs back to Airtable when connection restores

### 7. Observability

- **operations.log**: All CRUD and enrichment operations
- **agents.log**: CrewAI agent activity and decisions
- **errors.log**: Exceptions with stack traces
- **changes.log**: Feature additions and system changes
- **Analytics tracker**: Real-time metrics collection
- **Performance monitor**: Execution time and throughput tracking
- Log rotation: 10MB max per file, 5 backups

## External API Dependencies

| API | Purpose | Required |
|-----|---------|----------|
| Telegram Bot API | User interface | Yes |
| OpenAI GPT-4 | Intent classification, drafting, matching | Yes (or Gemini) |
| OpenAI Whisper | Voice transcription | Optional |
| GPT-4 Vision | Business card OCR | Optional |
| Google Gemini | AI fallback model | Optional |
| Tavily | Web search for enrichment | Optional |
| LinkedIn Scraper | Profile data extraction | Optional |
| SMTP (Gmail) | Email outreach sending | Optional |
| Airtable | Primary data storage | Yes |

## Configuration

All configuration lives in `.env` and `config.py`. Feature flags allow toggling:
- `AUTO_ENRICH_ENABLED` — enrich new contacts automatically
- `AUTO_CLASSIFY_ENABLED` — classify contacts on creation
- `VOICE_TRANSCRIPTION_ENABLED` — process voice messages
- `IMAGE_OCR_ENABLED` — process business card images
- `EMAIL_ENABLED` — email outreach capability
- `LINKEDIN_SCRAPER_ENABLED` — LinkedIn integration

## Dashboard API Endpoints

The web dashboard (`dashboard/server.py`) exposes:

| Endpoint | Source | Returns |
|----------|--------|---------|
| `/api/overview` | SQLite | Operation counts, follow-up count |
| `/api/contacts` | Airtable | All contacts + classifications, stages, industries, scores |
| `/api/introductions` | Airtable | Introduction list + status counts |
| `/api/interactions` | SQLite | Timeline, by-type, by-contact, follow-ups |
| `/api/intelligence` | Airtable | Network health, enrichment rate, email coverage |
| `/api/conversations` | SQLite | Message history, hourly distribution |
