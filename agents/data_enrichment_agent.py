"""
Data Enrichment Agent for researching and filling contact data fields.
This agent specializes in enriching contacts with comprehensive business intelligence.
"""

from crewai import Agent
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from tools.serpapi_tool import (
    SerpAPISearchPersonTool,
    SerpAPISearchCompanyTool,
    SerpAPIEnrichContactTool,
    SerpAPIFindLinkedInTool
)
from tools.ai_tool import AISummarizeEnrichmentTool


# Fields that the enrichment agent fills
ENRICHMENT_FIELDS = [
    "full_name",
    "company",
    "title",
    "linkedin_url",
    "company_description",
    "industry",
    "company_stage",
    "funding_raised",
    "linkedin_summary",
    "contact_type",
    "research_quality",
    "email",
    "phone",
    "website",
    "address",
    "key_strengths",
    "founder_score",
    "sector_fit",
    "stage_fit",
    "notes",
    "researched_date",
    "status"
]

# Contact type categories
CONTACT_TYPES = [
    "Founder",
    "Investor",
    "Tech Leader",
    "Corporate Executive",
    "Enabler",
    "Freelancer",
    "Professional",
    "Corporate Employee",
    "Company",
    "Investor Firm",
    "Accelerator"
]

# Company stages
COMPANY_STAGES = [
    "Pre-Seed",
    "Seed",
    "Series A",
    "Series B",
    "Series C+",
    "Growth",
    "Late Stage",
    "Public",
    "Public (SPAC)",
    "IPO",
    "Established",
    "Enterprise",
    "Acquired",
    "Shut Down",
    "NA"
]

# Research quality levels
RESEARCH_QUALITY_LEVELS = ["High", "Medium", "Low"]


