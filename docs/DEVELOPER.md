# Developer Guide

This guide is for developers who want to extend or modify the Telegram Network Nurturing Agent.

## Project Structure

```
Rover_Network_agent/
├── main.py                     # Entry point
├── config.py                   # Configuration loading
├── requirements.txt            # Dependencies
├── .env                        # Environment variables (not in git)
├── credentials.json            # Google credentials (not in git)
│
├── agents/                     # CrewAI agent definitions
│   ├── contact_agent.py
│   ├── enrichment_agent.py
│   ├── input_agent.py
│   ├── classification_agent.py
│   ├── reporting_agent.py
│   ├── evaluation_agent.py
│   └── troubleshooting_agent.py
│
├── crews/                      # CrewAI crew orchestrations
│   ├── contact_crew.py
│   ├── enrichment_crew.py
│   ├── input_processing_crew.py
│   └── reporting_crew.py
│
├── tools/                      # CrewAI tool wrappers
│   ├── google_sheets_tool.py
│   ├── serpapi_tool.py
│   ├── ai_tool.py
│   ├── validation_tool.py
│   └── transcription_tool.py
│
├── services/                   # Core business logic
│   ├── google_sheets.py
│   ├── ai_service.py
│   ├── enrichment.py
│   ├── classification.py
│   └── transcription.py
│
├── handlers/                   # Telegram command handlers
│   ├── contact_handlers.py
│   ├── enrichment_handlers.py
│   ├── report_handlers.py
│   ├── input_handlers.py
│   ├── analytics_handlers.py
│   ├── evaluation_handlers.py
│   └── conversation_handlers.py
│
├── analytics/                  # Analytics system
│   ├── tracker.py
│   ├── metrics.py
│   ├── usage_analytics.py
│   └── performance_monitor.py
│
├── app_logging/                # Logging system
│   ├── logger.py
│   ├── operation_logger.py
│   ├── agent_logger.py
│   ├── error_logger.py
│   └── change_logger.py
│
├── interfaces/                 # User interfaces
│   ├── evaluation_interface.py
│   ├── analytics_interface.py
│   └── dashboard.py
│
├── utils/                      # Utilities
│   ├── constants.py
│   ├── validators.py
│   ├── parsers.py
│   └── formatters.py
│
├── data/                       # Data models
│   ├── schema.py
│   └── storage.py
│
└── docs/                       # Documentation
    ├── ARCHITECTURE.md
    ├── API.md
    ├── AGENTS.md
    ├── CREWS.md
    ├── TOOLS.md
    ├── SETUP.md
    ├── USAGE.md
    ├── DEVELOPER.md
    ├── CHANGELOG.md
    └── TROUBLESHOOTING.md
```

## Development Setup

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd Rover_Network_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env
# Edit .env with your credentials

# Run in debug mode
DEBUG_MODE=true python main.py
```

## Adding New Features

### Adding a New Command

1. Create or edit handler file in `handlers/`:

```python
# handlers/my_handlers.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from analytics.tracker import get_tracker

async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tracker = get_tracker()
    tracker.start_operation(
        operation_type="my_operation",
        user_id=str(update.effective_user.id),
        command="/mycommand"
    )
    
    try:
        # Your logic here
        await update.message.reply_text("Response")
        tracker.end_operation(success=True)
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error: {e}")

def get_my_handlers():
    return [
        CommandHandler("mycommand", my_command),
    ]
```

2. Register in `main.py`:

```python
from handlers.my_handlers import get_my_handlers

# In main():
for handler in get_my_handlers():
    application.add_handler(handler)
```

3. Update help message in `utils/constants.py`

### Adding a New Agent

1. Create agent in `agents/`:

```python
# agents/my_agent.py
from crewai import Agent
from config import AIConfig

