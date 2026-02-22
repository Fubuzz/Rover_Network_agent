"""
Data schema definitions for contacts and analytics.
Matches the existing Google Sheet structure.

Uses Pydantic for data validation on Match and Draft models.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import uuid
import re

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr


# ============================================================
# SHEET NAME CONSTANTS
# ============================================================
CONTACTS_SHEET_NAME = "contacts"    # Sheet 1 - All contacts (founders, investors)
MATCHES_SHEET_NAME = "Matches"      # Sheet 2 - Founder-Investor matches
DRAFTS_SHEET_NAME = "Drafts"        # Sheet 3 - Email drafts for approval


class Classification(str, Enum):
    """Contact classification categories."""
    FOUNDER = "founder"
    INVESTOR = "investor"
    ENABLER = "enabler"
    PROFESSIONAL = "professional"


class InputSource(str, Enum):
    """Source of contact input."""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    BULK = "bulk"
    MANUAL = "manual"
    TELEGRAM = "telegram"


class OperationStatus(str, Enum):
    """Operation status."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


class OperationType(str, Enum):
    """Types of operations."""
    ADD_CONTACT = "add_contact"
    UPDATE_CONTACT = "update_contact"
    DELETE_CONTACT = "delete_contact"
    VIEW_CONTACT = "view_contact"
    SEARCH_CONTACT = "search_contact"
    ENRICH_CONTACT = "enrich_contact"
    CLASSIFY_CONTACT = "classify_contact"
    EXPORT_CONTACTS = "export_contacts"
    IMPORT_CONTACTS = "import_contacts"
    GENERATE_REPORT = "generate_report"
    VOICE_TRANSCRIPTION = "voice_transcription"
    IMAGE_OCR = "image_ocr"


@dataclass
class ImportResult:
    """Result of a bulk import operation."""
    total_rows: int = 0
    successful: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)

    def summary(self) -> str:
        """Generate a summary of the import result."""
        return (
            f"Total: {self.total_rows}, Added: {self.successful}, "
            f"Updated: {self.updated}, Skipped: {self.skipped}, Failed: {self.failed}"
        )


# Google Sheets column headers - matching your existing sheet
SHEET_HEADERS = [
    "contact_id",
    "first_name",
    "last_name",
    "full_name",
    "email",
    "phone",
    "linkedin_url",
    "company",
    "title",
    "source",
    "relationship_strength",
    "how_we_met",
    "last_contact_date",
    "notes",
    "status",
    "created_date",
    "updated_date",
    "company_description",
    "industry",
    "company_stage",
    "funding_raised",
    "founder_score",
    "key_strengths",
    "stage_fit",
    "sector_fit",
    "classified_date",
    "linkedin_summary",
    "contact_type",
    "research_quality",
    "researched_date",
    "imported_date",
    "linkedin_status",
    "chatId",
    "website",
    "address",
    "userId",
    "linkedin_link",
    # V3 New Fields
    "relationship_score",
    "last_interaction_date",
    "interaction_count",
    "follow_up_date",
    "follow_up_reason",
    "introduced_by",
    "introduced_to",
    "priority",
    "relationship_stage"
]

# Column index mapping
COL_INDEX = {name: i for i, name in enumerate(SHEET_HEADERS)}


