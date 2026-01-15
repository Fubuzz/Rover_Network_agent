# Architecture Documentation

## System Overview

The Telegram Network Nurturing Agent is built on a modular, agent-based architecture using CrewAI for AI orchestration. The system processes user inputs through Telegram, orchestrates AI agents for various tasks, stores data in Google Sheets, and tracks all operations for analytics.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM USER                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BOT (python-telegram-bot)          │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │   Contact   │ │ Enrichment  │ │   Report    │ │   Input   │  │
│  │  Handlers   │ │  Handlers   │ │  Handlers   │ │ Handlers  │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CREWAI ORCHESTRATION                      │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                          CREWS                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Contact   │ │ Enrichment  │ │   Input     │          │ │
│  │  │    Crew     │ │    Crew     │ │   Crew      │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                         AGENTS                              │ │
│  │  ┌─────────┐ ┌──────────┐ ┌───────┐ ┌──────────────┐      │ │
│  │  │ Contact │ │Enrichment│ │ Input │ │Classification│      │ │
│  │  │  Agent  │ │  Agent   │ │ Agent │ │    Agent     │      │ │
│  │  └─────────┘ └──────────┘ └───────┘ └──────────────┘      │ │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────────────────┐       │ │
│  │  │Reporting│ │Evaluation│ │   Troubleshooting     │       │ │
│  │  │  Agent  │ │  Agent   │ │       Agent           │       │ │
│  │  └─────────┘ └──────────┘ └───────────────────────┘       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                           TOOLS                                  │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │Google Sheets│ │  SerpAPI    │ │    AI       │ │Validation │  │
│  │    Tool     │ │   Tool      │ │   Tool      │ │   Tool    │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                          SERVICES                                │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │Google Sheets│ │  AI Service │ │ Enrichment  │ │Transcribe │  │
│  │  Service    │ │(OpenAI/Gem.)│ │  Service    │ │  Service  │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Google Sheets  │    │   External APIs  │    │ Analytics DB    │
│   (Data Store)  │    │ (Search, AI)     │    │   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Component Details

### 1. Telegram Bot Layer

The entry point for all user interactions. Built with `python-telegram-bot`:

- **Command Handlers**: Process specific commands (/add, /view, etc.)
- **Message Handlers**: Process text, voice, images, documents
- **Error Handler**: Catches and logs exceptions

### 2. CrewAI Orchestration Layer

Manages AI agent collaboration:

#### Crews
- **Contact Crew**: Manages contact operations with validation and classification
- **Enrichment Crew**: Handles web research and data enrichment
- **Input Processing Crew**: Processes various input formats
- **Reporting Crew**: Generates reports and statistics

#### Agents
Each agent has a specific role, goal, backstory, and set of tools:

| Agent | Role | Primary Tools |
|-------|------|---------------|
| Contact Agent | Data Entry Specialist | Google Sheets, Validation |
| Enrichment Agent | Research Specialist | SerpAPI, AI |
| Input Agent | Data Extraction | Transcription, OCR, AI |
| Classification Agent | Categorization | AI, Validation |
| Reporting Agent | Analytics Specialist | Google Sheets, AI |
| Evaluation Agent | Quality Assurance | Validation, Google Sheets |
| Troubleshooting Agent | Problem Resolution | All tools |

### 3. Tools Layer

CrewAI tools wrap services for agent use:

- **Google Sheets Tool**: Contact CRUD operations
- **SerpAPI Tool**: Web search capabilities
- **AI Tool**: Classification, parsing, OCR
- **Validation Tool**: Data validation
- **Transcription Tool**: Voice transcription

### 4. Services Layer

Core business logic:

- **Google Sheets Service**: Manages spreadsheet operations
- **AI Service**: Handles OpenAI/Gemini API calls
- **Enrichment Service**: Web search and data enrichment
- **Classification Service**: Contact categorization
- **Transcription Service**: Voice-to-text

### 5. Data Layer

- **Google Sheets**: Primary contact data storage
- **SQLite Analytics DB**: Operation tracking, metrics, logs

## Data Flow

### Adding a Contact (Text Input)

```
1. User sends: "Add John Doe, CEO at TechCorp, john@techcorp.com"
2. Text Handler receives message
3. Input Processing Crew activated:
   a. Input Agent parses text → extracts contact info
   b. Contact Agent validates and stores → adds to Google Sheets
   c. Classification Agent classifies → determines "founder"
4. Response sent to user
5. Operation tracked in analytics DB
```

### Enriching a Contact

```
1. User sends: "/enrich John Doe"
2. Enrichment Handler receives command
3. Enrichment Crew activated:
   a. Contact Agent retrieves current data
   b. Enrichment Agent searches web (SerpAPI)
   c. AI Tool summarizes findings
   d. Evaluation Agent validates enriched data
   e. Contact Agent updates record
4. Enrichment report sent to user
5. Operation tracked in analytics DB
```

## Design Decisions

### Why CrewAI?
- **Specialization**: Each agent focuses on specific tasks
- **Collaboration**: Agents work together on complex operations
- **Extensibility**: Easy to add new agents and capabilities
- **Evaluation**: Built-in mechanisms for quality assessment

### Why Google Sheets?
- **Accessibility**: Users can view/edit data directly
- **No Infrastructure**: No database server required
- **Sharing**: Easy to share with team members
- **Integration**: Works with other Google services

### Why SQLite for Analytics?
- **Lightweight**: No separate server needed
- **Fast**: Local queries are quick
- **Portable**: Single file database
- **Sufficient**: Handles expected query volumes

## Scalability Considerations

### Current Limitations
- Single-user focus (no authentication)
- Polling-based (vs. webhooks)
- Synchronous processing
- Rate limits on external APIs

### Future Improvements
- Multi-user support with database isolation
- Webhook-based updates for efficiency
- Async processing for heavy operations
- Caching for frequently accessed data
- Queue-based processing for rate limiting
