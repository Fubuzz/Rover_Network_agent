# Tools Documentation

This document describes the CrewAI tools available to agents.

## Overview

Tools are the interface between agents and external services. Each tool wraps a service or utility, exposing it in a format agents can use.

## Tool Architecture

```
Agent
   │
   ▼
Tool (CrewAI wrapper)
   │
   ▼
Service (Business logic)
   │
   ▼
External API / Database
```

## Available Tools

### 1. Google Sheets Tool

**Purpose**: Contact data storage and retrieval

**Functions**:

| Function | Description | Parameters |
|----------|-------------|------------|
| `add_contact` | Add a new contact | `contact_data: dict` |
| `get_contact` | Get contact by name | `name: str` |
| `update_contact` | Update a contact | `name: str, updates: dict` |
| `delete_contact` | Delete a contact | `name: str` |
| `search_contacts` | Search contacts | `query: str` |
| `get_all_contacts` | Get all contacts | None |
| `get_contact_stats` | Get statistics | None |

**Example Usage by Agent**:
```
I need to add a new contact.
Using tool: add_contact with {"name": "John Doe", "email": "john@example.com"}
```

---

### 2. SerpAPI Tool

**Purpose**: Web search and research

**Functions**:

| Function | Description | Parameters |
|----------|-------------|------------|
| `search_person` | Search for a person | `name: str, company: str` |
| `search_company` | Search for a company | `company_name: str` |
| `find_linkedin` | Find LinkedIn profile | `name: str, company: str` |
| `get_news` | Get recent news | `topic: str` |

**Example Usage by Agent**:
```
I need to find information about John Doe.
Using tool: search_person with {"name": "John Doe", "company": "TechCorp"}
```

---

### 3. AI Tool

**Purpose**: AI-powered analysis and extraction

**Functions**:

| Function | Description | Parameters |
|----------|-------------|------------|
| `classify_contact` | Classify a contact | `contact_info: str` |
| `parse_contact_text` | Parse natural language | `text: str` |
| `extract_from_image` | OCR and extraction | `image_data: bytes` |
| `generate_summary` | Summarize text | `text: str` |
| `generate_response` | Generate AI response | `query: str, context: str` |

**Example Usage by Agent**:
```
I need to classify this contact.
Using tool: classify_contact with {"contact_info": "John Doe, CEO at TechCorp"}
Result: "founder"
```

---

### 4. Validation Tool

**Purpose**: Data validation

**Functions**:

| Function | Description | Parameters |
|----------|-------------|------------|
| `validate_email` | Validate email format | `email: str` |
| `validate_phone` | Validate phone number | `phone: str` |
| `validate_url` | Validate URL | `url: str` |
| `validate_contact` | Validate full contact | `contact: dict` |

**Example Usage by Agent**:
```
I need to verify this email is valid.
Using tool: validate_email with {"email": "john@example.com"}
Result: true
```

---

### 5. Transcription Tool

**Purpose**: Voice-to-text transcription

**Functions**:

| Function | Description | Parameters |
|----------|-------------|------------|
| `transcribe_audio` | Transcribe audio file | `audio_bytes: bytes, format: str` |

**Example Usage by Agent**:
```
I need to transcribe this voice message.
Using tool: transcribe_audio with audio data
Result: "Add John Doe, he's the CEO at TechCorp"
```

## Creating Custom Tools

1. Create tool file in `tools/`:

```python
from crewai import Tool
from services.my_service import get_my_service

def my_function(param: str) -> str:
    """Description of what this tool does."""
    service = get_my_service()
    result = service.do_something(param)
    return str(result)

my_tool = Tool(
    name="my_tool",
    description="What this tool does and when to use it",
    func=my_function
)
```

2. Add to agent's tool list:

```python
from tools.my_tool import my_tool

agent = Agent(
    role="My Role",
    tools=[my_tool, other_tool]
)
```

## Tool Best Practices

1. **Clear Descriptions**: Agents use descriptions to decide when to use tools
2. **Error Handling**: Tools should handle errors gracefully
3. **Return Strings**: Tools should return string representations
4. **Single Purpose**: Each tool should do one thing well
5. **Logging**: Log tool usage for debugging

## Tool Naming Conventions

- Use snake_case for tool names
- Make names descriptive of the action
- Include the domain in the name if applicable

Examples:
- `add_contact` ✓
- `searchPerson` ✗
- `google_sheets_add` ✓

## Error Handling

Tools should return informative error messages:

```python
def my_tool(param: str) -> str:
    try:
        result = do_something(param)
        return f"Success: {result}"
    except ValidationError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return f"Error: {e}"
```

Agents will use these messages to decide next steps.
