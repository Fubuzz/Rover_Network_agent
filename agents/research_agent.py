"""
Deep Research Agent for comprehensive contact research.

This agent specializes in:
1. Finding LinkedIn profiles and professional information
2. Researching companies for context
3. Cross-validating information from multiple sources
4. Returning structured data ready for contact fields
"""

from crewai import Agent
from typing import List

from tools.deep_research_tool import (
    DeepPersonResearchTool,
    LinkedInSearchTool,
    CompanyResearchTool,
    ExtractContactFieldsTool
)


def create_research_agent() -> Agent:
    """
    Create the Deep Research Agent.
    
    This agent is designed to be thorough, accurate, and systematic
    in researching people and companies.
    """
    
    tools = [
        DeepPersonResearchTool(),
        LinkedInSearchTool(),
        CompanyResearchTool(),
        ExtractContactFieldsTool()
    ]
    
    return Agent(
        role="Senior Research Analyst",
        goal="""Conduct comprehensive, accurate research on people and companies.
        Find reliable information from multiple sources, cross-validate findings,
        and return structured data that can be directly used to populate contact profiles.
        Never make up information - only report what is found in actual sources.""",
        backstory="""You are a senior research analyst with 15 years of experience 
        in business intelligence and due diligence. You've worked for top investment firms
        and executive search companies, where accuracy is non-negotiable.
        
        Your methodology:
        1. Always start with LinkedIn - it's the most reliable professional source
        2. Cross-reference with company websites and news sources
        3. Verify titles and roles against multiple sources before confirming
        4. Classify contacts accurately (Founder vs Investor vs Enabler)
        5. Never guess or fabricate information - if uncertain, say so
        
        You're known for your thoroughness and your ability to find hard-to-get information.
        You understand that bad data is worse than no data, so you prioritize accuracy over speed.
        
        Key principles:
        - LinkedIn URL: Only provide if you found the actual profile
        - Contact Type: Founders have started companies, Investors work at VC/PE/Angel firms
        - Company Data: Always verify funding claims with news sources
        - Email: Only include if found in public sources (rare)
        """,
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def create_fast_research_agent() -> Agent:
    """
    Create a fast research agent for quick lookups.
    
    This agent prioritizes speed over depth - useful for
    quick LinkedIn lookups and basic verification.
    """
    
    tools = [
        LinkedInSearchTool(),
        CompanyResearchTool()
    ]
    
    return Agent(
        role="Quick Research Assistant",
        goal="""Quickly find key information about people and companies.
        Focus on LinkedIn profiles and basic company info. 
        Be fast and accurate - skip deep dives.""",
        backstory="""You're a fast researcher who can quickly find the essentials.
        You specialize in rapid LinkedIn lookups and basic company verification.
        You know that sometimes a quick answer is more valuable than a perfect one.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=False  # Stateless for speed
    )


def get_research_agent_tools() -> List:
    """Get the list of tools for the research agent."""
    return [
        DeepPersonResearchTool(),
        LinkedInSearchTool(),
        CompanyResearchTool(),
        ExtractContactFieldsTool()
    ]


# Research task templates
DEEP_RESEARCH_TASK = """
Research the following person comprehensively:

**Name:** {name}
**Company (if known):** {company}
**Additional Context:** {context}

Your task:
1. Find their LinkedIn profile URL
2. Determine their current title and company
3. Research their company for context
4. Classify them: Founder, Investor, or Enabler
5. Find any additional relevant information

Return your findings in this EXACT format:

## RESEARCH FINDINGS

### Person
- Name: [Full name]
- Title: [Current title]
- Company: [Current company]
- LinkedIn: [LinkedIn URL if found]
- Location: [City, Country if found]
- Contact Type: [Founder/Investor/Enabler]
- Seniority: [C-Level/VP/Director/Manager/IC]

### Company
- Name: [Company name]
- Industry: [Industry]
- Stage: [Funding stage if applicable]
- Website: [Company website if found]

### Research Summary
[2-3 sentences about this person's background and relevance]

### Data Confidence
- LinkedIn Verified: [Yes/No]
- Title Verified: [Yes/No]  
- Company Verified: [Yes/No]
- Overall Confidence: [High/Medium/Low]

### Warnings
[Any data quality concerns or unverified information]
"""


QUICK_LINKEDIN_TASK = """
Find the LinkedIn profile for:

**Name:** {name}
**Company (for context):** {company}

Return ONLY the LinkedIn URL if found, or "Not found" if not.
Do not guess or provide similar profiles - only the exact person.
"""


COMPANY_RESEARCH_TASK = """
Research this company:

**Company Name:** {company}

Find:
1. Company LinkedIn page
2. Website
3. Industry
4. Funding stage and amount (if startup)
5. Key information

Return structured company data.
"""
