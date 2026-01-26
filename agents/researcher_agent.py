"""
Dedicated Researcher Agent for comprehensive web research.
Single-minded focus on finding information about people and companies.
"""

from crewai import Agent
from typing import List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type

from services.enrichment import get_enrichment_service


# =============================================================================
# RESEARCH QUERY EXAMPLES
# =============================================================================
# These examples help the agent understand how to construct effective queries

LINKEDIN_SEARCH_EXAMPLES = """
FINDING LINKEDIN PROFILES - Query Patterns:

1. Basic person search:
   Query: "site:linkedin.com/in {name}"
   Example: "site:linkedin.com/in Ahmed Abaza"

2. Person at specific company:
   Query: "site:linkedin.com/in {name} {company}"
   Example: "site:linkedin.com/in John Smith Google"

3. Person with title:
   Query: "site:linkedin.com/in {name} {title}"
   Example: "site:linkedin.com/in Sarah Johnson CEO"

4. Person in location:
   Query: "site:linkedin.com/in {name} {location}"
   Example: "site:linkedin.com/in Ahmed Abaza Egypt"

5. Combined search (most effective):
   Query: "site:linkedin.com/in {name} {company} {location}"
   Example: "site:linkedin.com/in Ahmed Abaza Synapse Analytics Cairo"
"""

COMPANY_SEARCH_EXAMPLES = """
RESEARCHING COMPANIES - Query Patterns:

1. Company LinkedIn page:
   Query: "site:linkedin.com/company {company_name}"
   Example: "site:linkedin.com/company Synapse Analytics"

2. Company information:
   Query: "{company_name} company about"
   Example: "Synapse Analytics company about"

3. Company funding/investors:
   Query: "{company_name} funding raised investors"
   Example: "Synapse Analytics funding raised investors"

4. Company news:
   Query: "{company_name} news announcement"
   Example: "Synapse Analytics news announcement"

5. Company products/services:
   Query: "{company_name} products services customers"
   Example: "Synapse Analytics products services customers"

6. Company industry/sector:
   Query: "{company_name} industry sector"
   Example: "Synapse Analytics fintech analytics"
"""

GENERAL_RESEARCH_EXAMPLES = """
GENERAL RESEARCH - Query Patterns:

1. Person background:
   Query: "{name} {company} background experience"
   Example: "Ahmed Abaza Synapse background experience"

2. Recent news about person:
   Query: "{name} news interview {year}"
   Example: "Ahmed Abaza news interview 2024"

3. Speaking engagements:
   Query: "{name} speaker conference talk"
   Example: "Ahmed Abaza speaker conference talk"

4. Publications/articles:
   Query: "{name} article published wrote"
   Example: "Ahmed Abaza article published wrote"

5. Social media presence:
   Query: "{name} twitter github portfolio"
   Example: "Ahmed Abaza twitter github portfolio"
"""


# =============================================================================
# RESEARCHER TOOLS
# =============================================================================

class WebSearchInput(BaseModel):
    """Input for web search."""
    query: str = Field(..., description="The search query to execute")
    num_results: int = Field(default=10, description="Number of results to return")


class LinkedInSearchInput(BaseModel):
    """Input for LinkedIn search."""
    name: str = Field(..., description="Person's name to search for")
    company: Optional[str] = Field(None, description="Company name to narrow search")
    location: Optional[str] = Field(None, description="Location to narrow search")


class CompanyResearchInput(BaseModel):
    """Input for company research."""
    company_name: str = Field(..., description="Company name to research")
    aspect: Optional[str] = Field(None, description="Specific aspect: 'funding', 'news', 'products', 'team'")


class WebSearchTool(BaseTool):
    """General web search tool."""
    name: str = "web_search"
    description: str = """Search the web for any information.
    Use this for general queries about people, companies, topics, or anything else.

    Tips for effective searches:
    - Be specific with names and companies
    - Add context like location, title, or year
    - Use quotes for exact phrases
    """
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, num_results: int = 10) -> str:
        """Execute web search."""
        try:
            enrichment = get_enrichment_service()
            results = enrichment._search(query, num_results)

            if not results:
                return f"No results found for: {query}\n\nTry:\n- Different keywords\n- Adding company name\n- Adding location"

            output = [f"**Search Results for:** {query}\n"]
            for i, r in enumerate(results[:num_results], 1):
                output.append(f"{i}. **{r.get('title', 'No title')}**")
                output.append(f"   {r.get('snippet', '')[:200]}")
                output.append(f"   Link: {r.get('link', 'N/A')}")
                output.append("")

            return "\n".join(output)
        except Exception as e:
            return f"Search error: {str(e)}"


