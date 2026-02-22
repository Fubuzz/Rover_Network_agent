"""
Deep Research Tools for CrewAI.

These tools provide comprehensive research capabilities:
1. LinkedIn profile search and extraction
2. Company intelligence gathering
3. Person research and enrichment
4. Cross-source validation
"""

import logging
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from services.research_engine import get_research_engine
from services.ai_research_synthesizer import get_synthesizer
from data.research_schema import ResearchRequest, ResearchResult


logger = logging.getLogger('deep_research_tools')


class DeepPersonResearchInput(BaseModel):
    """Input for deep person research."""
    name: str = Field(description="Full name of the person to research")
    company: Optional[str] = Field(default=None, description="Company name for context (optional)")
    known_title: Optional[str] = Field(default=None, description="Known job title (optional)")
    known_location: Optional[str] = Field(default=None, description="Known location (optional)")


class DeepPersonResearchTool(BaseTool):
    """
    Comprehensive person research tool.
    
    Performs multi-source research including:
    - LinkedIn profile search
    - Professional background research
    - Company context research
    - Cross-validation of data
    
    Returns structured data ready for contact storage.
    """
    name: str = "deep_person_research"
    description: str = """
    Perform comprehensive research on a person.
    
    This tool will:
    1. Find their LinkedIn profile
    2. Research their professional background
    3. Research their company
    4. Classify them (Founder/Investor/Enabler)
    5. Return all findings in a structured format
    
    Use this when you need to find detailed information about someone.
    The results can be directly used to populate contact fields.
    """
    args_schema: Type[BaseModel] = DeepPersonResearchInput
    
    def _run(self, name: str, company: Optional[str] = None,
             known_title: Optional[str] = None, known_location: Optional[str] = None) -> str:
        """Execute deep person research."""
        logger.info(f"[TOOL] deep_person_research: {name} (company: {company})")
        
        engine = get_research_engine()
        
        request = ResearchRequest(
            name=name,
            company=company,
            known_title=known_title,
            known_location=known_location,
            depth="standard"
        )
        
        result = engine.research(request)
        
        # Format result for agent consumption
        return self._format_result(result)
    
    def _format_result(self, result: ResearchResult) -> str:
        """Format research result for agent consumption."""
        lines = []
        
        lines.append("## RESEARCH RESULTS")
        lines.append(f"**Query:** {result.search_query}")
        lines.append(f"**Confidence:** {result.overall_confidence.value}")
        lines.append(f"**Completeness:** {result.completeness_score:.0%}")
        lines.append("")
        
        # Person data
        if result.person:
            lines.append("### PERSON DATA")
            lines.append(f"- **Name:** {result.person.full_name}")
            if result.person.current_title:
                lines.append(f"- **Title:** {result.person.current_title}")
            if result.person.current_company:
                lines.append(f"- **Company:** {result.person.current_company}")
            if result.person.location:
                lines.append(f"- **Location:** {result.person.location}")
            if result.person.email:
                lines.append(f"- **Email:** {result.person.email}")
            if result.person.phone:
                lines.append(f"- **Phone:** {result.person.phone}")
            if result.person.linkedin_url:
                lines.append(f"- **LinkedIn:** {result.person.linkedin_url}")
            if result.person.contact_type:
                lines.append(f"- **Contact Type:** {result.person.contact_type}")
            if result.person.seniority:
                lines.append(f"- **Seniority:** {result.person.seniority}")
            if result.person.expertise_areas:
                lines.append(f"- **Expertise:** {', '.join(result.person.expertise_areas[:5])}")
            if result.person.professional_summary:
                lines.append(f"- **Summary:** {result.person.professional_summary[:300]}...")
            lines.append("")
        
        # LinkedIn profile
        if result.linkedin_profile and result.linkedin_profile.profile_url:
            lines.append("### LINKEDIN PROFILE")
            lines.append(f"- **URL:** {result.linkedin_profile.profile_url}")
            if result.linkedin_profile.headline:
                lines.append(f"- **Headline:** {result.linkedin_profile.headline}")
            lines.append("")
        
        # Company data
        if result.company:
            lines.append("### COMPANY DATA")
            lines.append(f"- **Name:** {result.company.name}")
            if result.company.website:
                lines.append(f"- **Website:** {result.company.website}")
            if result.company.linkedin_url:
                lines.append(f"- **Company LinkedIn:** {result.company.linkedin_url}")
            if result.company.industry:
                lines.append(f"- **Industry:** {result.company.industry}")
            if result.company.company_size:
                lines.append(f"- **Size:** {result.company.company_size}")
            if result.company.headquarters:
                lines.append(f"- **HQ:** {result.company.headquarters}")
            if result.company.funding_stage:
                lines.append(f"- **Stage:** {result.company.funding_stage}")
            if result.company.total_funding:
                lines.append(f"- **Funding:** {result.company.total_funding}")
            if result.company.description:
                lines.append(f"- **Description:** {result.company.description[:200]}...")
            lines.append("")
        
        # Field mappings for easy use
        lines.append("### CONTACT FIELD MAPPINGS")
        lines.append("Use these to update the contact:")
        mappings = result.get_contact_field_mapping()
        for field, value in mappings.items():
            if value:
                lines.append(f"- {field}: {value}")
        
        # Warnings
        if result.warnings:
            lines.append("")
            lines.append("### WARNINGS")
            for w in result.warnings:
                lines.append(f"⚠️ {w}")
        
        # Research notes
        if result.research_notes:
            lines.append("")
            lines.append("### NOTES")
            for n in result.research_notes:
                lines.append(f"- {n}")
        
        return "\n".join(lines)


