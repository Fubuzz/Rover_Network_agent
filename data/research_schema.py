"""
Research Result Schemas - Structured output for deep research.

These schemas ensure research data is:
1. Structured and typed
2. Confidence-scored
3. Source-attributed
4. Directly mappable to Contact fields
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Confidence level for extracted data."""
    HIGH = "high"        # Multiple sources confirm, direct evidence
    MEDIUM = "medium"    # Single reliable source or indirect evidence
    LOW = "low"          # Inferred or single unreliable source
    UNVERIFIED = "unverified"  # Found but not validated


class DataSource(str, Enum):
    """Source of research data."""
    LINKEDIN_PROFILE = "linkedin_profile"
    LINKEDIN_COMPANY = "linkedin_company"
    COMPANY_WEBSITE = "company_website"
    NEWS_ARTICLE = "news_article"
    CRUNCHBASE = "crunchbase"
    PITCHBOOK = "pitchbook"
    TWITTER = "twitter"
    GOOGLE_SEARCH = "google_search"
    AI_INFERENCE = "ai_inference"
    USER_PROVIDED = "user_provided"


class SourcedValue(BaseModel):
    """A value with its source and confidence."""
    value: str
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    source: DataSource = DataSource.GOOGLE_SEARCH
    source_url: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.now)
    
    def __str__(self):
        return self.value


class LinkedInProfile(BaseModel):
    """Structured LinkedIn profile data."""
    profile_url: Optional[str] = None
    headline: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    connections: Optional[int] = None
    summary: Optional[str] = None
    
    # Professional history
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    
    # Engagement signals
    posts_about: List[str] = Field(default_factory=list)
    shared_interests: List[str] = Field(default_factory=list)
    
    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    is_verified_profile: bool = False


class CompanyIntelligence(BaseModel):
    """Structured company research data."""
    name: str
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    
    # Basic info
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None  # "11-50", "51-200", etc.
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    company_type: Optional[str] = None  # Startup, Enterprise, SMB
    
    # Funding & financials
    funding_stage: Optional[str] = None  # Seed, Series A, B, C, etc.
    total_funding: Optional[str] = None
    last_funding_date: Optional[str] = None
    investors: List[str] = Field(default_factory=list)
    valuation: Optional[str] = None
    
    # Key people
    founders: List[str] = Field(default_factory=list)
    executives: List[Dict[str, str]] = Field(default_factory=list)  # [{name, title}]
    
    # Market position
    competitors: List[str] = Field(default_factory=list)
    customers: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    
    # Recent activity
    recent_news: List[Dict[str, str]] = Field(default_factory=list)  # [{title, url, date}]
    press_releases: List[Dict[str, str]] = Field(default_factory=list)
    
    # Signals
    hiring_signals: List[str] = Field(default_factory=list)
    growth_signals: List[str] = Field(default_factory=list)
    
    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    data_freshness: Optional[str] = None  # When was this data current


class PersonIntelligence(BaseModel):
    """Structured person research data."""
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    # Current role
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    department: Optional[str] = None
    
    # Contact info
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Online presence
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    personal_website: Optional[str] = None
    
    # Location
    location: Optional[str] = None
    timezone: Optional[str] = None
    
    # Professional background
    years_experience: Optional[int] = None
    previous_companies: List[str] = Field(default_factory=list)
    expertise_areas: List[str] = Field(default_factory=list)
    
    # Classification
    contact_type: Optional[str] = None  # Founder, Investor, Enabler
    seniority: Optional[str] = None  # C-Level, VP, Director, Manager, IC
    
    # Bio & summary
    professional_summary: Optional[str] = None
    key_achievements: List[str] = Field(default_factory=list)
    
    # Recent activity
    recent_mentions: List[Dict[str, str]] = Field(default_factory=list)
    speaking_engagements: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    
    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED


class ResearchResult(BaseModel):
    """
    Complete research result for a contact.
    This is the main output that maps directly to Contact fields.
    """
    # Search metadata
    search_query: str
    search_timestamp: datetime = Field(default_factory=datetime.now)
    research_duration_seconds: float = 0.0
    sources_consulted: int = 0
    
    # Person data
    person: Optional[PersonIntelligence] = None
    linkedin_profile: Optional[LinkedInProfile] = None
    
    # Company data
    company: Optional[CompanyIntelligence] = None
    
    # Direct field mappings with confidence
    # These map directly to Contact schema fields
    field_mappings: Dict[str, SourcedValue] = Field(default_factory=dict)
    
    # Overall quality
    overall_confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    completeness_score: float = 0.0  # 0-1, how many fields were found
    accuracy_indicators: List[str] = Field(default_factory=list)
    
    # Warnings & notes
    warnings: List[str] = Field(default_factory=list)
    research_notes: List[str] = Field(default_factory=list)
    
    # Raw data for debugging
    raw_search_results: List[Dict[str, Any]] = Field(default_factory=list)
    
    def get_contact_field_mapping(self) -> Dict[str, Any]:
        """
        Get a dict that maps directly to Contact schema fields.
        Only includes high/medium confidence fields.
        """
        mapping = {}
        
        # Map from field_mappings
        for field_name, sourced_value in self.field_mappings.items():
            if sourced_value.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]:
                mapping[field_name] = sourced_value.value
        
        # Add from person intelligence
        if self.person:
            if self.person.full_name:
                mapping.setdefault('full_name', self.person.full_name)
            if self.person.first_name:
                mapping.setdefault('first_name', self.person.first_name)
            if self.person.last_name:
                mapping.setdefault('last_name', self.person.last_name)
            if self.person.current_title:
                mapping.setdefault('title', self.person.current_title)
            if self.person.current_company:
                mapping.setdefault('company', self.person.current_company)
            if self.person.email:
                mapping.setdefault('email', self.person.email)
            if self.person.phone:
                mapping.setdefault('phone', self.person.phone)
            if self.person.linkedin_url:
                mapping.setdefault('linkedin_url', self.person.linkedin_url)
            if self.person.location:
                mapping.setdefault('address', self.person.location)
            if self.person.contact_type:
                mapping.setdefault('contact_type', self.person.contact_type)
            if self.person.professional_summary:
                mapping.setdefault('linkedin_summary', self.person.professional_summary)
            if self.person.expertise_areas:
                mapping.setdefault('key_strengths', ', '.join(self.person.expertise_areas[:5]))
        
        # Add from LinkedIn profile
        if self.linkedin_profile:
            if self.linkedin_profile.profile_url:
                mapping.setdefault('linkedin_url', self.linkedin_profile.profile_url)
            if self.linkedin_profile.current_title:
                mapping.setdefault('title', self.linkedin_profile.current_title)
            if self.linkedin_profile.current_company:
                mapping.setdefault('company', self.linkedin_profile.current_company)
            if self.linkedin_profile.location:
                mapping.setdefault('address', self.linkedin_profile.location)
            if self.linkedin_profile.summary:
                mapping.setdefault('linkedin_summary', self.linkedin_profile.summary[:500])
        
        # Add from company intelligence
        if self.company:
            if self.company.linkedin_url:
                mapping.setdefault('company_linkedin_url', self.company.linkedin_url)
            if self.company.website:
                mapping.setdefault('website', self.company.website)
            if self.company.description:
                mapping.setdefault('company_description', self.company.description[:500])
            if self.company.industry:
                mapping.setdefault('industry', self.company.industry)
            if self.company.funding_stage:
                mapping.setdefault('company_stage', self.company.funding_stage)
            if self.company.total_funding:
                mapping.setdefault('funding_raised', self.company.total_funding)
            if self.company.headquarters:
                mapping.setdefault('address', self.company.headquarters)
        
        return mapping
    
    def get_research_summary(self) -> str:
        """Generate a human-readable research summary."""
        lines = []
        
        # Person summary
        if self.person:
            lines.append(f"**{self.person.full_name}**")
            if self.person.current_title and self.person.current_company:
                lines.append(f"{self.person.current_title} at {self.person.current_company}")
            if self.person.location:
                lines.append(f"📍 {self.person.location}")
            if self.person.professional_summary:
                lines.append(f"\n{self.person.professional_summary[:200]}...")
        
        # LinkedIn
        if self.linkedin_profile and self.linkedin_profile.profile_url:
            lines.append(f"\n🔗 LinkedIn: {self.linkedin_profile.profile_url}")
        
        # Company summary
        if self.company:
            lines.append(f"\n**Company: {self.company.name}**")
            if self.company.industry:
                lines.append(f"Industry: {self.company.industry}")
            if self.company.funding_stage:
                lines.append(f"Stage: {self.company.funding_stage}")
            if self.company.total_funding:
                lines.append(f"Funding: {self.company.total_funding}")
        
        # Quality indicators
        lines.append(f"\n**Research Quality:** {self.overall_confidence.value}")
        lines.append(f"**Completeness:** {self.completeness_score:.0%}")
        lines.append(f"**Sources:** {self.sources_consulted}")
        
        if self.warnings:
            lines.append(f"\n⚠️ {'; '.join(self.warnings)}")
        
        return '\n'.join(lines)
    
    def calculate_completeness(self) -> float:
        """Calculate how complete the research is."""
        key_fields = [
            self.person and self.person.full_name,
            self.person and self.person.current_title,
            self.person and self.person.current_company,
            self.person and self.person.linkedin_url,
            self.person and self.person.location,
            self.person and self.person.contact_type,
            self.company and self.company.description,
            self.company and self.company.industry,
        ]
        filled = sum(1 for f in key_fields if f)
        self.completeness_score = filled / len(key_fields)
        return self.completeness_score


class ResearchRequest(BaseModel):
    """Request for research with context."""
    name: str
    company: Optional[str] = None
    
    # Known data to help narrow search
    known_title: Optional[str] = None
    known_email: Optional[str] = None
    known_location: Optional[str] = None
    known_linkedin: Optional[str] = None
    
    # Research options
    depth: str = "standard"  # quick, standard, deep
    prioritize_fields: List[str] = Field(default_factory=list)  # Fields to focus on
    skip_company_research: bool = False
    
    # Context
    context_notes: Optional[str] = None  # Additional context for search