def create_data_enrichment_agent() -> Agent:
    """Create the Data Enrichment Agent specialized in filling contact fields."""

    tools = [
        SerpAPISearchPersonTool(),
        SerpAPISearchCompanyTool(),
        SerpAPIEnrichContactTool(),
        SerpAPIFindLinkedInTool(),
        AISummarizeEnrichmentTool()
    ]

    return Agent(
        role="Contact Data Enrichment Specialist",
        goal="""Enrich contact data by researching people and companies online.
        Fill in missing fields with accurate, up-to-date information.
        Return comprehensive enrichment data in structured JSON format.""",
        backstory="""You are an expert at finding and verifying professional information online.
You specialize in enriching contact databases with business intelligence.

Your job is to take a contact name (and optionally company) and find:
- Full name and professional title
- Company information (description, industry, stage, funding)
- LinkedIn profile URL and summary
- Contact type classification (Founder, Investor, Executive, etc.)
- Website, location, and other relevant details

IMPORTANT RULES:
1. Always return data in valid JSON format
2. Use "NA" for fields you cannot find - never leave fields empty
3. Set research_quality to "High", "Medium", or "Low" based on data confidence
4. Set status to "Enriched", "Partial", or "Failed" based on completeness
5. Always include researched_date as the current date
6. Be accurate - don't make up information
7. If a name is too common or vague, acknowledge the limitation

You are thorough but honest about what you can and cannot find.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_data_enrichment_tools() -> List:
    """Get the list of tools for the data enrichment agent."""
    return [
        SerpAPISearchPersonTool(),
        SerpAPISearchCompanyTool(),
        SerpAPIEnrichContactTool(),
        SerpAPIFindLinkedInTool(),
        AISummarizeEnrichmentTool()
    ]


def create_empty_enrichment_result(name: str = None, company: str = None) -> Dict[str, Any]:
    """Create an empty enrichment result with NA values."""
    return {
        "full_name": name or "NA",
        "company": company or "NA",
        "title": "NA",
        "linkedin_url": "NA",
        "company_description": "NA",
        "industry": "NA",
        "company_stage": "NA",
        "funding_raised": "NA",
        "linkedin_summary": "NA",
        "contact_type": "NA",
        "research_quality": "Low",
        "email": "NA",
        "phone": "NA",
        "website": "NA",
        "address": "NA",
        "key_strengths": "NA",
        "notes": "NA",
        "researched_date": datetime.now().strftime("%Y-%m-%d"),
        "status": "Failed"
    }


def parse_enrichment_input(user_input: str) -> Dict[str, str]:
    """
    Parse user enrichment input to extract name and company.

    Examples:
    - "enrich John Doe" -> {"name": "John Doe"}
    - "enrich John from TechCorp" -> {"name": "John", "company": "TechCorp"}
    - "enrich Ahmed Abbas SAIB" -> {"name": "Ahmed Abbas", "company": "SAIB"}
    """
    # Remove common prefixes
    input_clean = user_input.lower().strip()
    for prefix in ["enrich", "research", "lookup", "find"]:
        if input_clean.startswith(prefix):
            input_clean = user_input[len(prefix):].strip()
            break
    else:
        input_clean = user_input.strip()

    result = {"name": input_clean, "company": None}

    # Check for "from" pattern: "John from TechCorp"
    if " from " in input_clean.lower():
        parts = input_clean.lower().split(" from ")
        result["name"] = input_clean[:input_clean.lower().find(" from ")].strip()
        result["company"] = input_clean[input_clean.lower().find(" from ") + 6:].strip()

    # Check for "at" pattern: "John at TechCorp"
    elif " at " in input_clean.lower():
        parts = input_clean.lower().split(" at ")
        result["name"] = input_clean[:input_clean.lower().find(" at ")].strip()
        result["company"] = input_clean[input_clean.lower().find(" at ") + 4:].strip()

    # Check for parenthetical info: "Sarah Jones (Freelance Designer)"
    elif "(" in input_clean and ")" in input_clean:
        paren_start = input_clean.find("(")
        paren_end = input_clean.find(")")
        result["name"] = input_clean[:paren_start].strip()
        result["company"] = input_clean[paren_start+1:paren_end].strip()

    return result


def format_enrichment_output(data: Dict[str, Any]) -> str:
    """Format enrichment data as a nice JSON string for display."""
    # Ensure all required fields exist
    for field in ENRICHMENT_FIELDS:
        if field not in data:
            data[field] = "NA"

    # Format as pretty JSON
    return json.dumps(data, indent=2, ensure_ascii=False)


def validate_enrichment_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize enrichment data."""
    validated = {}

    for field in ENRICHMENT_FIELDS:
        value = data.get(field)

        # Normalize empty values to NA
        if value is None or value == "" or value == "null":
            validated[field] = "NA"
        else:
            validated[field] = str(value).strip()

    # Ensure valid status
    if validated.get("status") not in ["Enriched", "Partial", "Failed"]:
        # Determine status based on filled fields
        non_na_count = sum(1 for v in validated.values() if v != "NA")
        if non_na_count > 10:
            validated["status"] = "Enriched"
        elif non_na_count > 5:
            validated["status"] = "Partial"
        else:
            validated["status"] = "Failed"

    # Ensure valid research_quality
    if validated.get("research_quality") not in RESEARCH_QUALITY_LEVELS:
        validated["research_quality"] = "Low"

    # Ensure researched_date is set
    if validated.get("researched_date") == "NA":
        validated["researched_date"] = datetime.now().strftime("%Y-%m-%d")

    return validated


def needs_enrichment(contact_data: Dict[str, Any]) -> bool:
    """Check if a contact needs enrichment based on missing fields."""
    # Key fields that indicate a contact needs enrichment
    key_fields = [
        "company",
        "title",
        "linkedin_url",
        "industry",
        "company_description"
    ]

    for field in key_fields:
        value = contact_data.get(field)
        if not value or value == "NA" or value.strip() == "":
            return True

    # Check if enrichment was never done
    if not contact_data.get("researched_date"):
        return True

    return False


def get_contacts_needing_enrichment(contacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter contacts that need enrichment."""
    return [c for c in contacts if needs_enrichment(c)]