class LinkedInSearchInput(BaseModel):
    """Input for LinkedIn search."""
    name: str = Field(description="Name of the person")
    company: Optional[str] = Field(default=None, description="Company for context (optional)")


class LinkedInSearchTool(BaseTool):
    """
    Quick LinkedIn profile search tool.
    
    Finds a person's LinkedIn profile URL.
    Faster than full research when you just need the LinkedIn URL.
    """
    name: str = "linkedin_search"
    description: str = """
    Search for a person's LinkedIn profile URL.
    
    Use this when you specifically need to find someone's LinkedIn profile.
    Returns just the LinkedIn URL if found.
    """
    args_schema: Type[BaseModel] = LinkedInSearchInput
    
    def _run(self, name: str, company: Optional[str] = None) -> str:
        """Execute LinkedIn search."""
        logger.info(f"[TOOL] linkedin_search: {name} (company: {company})")
        
        engine = get_research_engine()
        url = engine.quick_linkedin_search(name, company)
        
        if url:
            return f"**LinkedIn Found:** {url}"
        return f"Could not find LinkedIn profile for {name}. Try deep_person_research for more comprehensive search."


class CompanyResearchInput(BaseModel):
    """Input for company research."""
    company_name: str = Field(description="Name of the company to research")


class CompanyResearchTool(BaseTool):
    """
    Company intelligence research tool.
    
    Researches a company to find:
    - LinkedIn page
    - Website
    - Industry
    - Funding information
    - Key details
    """
    name: str = "company_research"
    description: str = """
    Research a company for detailed information.
    
    Returns company intelligence including:
    - LinkedIn URL
    - Website
    - Industry
    - Funding stage/amount
    - Description
    - Size and location
    """
    args_schema: Type[BaseModel] = CompanyResearchInput
    
    def _run(self, company_name: str) -> str:
        """Execute company research."""
        logger.info(f"[TOOL] company_research: {company_name}")
        
        engine = get_research_engine()
        company = engine.quick_company_search(company_name)
        
        if not company:
            return f"Could not find information about {company_name}."
        
        lines = [f"## Company: {company.name}"]
        
        if company.website:
            lines.append(f"- **Website:** {company.website}")
        if company.linkedin_url:
            lines.append(f"- **LinkedIn:** {company.linkedin_url}")
        if company.industry:
            lines.append(f"- **Industry:** {company.industry}")
        if company.company_size:
            lines.append(f"- **Size:** {company.company_size}")
        if company.headquarters:
            lines.append(f"- **HQ:** {company.headquarters}")
        if company.funding_stage:
            lines.append(f"- **Stage:** {company.funding_stage}")
        if company.total_funding:
            lines.append(f"- **Total Funding:** {company.total_funding}")
        if company.description:
            lines.append(f"- **About:** {company.description[:300]}...")
        if company.founders:
            lines.append(f"- **Founders:** {', '.join(company.founders)}")
        if company.investors:
            lines.append(f"- **Investors:** {', '.join(company.investors[:5])}")
        
        return "\n".join(lines)


class ExtractContactFieldsInput(BaseModel):
    """Input for field extraction."""
    research_text: str = Field(description="Raw research text to extract fields from")
    contact_name: str = Field(description="Name of the contact for context")


class ExtractContactFieldsTool(BaseTool):
    """
    AI-powered field extraction tool.
    
    Uses AI to extract structured contact fields from raw research text.
    """
    name: str = "extract_contact_fields"
    description: str = """
    Extract structured contact fields from research text.
    
    Use this after web searches to extract specific fields like:
    - LinkedIn URL
    - Email
    - Phone
    - Title
    - Company
    - Location
    
    Returns a structured mapping of fields to values.
    """
    args_schema: Type[BaseModel] = ExtractContactFieldsInput
    
    def _run(self, research_text: str, contact_name: str) -> str:
        """Extract fields using AI."""
        logger.info(f"[TOOL] extract_contact_fields for {contact_name}")
        
        synthesizer = get_synthesizer()
        
        # Format as fake search results for the synthesizer
        fake_results = [{"title": "Research", "content": research_text}]
        
        result = synthesizer.synthesize_research(
            name=contact_name,
            search_results=fake_results
        )
        
        if "error" in result:
            return f"Could not extract fields: {result['error']}"
        
        lines = ["## Extracted Fields"]
        
        if "person" in result and result["person"]:
            person = result["person"]
            for field, value in person.items():
                if value and value != "Unknown" and not isinstance(value, list):
                    lines.append(f"- **{field}:** {value}")
        
        if "company" in result and result["company"]:
            lines.append("\n### Company Fields")
            company = result["company"]
            for field, value in company.items():
                if value and value != "Unknown" and not isinstance(value, list):
                    lines.append(f"- **{field}:** {value}")
        
        return "\n".join(lines)


def get_research_tools():
    """Get all research tools for agent use."""
    return [
        DeepPersonResearchTool(),
        LinkedInSearchTool(),
        CompanyResearchTool(),
        ExtractContactFieldsTool()
    ]
