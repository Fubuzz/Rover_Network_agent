"""
Enrichment Agent for researching and enriching contact data.
"""

from crewai import Agent
from typing import List

from tools.serpapi_tool import (
    SerpAPISearchPersonTool,
    SerpAPISearchCompanyTool,
    SerpAPIEnrichContactTool,
    SerpAPIFindLinkedInTool
)
from tools.ai_tool import AISummarizeEnrichmentTool


def create_enrichment_agent() -> Agent:
    """Create the Enrichment Agent."""
    
    tools = [
        SerpAPISearchPersonTool(),
        SerpAPISearchCompanyTool(),
        SerpAPIEnrichContactTool(),
        SerpAPIFindLinkedInTool(),
        AISummarizeEnrichmentTool()
    ]
    
    return Agent(
        role="Research Specialist",
        goal="Enrich contact data through comprehensive online research, finding LinkedIn profiles, company information, and professional background details.",
        backstory="""You are a skilled research analyst with expertise in finding and verifying professional information.
You have access to powerful search tools and know how to find relevant information about people and companies.
You are thorough in your research, cross-referencing multiple sources to ensure accuracy.
You focus on gathering actionable insights that help build stronger professional relationships.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_enrichment_agent_tools() -> List:
    """Get the list of tools for the enrichment agent."""
    return [
        SerpAPISearchPersonTool(),
        SerpAPISearchCompanyTool(),
        SerpAPIEnrichContactTool(),
        SerpAPIFindLinkedInTool(),
        AISummarizeEnrichmentTool()
    ]