class LinkedInFinderTool(BaseTool):
    """Specialized tool for finding LinkedIn profiles."""
    name: str = "find_linkedin_profile"
    description: str = """Find a person's LinkedIn profile URL.

    Provide the person's name and optionally their company/location for better results.

    Examples:
    - find_linkedin_profile("Ahmed Abaza")
    - find_linkedin_profile("John Smith", company="Google")
    - find_linkedin_profile("Sarah Johnson", company="Meta", location="San Francisco")
    """
    args_schema: Type[BaseModel] = LinkedInSearchInput

    def _run(self, name: str, company: str = None, location: str = None) -> str:
        """Find LinkedIn profile."""
        try:
            enrichment = get_enrichment_service()

            # Build optimized query
            query = f"site:linkedin.com/in {name}"
            if company:
                query += f" {company}"
            if location:
                query += f" {location}"

            results = enrichment._search(query, 10)

            # Filter for personal profiles only
            profiles_found = []
            for r in results:
                link = r.get("link", "")
                if "/in/" in link and "/company/" not in link:
                    profiles_found.append({
                        "url": link,
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", "")
                    })

            if not profiles_found:
                suggestions = [
                    f"No LinkedIn profile found for {name}.",
                    "",
                    "Suggestions:",
                    f"- Try with full name if you used nickname",
                    f"- Add company name: find_linkedin_profile(\"{name}\", company=\"CompanyName\")",
                    f"- Add location: find_linkedin_profile(\"{name}\", location=\"Cairo\")",
                    f"- Check spelling of the name"
                ]
                return "\n".join(suggestions)

            output = [f"**LinkedIn Profiles Found for {name}:**\n"]
            for i, p in enumerate(profiles_found[:5], 1):
                output.append(f"{i}. {p['title']}")
                output.append(f"   URL: {p['url']}")
                if p['snippet']:
                    output.append(f"   {p['snippet'][:150]}...")
                output.append("")

            # Highlight the best match
            output.append(f"**Best Match:** {profiles_found[0]['url']}")

            return "\n".join(output)
        except Exception as e:
            return f"LinkedIn search error: {str(e)}"


class CompanyResearchTool(BaseTool):
    """Specialized tool for researching companies."""
    name: str = "research_company"
    description: str = """Research a company to find information about them.

    Can find:
    - Company description and what they do
    - LinkedIn company page
    - Recent news and announcements
    - Funding information
    - Products and services
    - Key team members

    Examples:
    - research_company("Synapse Analytics")
    - research_company("Synapse Analytics", aspect="funding")
    - research_company("Synapse Analytics", aspect="products")
    """
    args_schema: Type[BaseModel] = CompanyResearchInput

    def _run(self, company_name: str, aspect: str = None) -> str:
        """Research a company."""
        try:
            enrichment = get_enrichment_service()

            output = [f"**Company Research: {company_name}**\n"]

            # Build queries based on aspect
            if aspect == "funding":
                query = f"{company_name} funding raised investors series"
            elif aspect == "news":
                query = f"{company_name} news announcement 2024"
            elif aspect == "products":
                query = f"{company_name} products services customers"
            elif aspect == "team":
                query = f"{company_name} founders team leadership"
            else:
                query = f"{company_name} company about"

            results = enrichment._search(query, 10)

            if results:
                output.append(f"**Search: {query}**")
                for i, r in enumerate(results[:5], 1):
                    output.append(f"{i}. {r.get('title', 'No title')}")
                    output.append(f"   {r.get('snippet', '')[:200]}")
                    output.append(f"   {r.get('link', '')}")
                    output.append("")

            # Also search for LinkedIn company page
            linkedin_query = f"site:linkedin.com/company {company_name}"
            linkedin_results = enrichment._search(linkedin_query, 3)

            for r in linkedin_results:
                link = r.get("link", "")
                if "/company/" in link:
                    output.append(f"**LinkedIn Company Page:** {link}")
                    break

            if not results and not linkedin_results:
                return f"No information found for company: {company_name}\n\nTry:\n- Check spelling\n- Use the official company name\n- Try alternative names (Inc., LLC removed)"

            return "\n".join(output)
        except Exception as e:
            return f"Company research error: {str(e)}"