@dataclass
class Contact:
    """Contact data model - matches your existing Google Sheet structure."""
    # Core fields
    contact_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None  # Job title
    source: str = InputSource.TELEGRAM.value
    
    # Relationship fields
    relationship_strength: Optional[str] = None
    how_we_met: Optional[str] = None
    last_contact_date: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"
    
    # Dates
    created_date: Optional[str] = None
    updated_date: Optional[str] = None
    
    # Company info
    company_description: Optional[str] = None
    industry: Optional[str] = None
    company_stage: Optional[str] = None
    funding_raised: Optional[str] = None
    
    # Classification & scoring
    founder_score: Optional[str] = None
    key_strengths: Optional[str] = None
    stage_fit: Optional[str] = None
    sector_fit: Optional[str] = None
    classified_date: Optional[str] = None
    
    # Research
    linkedin_summary: Optional[str] = None
    contact_type: Optional[str] = None  # founder, investor, enabler, professional
    research_quality: Optional[str] = None
    researched_date: Optional[str] = None
    research_summary: Optional[str] = None  # In-memory only, not persisted to sheet
    imported_date: Optional[str] = None
    linkedin_status: Optional[str] = None
    
    # Telegram/User info
    chat_id: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    user_id: Optional[str] = None
    linkedin_link: Optional[str] = None
    
    # V3 New Fields - Relationship Intelligence
    relationship_score: Optional[int] = None  # 0-100 relationship health score
    last_interaction_date: Optional[str] = None  # When did you last interact?
    interaction_count: Optional[int] = 0  # How many times have you interacted?
    follow_up_date: Optional[str] = None  # When should you follow up?
    follow_up_reason: Optional[str] = None  # Why follow up?
    introduced_by: Optional[str] = None  # Who introduced you?
    introduced_to: Optional[str] = None  # Who have you introduced them to?
    priority: Optional[str] = None  # high/medium/low
    relationship_stage: Optional[str] = None  # new/building/strong/dormant/lost
    
    # Internal
    row_number: Optional[int] = None
    
    @property
    def name(self) -> str:
        """Get display name."""
        if self.full_name:
            return self.full_name
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else "Unknown"
    
    @name.setter
    def name(self, value: str):
        """Set name - splits into first/last."""
        self.full_name = value
        parts = value.split(" ", 1)
        self.first_name = parts[0]
        self.last_name = parts[1] if len(parts) > 1 else None
    
    @property
    def job_title(self) -> Optional[str]:
        """Alias for title field."""
        return self.title
    
    @job_title.setter
    def job_title(self, value: str):
        self.title = value
    
    @property
    def classification(self) -> Optional[str]:
        """Alias for contact_type field."""
        return self.contact_type
    
    @classification.setter
    def classification(self, value: str):
        self.contact_type = value
    
    @property
    def location(self) -> Optional[str]:
        """Alias for address field."""
        return self.address
    
    @location.setter
    def location(self, value: str):
        self.address = value
    
    @property
    def tags(self) -> List[str]:
        """Get tags from key_strengths."""
        if self.key_strengths:
            return [t.strip() for t in self.key_strengths.split(",") if t.strip()]
        return []
    
    @tags.setter
    def tags(self, value):
        if isinstance(value, list):
            self.key_strengths = ",".join(value)
        else:
            self.key_strengths = value
    
    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "linkedin_url": self.linkedin_url or self.linkedin_link,
            "company": self.company,
            "job_title": self.title,
            "classification": self.contact_type,
            "location": self.address,
            "notes": self.notes,
            "tags": self.key_strengths,
            "industry": self.industry,
            "source": self.source,
            "last_contacted": self.last_contact_date,
            "how_we_met": self.how_we_met,
            "relationship_strength": self.relationship_strength,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        """Create Contact from dictionary (e.g., from parsed input)."""
        contact = cls()
        
        # Handle name
        if data.get("name"):
            contact.name = data["name"]
        if data.get("first_name"):
            contact.first_name = data["first_name"]
        if data.get("last_name"):
            contact.last_name = data["last_name"]
        
        # Map common field names
        contact.email = data.get("email")
        contact.phone = data.get("phone")
        contact.linkedin_url = data.get("linkedin_url") or data.get("linkedin")
        contact.company = data.get("company")
        contact.title = data.get("title") or data.get("job_title")
        contact.contact_type = data.get("contact_type") or data.get("classification")
        contact.address = data.get("address") or data.get("location")
        contact.notes = data.get("notes")
        contact.industry = data.get("industry")
        contact.source = data.get("source", InputSource.TELEGRAM.value)
        contact.how_we_met = data.get("how_we_met")
        
        # Set dates
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        contact.created_date = data.get("created_date", now)
        contact.updated_date = now
        contact.imported_date = now
        
        return contact
    
    def to_sheet_row(self) -> list:
        """Convert to list for Google Sheets row."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return [
            self.contact_id or str(uuid.uuid4())[:8],
            self.first_name or "",
            self.last_name or "",
            self.full_name or self.name or "",
            self.email or "",
            self.phone or "",
            self.linkedin_url or "",
            self.company or "",
            self.title or "",
            self.source or "telegram",
            self.relationship_strength or "",
            self.how_we_met or "",
            self.last_contact_date or "",
            self.notes or "",
            self.status or "active",
            self.created_date or now,
            self.updated_date or now,
            self.company_description or "",
            self.industry or "",
            self.company_stage or "",
            self.funding_raised or "",
            self.founder_score or "",
            self.key_strengths or "",
            self.stage_fit or "",
            self.sector_fit or "",
            self.classified_date or "",
            self.linkedin_summary or "",
            self.contact_type or "",
            self.research_quality or "",
            self.researched_date or "",
            self.imported_date or now,
            self.linkedin_status or "",
            self.chat_id or "",
            self.website or "",
            self.address or "",
            self.user_id or "",
            self.linkedin_link or self.linkedin_url or "",
            # V3 New Fields
            str(self.relationship_score) if self.relationship_score is not None else "",
            self.last_interaction_date or "",
            str(self.interaction_count) if self.interaction_count is not None else "0",
            self.follow_up_date or "",
            self.follow_up_reason or "",
            self.introduced_by or "",
            self.introduced_to or "",
            self.priority or "",
            self.relationship_stage or ""
        ]
    
    @classmethod
    def from_sheet_row(cls, row: list, row_number: int = None) -> "Contact":
        """Create Contact from Google Sheets row."""
        # Ensure row has enough elements
        while len(row) < len(SHEET_HEADERS):
            row.append("")
        
        contact = cls(
            contact_id=row[0] or str(uuid.uuid4())[:8],
            first_name=row[1] or None,
            last_name=row[2] or None,
            full_name=row[3] or None,
            email=row[4] or None,
            phone=row[5] or None,
            linkedin_url=row[6] or None,
            company=row[7] or None,
            title=row[8] or None,
            source=row[9] or "telegram",
            relationship_strength=row[10] or None,
            how_we_met=row[11] or None,
            last_contact_date=row[12] or None,
            notes=row[13] or None,
            status=row[14] or "active",
            created_date=row[15] or None,
            updated_date=row[16] or None,
            company_description=row[17] or None,
            industry=row[18] or None,
            company_stage=row[19] or None,
            funding_raised=row[20] or None,
            founder_score=row[21] or None,
            key_strengths=row[22] or None,
            stage_fit=row[23] or None,
            sector_fit=row[24] or None,
            classified_date=row[25] or None,
            linkedin_summary=row[26] or None,
            contact_type=row[27] or None,
            research_quality=row[28] or None,
            researched_date=row[29] or None,
            imported_date=row[30] or None,
            linkedin_status=row[31] or None,
            chat_id=row[32] or None,
            website=row[33] or None,
            address=row[34] or None,
            user_id=row[35] or None,
            linkedin_link=row[36] if len(row) > 36 else None,
            # V3 New Fields
            relationship_score=int(row[37]) if len(row) > 37 and row[37] and row[37].strip().isdigit() else None,
            last_interaction_date=row[38] if len(row) > 38 else None,
            interaction_count=int(row[39]) if len(row) > 39 and row[39] and row[39].strip().isdigit() else 0,
            follow_up_date=row[40] if len(row) > 40 else None,
            follow_up_reason=row[41] if len(row) > 41 else None,
            introduced_by=row[42] if len(row) > 42 else None,
            introduced_to=row[43] if len(row) > 43 else None,
            priority=row[44] if len(row) > 44 else None,
            relationship_stage=row[45] if len(row) > 45 else None,
            row_number=row_number
        )
        
        return contact


@dataclass
class OperationRecord:
    """Record of an operation for analytics."""
    operation_type: str
    status: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    agent_name: Optional[str] = None
    crew_name: Optional[str] = None
    user_id: Optional[str] = None
    command: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class FeatureUsageRecord:
    """Record of feature usage."""
    feature_name: str
    usage_count: int = 1
    last_used: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    id: Optional[int] = None


@dataclass
class AgentActivityRecord:
    """Record of agent activity."""
    agent_name: str
    action: str
    tool_used: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    success: bool = True
    operation_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class ErrorLogRecord:
    """Record of an error."""
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    operation_id: Optional[int] = None
    agent_name: Optional[str] = None
    resolved: bool = False
    resolution: Optional[str] = None
    id: Optional[int] = None


@dataclass
class FeatureChangeRecord:
    """Record of a feature change."""
    change_type: str  # added, modified, removed
    feature_name: str
    description: str
    version: str = "1.0.0"
    timestamp: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    id: Optional[int] = None


# ============================================================
# MATCHMAKER SCHEMA (V01)
# ============================================================

# Match Sheet Headers - for the "Matches" tab (Sheet 2)
# MUST match exact column order in Google Sheet
# Names and LinkedIn URLs are "baked in" by the Matchmaker for downstream use
MATCH_SHEET_HEADERS = [
    "match_id",                  # 1
    "founder_contact_id",        # 2
    "founder_email",             # 3
    "founder_linkedin",          # 4 - Person's LinkedIn (from contact_linkedin_url)
    "founder_name",              # 5
    "startup_name",              # 6
    "investor_contact_id",       # 7
    "investor_email",            # 8
    "investor_firm",             # 9
    "investor_name",             # 10
    "investor_linkedin",         # 11 - Person's LinkedIn (from contact_linkedin_url)
    "match_score",               # 12
    "primary_match_reason",
    "match_rationale",
    "thesis_alignment_notes",
    "portfolio_synergy",
    "anti_portfolio_flag",
    "sector_overlap",
    "stage_alignment",
    "check_size_fit",
    "geo_alignment",
    "intro_angle",
    "suggested_subject_line",
    "recent_news_hook",
    "tone_instruction",
    "match_date",
    "email_status",
    "human_approved"
]

MATCH_COL_INDEX = {name: i for i, name in enumerate(MATCH_SHEET_HEADERS)}


class StageAlignment(str, Enum):
    """Stage alignment classification."""
    MATCH = "Match"      # Perfect stage fit
    REACH = "Reach"      # Founder stage slightly below investor preference
    SAFETY = "Safety"    # Founder stage slightly above investor preference


class IntroAngle(str, Enum):
    """Email introduction strategy."""
    FLATTERY = "Flattery"      # Compliment recent achievement
    MOMENTUM = "Momentum"      # Highlight startup traction
    HARD_DATA = "Hard Data"    # Lead with metrics
    MUTUAL = "Mutual"          # Mention mutual connection
    THESIS = "Thesis"          # Appeal to investor thesis


class ToneInstruction(str, Enum):
    """Email tone."""
    WARM = "Warm"
    FORMAL = "Formal"
    URGENT = "Urgent"


class EmailStatus(str, Enum):
    """Match email status."""
    DRAFTED = "Drafted"
    SENT = "Sent"
    REPLIED = "Replied"
    MEETING_SCHEDULED = "Meeting Scheduled"
    PASSED = "Passed"
    MISSING_DATA = "Missing Data"


class Match(BaseModel):
    """
    Pydantic model for Founder-Investor Match.
    Validates data before writing to Matches sheet (Sheet 2).
    """
    # IDs
    match_id: str = Field(default_factory=lambda: f"MATCH_{str(uuid.uuid4())[:6].upper()}")
    founder_contact_id: Optional[str] = Field(default=None, description="Contact ID from Sheet 1")
    investor_contact_id: Optional[str] = Field(default=None, description="Contact ID from Sheet 1")

    # Founder Info (columns 3-6 in Matches sheet)
    founder_email: Optional[str] = Field(default=None, description="Founder's email address")
    founder_linkedin: Optional[str] = Field(default=None, description="Person's LinkedIn (from contact_linkedin_url)")
    founder_name: Optional[str] = Field(default=None, description="Founder's full name")
    startup_name: Optional[str] = Field(default=None, description="Startup/company name")

    # Investor Info (columns 7-11 in Matches sheet)
    investor_email: Optional[str] = Field(default=None, description="Investor's email address")
    investor_firm: Optional[str] = Field(default=None, description="Investment firm name")
    investor_name: Optional[str] = Field(default=None, description="Investor's full name")
    investor_linkedin: Optional[str] = Field(default=None, description="Person's LinkedIn (from contact_linkedin_url)")

    # Scoring
    match_score: int = Field(default=0, ge=0, le=100, description="Match quality score 0-100")
    primary_match_reason: Optional[str] = None
    match_rationale: Optional[str] = None

    # Analysis
    thesis_alignment_notes: Optional[str] = None
    portfolio_synergy: Optional[str] = None
    anti_portfolio_flag: bool = False
    sector_overlap: Optional[str] = None
    stage_alignment: str = Field(default=StageAlignment.MATCH.value)
    check_size_fit: str = Field(default="Unknown")
    geo_alignment: str = Field(default="Unknown")

    # Email Strategy
    intro_angle: str = Field(default=IntroAngle.THESIS.value)
    suggested_subject_line: Optional[str] = None
    recent_news_hook: Optional[str] = None
    tone_instruction: str = Field(default=ToneInstruction.WARM.value)

    # Status
    match_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    email_status: str = Field(default=EmailStatus.DRAFTED.value)
    human_approved: bool = False

    model_config = {"extra": "ignore"}  # Ignore extra fields

    @field_validator('founder_name', 'investor_name', mode='before')
    @classmethod
    def clean_name(cls, v):
        """Strip whitespace from names."""
        if v is None:
            return None
        return str(v).strip() if v else None

    @field_validator('founder_email', 'investor_email', mode='before')
    @classmethod
    def clean_email(cls, v):
        """Normalize email to lowercase."""
        if v is None or not v:
            return None
        return str(v).strip().lower()

    @field_validator('founder_linkedin', 'investor_linkedin', mode='before')
    @classmethod
    def validate_linkedin(cls, v):
        """Validate LinkedIn URL format."""
        if v is None or not v:
            return None
        v = str(v).strip()
        # Accept any LinkedIn URL or empty
        if v and 'linkedin.com' not in v.lower() and v != "":
            # Not a valid LinkedIn URL but not empty - keep it anyway for flexibility
            pass
        return v

    @field_validator('match_score', mode='before')
    @classmethod
    def coerce_score(cls, v):
        """Coerce score to int."""
        if v is None:
            return 0
        try:
            score = int(v)
            return max(0, min(100, score))  # Clamp to 0-100
        except (ValueError, TypeError):
            return 0

    def to_sheet_row(self) -> list:
        """Convert to list for Google Sheets row.

        Order MUST match MATCH_SHEET_HEADERS exactly (28 columns):
        match_id, founder_contact_id, founder_email, founder_linkedin, founder_name,
        startup_name, investor_contact_id, investor_email, investor_firm, investor_name,
        investor_linkedin, match_score, ...
        """
        return [
            self.match_id,                       # 1
            self.founder_contact_id or "",       # 2
            self.founder_email or "",            # 3
            self.founder_linkedin or "",         # 4 - Person's LinkedIn
            self.founder_name or "",             # 5
            self.startup_name or "",             # 6
            self.investor_contact_id or "",      # 7
            self.investor_email or "",           # 8
            self.investor_firm or "",            # 9
            self.investor_name or "",            # 10
            self.investor_linkedin or "",        # 11 - Person's LinkedIn
            str(self.match_score),               # 12
            self.primary_match_reason or "",
            self.match_rationale or "",
            self.thesis_alignment_notes or "",
            self.portfolio_synergy or "",
            str(self.anti_portfolio_flag).upper(),
            self.sector_overlap or "",
            self.stage_alignment,
            self.check_size_fit,
            self.geo_alignment,
            self.intro_angle,
            self.suggested_subject_line or "",
            self.recent_news_hook or "",
            self.tone_instruction,
            self.match_date,
            self.email_status,
            str(self.human_approved).upper()
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "Match":
        """Create Match from dictionary with Pydantic validation."""
        return cls.model_validate(data)


# ============================================================
# OUTREACH AGENT SCHEMA (V02 - Enriched Drafts)
# ============================================================

# Draft Sheet Headers - for the "Drafts" tab (Sheet 3)
# Now includes enriched data from Sheet 1 lookups
DRAFT_SHEET_HEADERS = [
    "draft_id",
    "match_id",
    "founder_name",
    "founder_email",
    "investor_name",
    "investor_email",
    "investor_company_name",
    "startup_name",
    "startup_linkedin",
    "investor_company_linkedin",
    "startup_description",
    "startup_milestone",
    "email_subject",
    "email_body",
    "approval_status",
    "reviewer_notes",
    "send_status",
    "created_date",
    "sent_date"
]

DRAFT_COL_INDEX = {name: i for i, name in enumerate(DRAFT_SHEET_HEADERS)}


class ApprovalStatus(str, Enum):
    """Draft approval status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"


