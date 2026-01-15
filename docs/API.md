# API Documentation

This document describes the internal service APIs.

## Services Overview

| Service | Purpose | Dependencies |
|---------|---------|--------------|
| Google Sheets Service | Contact storage | gspread, google-auth |
| AI Service | AI operations | openai, google-generativeai |
| Enrichment Service | Web search | serpapi |
| Classification Service | Categorization | AI Service |
| Transcription Service | Voice-to-text | AI Service |

## Google Sheets Service

### `get_sheets_service()`

Returns the singleton Google Sheets service instance.

### Methods

#### `initialize() -> bool`

Initialize the Google Sheets connection.

```python
service = get_sheets_service()
if service.initialize():
    print("Connected to Google Sheets")
```

#### `add_contact(contact: Contact) -> bool`

Add a new contact to the sheet.

```python
from data.schema import Contact

contact = Contact(
    name="John Doe",
    email="john@example.com",
    company="TechCorp"
)
success = service.add_contact(contact)
```

#### `get_contact_by_name(name: str) -> Optional[Contact]`

Retrieve a contact by name.

```python
contact = service.get_contact_by_name("John Doe")
if contact:
    print(contact.email)
```

#### `update_contact(name: str, updates: Dict[str, Any]) -> bool`

Update an existing contact.

```python
service.update_contact("John Doe", {
    "email": "newemail@example.com",
    "phone": "+1-555-0123"
})
```

#### `delete_contact(name: str) -> bool`

Delete a contact by name.

```python
if service.delete_contact("John Doe"):
    print("Contact deleted")
```

#### `search_contacts(query: str) -> List[Contact]`

Search contacts across all fields.

```python
results = service.search_contacts("TechCorp")
for contact in results:
    print(contact.name)
```

#### `get_all_contacts() -> List[Contact]`

Get all contacts.

```python
contacts = service.get_all_contacts()
```

#### `get_contact_stats() -> Dict[str, Any]`

Get contact statistics.

```python
stats = service.get_contact_stats()
print(f"Total: {stats['total']}")
print(f"By classification: {stats['by_classification']}")
```

#### `export_to_csv() -> str`

Export all contacts to CSV format.

```python
csv_content = service.export_to_csv()
```

---

## AI Service

### `get_ai_service()`

Returns the singleton AI service instance.

### Methods

#### `classify_contact(contact_info: str) -> str`

Classify a contact into categories.

```python
service = get_ai_service()
category = service.classify_contact("John Doe, CEO at TechCorp")
# Returns: "founder"
```

Categories: `founder`, `investor`, `enabler`, `professional`

#### `parse_contact_text(text: str) -> Dict[str, Any]`

Parse natural language to extract contact information.

```python
result = service.parse_contact_text(
    "I met Sarah Johnson yesterday. She's the VP of Engineering at StartupXYZ"
)
# Returns: {
#     "name": "Sarah Johnson",
#     "job_title": "VP of Engineering",
#     "company": "StartupXYZ"
# }
```

#### `extract_from_image(image_bytes: bytes) -> Dict[str, Any]`

Extract contact information from business card image.

```python
with open("card.jpg", "rb") as f:
    image_data = f.read()

result = service.extract_from_image(image_data)
```

#### `transcribe_audio(audio_bytes: bytes, filename: str) -> str`

Transcribe audio to text.

```python
transcript = service.transcribe_audio(audio_bytes, "voice.ogg")
```

#### `generate_response(query: str, context: str) -> str`

Generate AI response to a query with context.

```python
response = service.generate_response(
    "Who works at TechCorp?",
    "Contacts: John Doe (CEO at TechCorp), Jane Smith (CTO at TechCorp)"
)
```

---

## Enrichment Service

### `get_enrichment_service()`

Returns the singleton enrichment service instance.

### Methods

#### `search_person(name: str, company: str = None) -> Dict[str, Any]`

Search for information about a person.

```python
service = get_enrichment_service()
result = service.search_person("John Doe", "TechCorp")
```

#### `search_company(company_name: str) -> Dict[str, Any]`

Search for company information.

```python
result = service.search_company("TechCorp")
```

#### `find_linkedin(name: str, company: str = None) -> Optional[str]`

Find a person's LinkedIn profile URL.

```python
linkedin_url = service.find_linkedin("John Doe", "TechCorp")
```

#### `get_company_news(company_name: str, limit: int = 5) -> List[Dict]`

Get recent news about a company.

```python
news = service.get_company_news("TechCorp", limit=3)
```

---

## Analytics Tracker

### `get_tracker()`

Returns the singleton analytics tracker instance.

### Methods

#### `start_operation(operation_type: str, user_id: str, command: str) -> str`

Start tracking an operation.

```python
tracker = get_tracker()
operation_id = tracker.start_operation(
    operation_type="add_contact",
    user_id="12345",
    command="/add"
)
```

#### `end_operation(success: bool, error_message: str = None)`

End the current operation.

```python
tracker.end_operation(success=True)
# or
tracker.end_operation(success=False, error_message="Contact not found")
```

---

## Analytics Database

### `get_analytics_db()`

Returns the singleton analytics database instance.

### Methods

#### `get_operation_stats(days: int = 7) -> Dict[str, Any]`

Get operation statistics for a period.

```python
db = get_analytics_db()
stats = db.get_operation_stats(days=7)
```

#### `get_operations(limit: int = 100) -> List[Dict]`

Get recent operations.

```python
operations = db.get_operations(limit=50)
```

#### `get_agent_stats() -> Dict[str, Any]`

Get agent activity statistics.

```python
agent_stats = db.get_agent_stats()
```

#### `get_recent_errors(limit: int = 100) -> List[Dict]`

Get recent errors.

```python
errors = db.get_recent_errors(limit=10)
```

---

## Data Schema

### Contact Model

```python
@dataclass
class Contact:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    linkedin: Optional[str] = None
    location: Optional[str] = None
    classification: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    added_date: Optional[str] = None
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Contact": ...
```

### OperationType Enum

```python
class OperationType(Enum):
    ADD_CONTACT = "add_contact"
    VIEW_CONTACT = "view_contact"
    UPDATE_CONTACT = "update_contact"
    DELETE_CONTACT = "delete_contact"
    SEARCH_CONTACT = "search_contact"
    ENRICH_CONTACT = "enrich_contact"
    CLASSIFY_CONTACT = "classify_contact"
    VOICE_TRANSCRIPTION = "voice_transcription"
    IMAGE_OCR = "image_ocr"
    GENERATE_REPORT = "generate_report"
    EXPORT_CONTACTS = "export_contacts"
    IMPORT_CONTACTS = "import_contacts"
```
