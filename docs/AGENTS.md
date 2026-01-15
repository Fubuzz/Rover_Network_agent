# Agents Documentation

This document describes the CrewAI agents that power the Network Nurturing Agent.

## Overview

The system uses 7 specialized AI agents, each with specific roles and capabilities.

## Agent Architecture

Each agent has:
- **Role**: The agent's job title
- **Goal**: What the agent aims to accomplish
- **Backstory**: Context that shapes behavior
- **Tools**: Set of tools the agent can use
- **LLM**: Language model configuration

## Agent Definitions

### 1. Contact Management Agent

**Role**: Data Entry Specialist

**Goal**: Accurately add, update, and manage contact information in the database

**Tools**:
- Google Sheets Tool
- Validation Tool

**Responsibilities**:
- Adding new contacts
- Updating existing contacts
- Deleting contacts
- Searching contacts
- Validating data before storage

**Example Tasks**:
```python
agent.add_contact({
    "name": "John Doe",
    "email": "john@example.com",
    "company": "TechCorp"
})
```

---

### 2. Enrichment Agent

**Role**: Research Specialist

**Goal**: Gather additional information about contacts through web research

**Tools**:
- SerpAPI Tool
- AI Tool
- Google Sheets Tool

**Responsibilities**:
- Web searches for contact information
- LinkedIn profile discovery
- Company research
- News gathering
- Summarizing research findings

**Example Tasks**:
```python
agent.enrich_contact("John Doe")
agent.research_company("TechCorp")
```

---

### 3. Input Processing Agent

**Role**: Data Extraction Specialist

**Goal**: Extract structured contact information from various input formats

**Tools**:
- AI Tool
- Transcription Tool
- Validation Tool

**Responsibilities**:
- Parsing natural language text
- Processing voice transcripts
- OCR from images
- Bulk import processing
- Data normalization

**Example Tasks**:
```python
agent.process_text("John Doe, CEO at TechCorp")
agent.process_voice(transcript)
agent.process_image(image_data)
```

---

### 4. Classification Agent

**Role**: Categorization Specialist

**Goal**: Accurately classify contacts into predefined categories

**Tools**:
- AI Tool
- Validation Tool

**Categories**:
- **Founder**: Founders and co-founders of companies
- **Investor**: VCs, angels, investment professionals
- **Enabler**: Advisors, mentors, connectors
- **Professional**: Industry professionals

**Classification Logic**:
```python
# Uses context clues:
# - Job title (CEO, Partner, Advisor)
# - Company type (VC firm, startup)
# - Background information
```

---

### 5. Reporting Agent

**Role**: Analytics Specialist

**Goal**: Generate comprehensive reports and statistics about the contact network

**Tools**:
- Google Sheets Tool
- AI Tool

**Responsibilities**:
- Contact statistics
- Breakdown by attributes
- Network insights
- Trend analysis
- Individual contact reports

**Example Tasks**:
```python
agent.generate_stats()
agent.generate_stats_by("company")
agent.generate_network_insights()
```

---

### 6. Evaluation Agent

**Role**: Quality Assurance Specialist

**Goal**: Assess data quality, completeness, and accuracy of contact information

**Tools**:
- Validation Tool
- Google Sheets Tool

**Responsibilities**:
- Data completeness assessment
- Validity checking
- Duplicate detection
- Quality scoring
- Improvement recommendations

**Metrics Tracked**:
- Completeness rate
- Field coverage
- Duplicate count
- Invalid entries

---

### 7. Troubleshooting Agent

**Role**: Problem Resolution Specialist

**Goal**: Identify, diagnose, and resolve issues in data and operations

**Tools**:
- All available tools

**Responsibilities**:
- Error detection
- Root cause analysis
- Problem resolution
- Recovery procedures
- Issue logging

**Error Types Handled**:
- Validation errors
- API failures
- Data inconsistencies
- Processing failures

## Agent Collaboration

Agents work together through Crews:

```
                    ┌─────────────────────┐
                    │   Contact Crew      │
                    └─────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Contact Agent  │  │Classification   │  │  Evaluation     │
│                 │  │    Agent        │  │    Agent        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Creating Custom Agents

To add a new agent:

1. Create agent file in `agents/`:

```python
from crewai import Agent
from config import AIConfig

def create_custom_agent(tools=None):
    return Agent(
        role="Your Role",
        goal="Your agent's goal",
        backstory="""Your agent's backstory""",
        tools=tools or [],
        allow_delegation=False,
        verbose=True,
        llm_config={
            "model": AIConfig.DEFAULT_MODEL,
            "temperature": 0.7
        }
    )
```

2. Add getter function:

```python
_custom_agent = None

def get_custom_agent(tools=None):
    global _custom_agent
    if _custom_agent is None:
        _custom_agent = create_custom_agent(tools)
    return _custom_agent
```

3. Import in relevant crew

## Best Practices

1. **Single Responsibility**: Each agent has one primary function
2. **Tool Minimization**: Only provide tools the agent needs
3. **Clear Goals**: Specific, measurable goals improve performance
4. **Descriptive Backstories**: Help agents understand context
5. **Verbose Mode**: Enable for debugging, disable in production