class PersonResearchTool(BaseTool):
    """Comprehensive person research tool."""
    name: str = "research_person"
    description: str = """Research a person comprehensively.

    Finds:
    - LinkedIn profile
    - Professional background
    - Company information
    - News mentions
    - Social media presence

    Examples:
    - research_person("Ahmed Abaza")
    - research_person("John Smith", company="Google")
    """
    args_schema: Type[BaseModel] = LinkedInSearchInput

    def _run(self, name: str, company: str = None, location: str = None) -> str:
        """Research a person comprehensively."""
        try:
            enrichment = get_enrichment_service()
            output = [f"**Comprehensive Research: {name}**\n"]

            # 1. Find LinkedIn
            linkedin_query = f"site:linkedin.com/in {name}"
            if company:
                linkedin_query += f" {company}"
            linkedin_results = enrichment._search(linkedin_query, 5)

            linkedin_url = None
            for r in linkedin_results:
                link = r.get("link", "")
                if "/in/" in link:
                    linkedin_url = link
                    output.append(f"**LinkedIn:** {link}")
                    if r.get("snippet"):
                        output.append(f"Summary: {r.get('snippet', '')[:200]}")
                    break

            if not linkedin_url:
                output.append("**LinkedIn:** Not found")

            output.append("")

            # 2. General background search
            bg_query = f"{name}"
            if company:
                bg_query += f" {company}"
            bg_results = enrichment._search(bg_query, 10)

            if bg_results:
                output.append("**Background Information:**")
                for i, r in enumerate(bg_results[:3], 1):
                    if "linkedin.com" not in r.get("link", ""):
                        output.append(f"- {r.get('title', 'No title')}")
                        output.append(f"  {r.get('snippet', '')[:150]}")
                output.append("")

            # 3. News mentions
            news_query = f"{name} news"
            if company:
                news_query += f" {company}"
            news_results = enrichment._search(news_query, 5)

            news_found = []
            for r in news_results:
                link = r.get("link", "")
                if "linkedin.com" not in link and "facebook.com" not in link:
                    news_found.append(r)

            if news_found:
                output.append("**Recent News/Mentions:**")
                for r in news_found[:2]:
                    output.append(f"- {r.get('title', 'No title')}")
                    output.append(f"  {r.get('link', '')}")

            return "\n".join(output)
        except Exception as e:
            return f"Person research error: {str(e)}"


# =============================================================================
# RESEARCHER AGENT
# =============================================================================

def create_researcher_agent() -> Agent:
    """Create the dedicated Researcher Agent."""

    tools = [
        WebSearchTool(),
        LinkedInFinderTool(),
        CompanyResearchTool(),
        PersonResearchTool(),
    ]

    backstory = f"""You are a world-class research specialist with expertise in finding
information about professionals and companies. You have a single-minded focus on
delivering accurate, comprehensive research results.

Your expertise includes:
- Finding LinkedIn profiles with high accuracy
- Researching company backgrounds, funding, and news
- Discovering professional backgrounds and achievements
- Cross-referencing multiple sources for accuracy

RESEARCH METHODOLOGY:

{LINKEDIN_SEARCH_EXAMPLES}

{COMPANY_SEARCH_EXAMPLES}

{GENERAL_RESEARCH_EXAMPLES}

IMPORTANT GUIDELINES:
1. Always start with the most specific search possible
2. If initial search fails, try variations (different spelling, add/remove company)
3. For LinkedIn searches, use "site:linkedin.com/in" for people
4. For company pages, use "site:linkedin.com/company"
5. Cross-reference information from multiple results
6. Clearly state when information cannot be found
7. Suggest alternative search strategies if needed

You are thorough, accurate, and persistent in your research."""

    return Agent(
        role="Research Specialist",
        goal="Find comprehensive, accurate information about people and companies through web research. Always provide LinkedIn profiles when possible.",
        backstory=backstory,
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True,
        max_iter=5  # Allow multiple search attempts
    )


def get_researcher_tools() -> List:
    """Get the list of researcher tools."""
    return [
        WebSearchTool(),
        LinkedInFinderTool(),
        CompanyResearchTool(),
        PersonResearchTool(),
    ]