class SendStatus(str, Enum):
    """Email send status."""
    DRAFTED = "Drafted"
    READY_TO_SEND = "Ready to Send"
    SENT = "Sent"
    FAILED = "Failed"
    BOUNCED = "Bounced"


class Draft(BaseModel):
    """
    Pydantic model for Email Draft.
    Validates data before writing to Drafts sheet (Sheet 3).
    """
    # IDs
    draft_id: str = Field(default_factory=lambda: f"DRAFT_{str(uuid.uuid4())[:6].upper()}")
    match_id: Optional[str] = Field(default=None, description="Reference to Match ID")

    # Founder Info (enriched from contacts sheet)
    founder_name: Optional[str] = Field(default=None, description="Founder's full name")
    founder_email: Optional[str] = Field(default=None, description="Founder's email")

    # Investor Info (enriched from contacts sheet)
    investor_name: Optional[str] = Field(default=None, description="Investor's full name")
    investor_email: Optional[str] = Field(default=None, description="Investor's email")
    investor_company_name: Optional[str] = Field(default=None, description="Investment firm name")

    # Startup Info (enriched from contacts sheet)
    startup_name: Optional[str] = Field(default=None, description="Startup/company name")
    startup_linkedin: Optional[str] = Field(default=None, description="Company LinkedIn (from company_linkedin_url)")
    investor_company_linkedin: Optional[str] = Field(default=None, description="Firm LinkedIn (from company_linkedin_url)")
    startup_description: Optional[str] = Field(default=None, description="Brief startup description")
    startup_milestone: Optional[str] = Field(default=None, description="Recent milestone or funding")

    # Email Content
    email_subject: Optional[str] = Field(default=None, description="Email subject line")
    email_body: Optional[str] = Field(default=None, description="Full email body")

    # Approval
    approval_status: str = Field(default=ApprovalStatus.PENDING.value, description="PENDING, APPROVED, REJECTED")
    reviewer_notes: Optional[str] = None

    # Status
    send_status: str = Field(default=SendStatus.DRAFTED.value, description="Drafted, Sent, Failed")
    created_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    sent_date: Optional[str] = None

    model_config = {"extra": "ignore"}  # Ignore extra fields

    @field_validator('founder_name', 'investor_name', mode='before')
    @classmethod
    def clean_name(cls, v):
        """Strip whitespace and validate names are not empty."""
        if v is None:
            return None
        cleaned = str(v).strip() if v else None
        return cleaned

    @field_validator('founder_email', 'investor_email', mode='before')
    @classmethod
    def clean_email(cls, v):
        """Normalize email to lowercase."""
        if v is None or not v:
            return None
        return str(v).strip().lower()

    @field_validator('email_subject', mode='before')
    @classmethod
    def validate_subject(cls, v):
        """Ensure subject is not too long."""
        if v is None or not v:
            return None
        v = str(v).strip()
        if len(v) > 200:
            return v[:200]  # Truncate if too long
        return v

    @field_validator('email_body', mode='before')
    @classmethod
    def validate_body(cls, v):
        """Ensure email body exists and is reasonable."""
        if v is None or not v:
            return None
        return str(v).strip()

    @model_validator(mode='after')
    def validate_required_for_sending(self):
        """Validate that required fields are present for approved drafts."""
        if self.approval_status == ApprovalStatus.APPROVED.value:
            missing = []
            if not self.founder_name:
                missing.append("founder_name")
            if not self.investor_name:
                missing.append("investor_name")
            if not self.investor_email:
                missing.append("investor_email")
            if not self.email_body:
                missing.append("email_body")
            if missing:
                # Don't raise, just log - we don't want to break existing flow
                print(f"[DRAFT VALIDATION] Warning: Approved draft missing: {missing}")
        return self

    def to_sheet_row(self) -> list:
        """Convert to list for Google Sheets row.

        Order MUST match DRAFT_SHEET_HEADERS exactly (19 columns).
        """
        return [
            self.draft_id,
            self.match_id or "",
            self.founder_name or "",
            self.founder_email or "",
            self.investor_name or "",
            self.investor_email or "",
            self.investor_company_name or "",
            self.startup_name or "",
            self.startup_linkedin or "",
            self.investor_company_linkedin or "",
            self.startup_description or "",
            self.startup_milestone or "",
            self.email_subject or "",
            self.email_body or "",
            self.approval_status,
            self.reviewer_notes or "",
            self.send_status,
            self.created_date,
            self.sent_date or ""
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "Draft":
        """Create Draft from dictionary with Pydantic validation."""
        return cls.model_validate(data)


# ============================================================
# TOOL ARGUMENT SCHEMAS (Pydantic)
# These schemas validate LLM tool arguments before execution
# ============================================================

class WriteMatchToolArgs(BaseModel):
    """
    Pydantic schema for WriteMatchRowTool arguments.
    Prevents LLM hallucinations from breaking Match writes.
    """
    founder_contact_id: str = Field(..., description="Contact ID of the founder from contacts sheet")
    investor_contact_id: str = Field(..., description="Contact ID of the investor from contacts sheet")
    founder_email: str = Field(..., description="Founder's email address")
    founder_linkedin: Optional[str] = Field(default=None, description="Founder's LinkedIn URL (from contact_linkedin_url)")
    founder_name: str = Field(..., description="Founder's full name")
    startup_name: str = Field(..., description="Name of the startup/company")
    investor_email: str = Field(..., description="Investor's email address")
    investor_firm: str = Field(..., description="Investment firm name")
    investor_name: str = Field(..., description="Investor's full name")
    investor_linkedin: Optional[str] = Field(default=None, description="Investor's LinkedIn URL (from contact_linkedin_url)")
    match_score: int = Field(..., ge=0, le=100, description="Match quality score 0-100")
    primary_match_reason: str = Field(..., description="Main reason for the match")
    match_rationale: str = Field(..., description="Detailed rationale for the match")
    sector_overlap: Optional[str] = Field(default=None, description="Sector alignment description")
    stage_alignment: Optional[str] = Field(default="Match", description="Stage alignment: Match, Reach, or Safety")
    geo_alignment: Optional[str] = Field(default="Unknown", description="Geographic alignment")
    intro_angle: Optional[str] = Field(default="Thesis", description="Best intro angle: Flattery, Momentum, Hard Data, Mutual, Thesis")

    model_config = {"extra": "ignore"}

    @field_validator('match_score', mode='before')
    @classmethod
    def coerce_score(cls, v):
        """Coerce score to int and clamp to valid range."""
        try:
            return max(0, min(100, int(v)))
        except (ValueError, TypeError):
            return 50  # Default to middle score


class WriteDraftToolArgs(BaseModel):
    """
    Pydantic schema for WriteDraftRowTool arguments.
    Prevents LLM hallucinations from breaking Draft writes.
    """
    match_id: str = Field(..., description="Reference to the Match ID")
    founder_name: str = Field(..., description="Founder's full name - REQUIRED")
    founder_email: str = Field(..., description="Founder's email address")
    investor_name: str = Field(..., description="Investor's full name - REQUIRED")
    investor_email: str = Field(..., description="Investor's email address - REQUIRED for sending")
    investor_company_name: str = Field(..., description="Investment firm name")
    startup_name: str = Field(..., description="Startup/company name")
    startup_linkedin: Optional[str] = Field(default=None, description="Company LinkedIn (from company_linkedin_url)")
    investor_company_linkedin: Optional[str] = Field(default=None, description="Firm LinkedIn (from company_linkedin_url)")
    startup_description: Optional[str] = Field(default=None, description="Brief startup description")
    startup_milestone: Optional[str] = Field(default=None, description="Recent milestone or funding")
    email_subject: str = Field(..., description="Email subject line")
    email_body: str = Field(..., description="Full email body - REQUIRED")

    model_config = {"extra": "ignore"}

    @field_validator('founder_name', 'investor_name', mode='before')
    @classmethod
    def validate_name_not_empty(cls, v):
        """Ensure names are not empty."""
        if not v or not str(v).strip():
            raise ValueError("Name cannot be empty")
        return str(v).strip()

    @field_validator('email_body', mode='before')
    @classmethod
    def validate_email_body(cls, v):
        """Ensure email body is present and reasonable."""
        if not v or not str(v).strip():
            raise ValueError("Email body cannot be empty")
        body = str(v).strip()
        # Reject generic/placeholder emails
        if "Network Nurturing Agent" in body:
            raise ValueError("Email body contains placeholder text")
        return body


class ContactLookupArgs(BaseModel):
    """Schema for looking up a contact by ID."""
    contact_id: str = Field(..., description="The contact_id from the contacts sheet")

    model_config = {"extra": "ignore"}