def create_my_agent(tools=None):
    return Agent(
        role="My Role",
        goal="What this agent accomplishes",
        backstory="""Agent's background and expertise""",
        tools=tools or [],
        allow_delegation=False,
        verbose=True,
        llm_config={
            "model": AIConfig.DEFAULT_MODEL,
            "temperature": 0.7
        }
    )

_my_agent = None

def get_my_agent(tools=None):
    global _my_agent
    if _my_agent is None:
        _my_agent = create_my_agent(tools)
    return _my_agent
```

2. Use in a crew or create new crew

### Adding a New Service

1. Create service in `services/`:

```python
# services/my_service.py
from typing import Optional
from config import MyConfig

class MyService:
    def __init__(self):
        self.api_key = MyConfig.API_KEY
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            # Initialize client
            pass
        return self._client
    
    def my_method(self, param: str) -> str:
        # Implementation
        return result

_my_service: Optional[MyService] = None

def get_my_service() -> MyService:
    global _my_service
    if _my_service is None:
        _my_service = MyService()
    return _my_service
```

2. Optionally wrap as CrewAI tool in `tools/`

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints
- Document public functions
- Maximum line length: 100 characters

### Naming Conventions

- Files: snake_case (`my_module.py`)
- Classes: PascalCase (`MyClass`)
- Functions: snake_case (`my_function`)
- Constants: UPPER_SNAKE_CASE (`MY_CONSTANT`)

### Error Handling

```python
# Do
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return error_response()

# Don't
try:
    result = risky_operation()
except:
    pass
```

### Logging

Use the centralized logging system:

```python
from app_logging.logger import get_main_logger
from app_logging.operation_logger import get_operation_logger

logger = get_main_logger()
op_logger = get_operation_logger()

logger.info("General info message")
op_logger.log_operation_start("my_operation", {"param": value})
```

### Analytics Tracking

Track all significant operations:

```python
from analytics.tracker import get_tracker

tracker = get_tracker()
tracker.start_operation("operation_name", user_id, command)
try:
    # Operation
    tracker.end_operation(success=True)
except Exception as e:
    tracker.end_operation(success=False, error_message=str(e))
```

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=. tests/

# Run specific test
python -m pytest tests/test_services.py::test_google_sheets
```

### Writing Tests

```python
# tests/test_my_module.py
import pytest
from services.my_service import get_my_service

def test_my_method():
    service = get_my_service()
    result = service.my_method("test")
    assert result == expected_value

@pytest.fixture
def mock_service(mocker):
    mock = mocker.patch("services.my_service.get_my_service")
    return mock
```

## Debugging

### Enable Debug Mode

```bash
DEBUG_MODE=true LOG_LEVEL=DEBUG python main.py
```

### Viewing Logs

```bash
# View main log
tail -f logs/main.log

# View operation log
tail -f logs/operations.log

# View errors
tail -f logs/errors.log
```

### Agent Debugging

Enable verbose mode in agents:

```python
agent = Agent(
    role="My Role",
    verbose=True,  # Shows agent thinking
    ...
)
```

## Common Tasks

### Updating Dependencies

```bash
pip install new-package
pip freeze > requirements.txt
```

### Adding Environment Variables

1. Add to `.env.template`:
```
MY_NEW_VAR=default_value
```

2. Add to `config.py`:
```python
class MyConfig:
    MY_VAR = os.getenv("MY_NEW_VAR", "default")
```

3. Update documentation

### Database Migrations

The analytics database auto-migrates on startup. For manual changes:

```python
# In data/storage.py, add to _init_database():
cursor.execute("""
    ALTER TABLE operations ADD COLUMN new_column TEXT
""")
```

## Performance Tips

1. Use singleton patterns for services (already implemented)
2. Cache frequently accessed data
3. Use async operations where possible
4. Monitor API rate limits
5. Use batch operations for bulk updates

## Security Notes

1. Never commit `.env` or `credentials.json`
2. Use environment variables for secrets
3. Validate all user inputs
4. Sanitize data before storage
5. Use HTTPS for all external requests
