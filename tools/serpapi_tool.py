"""
CrewAI tool for SerpAPI web searches.
"""

from crewai.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

from services.enrichment import get_enrichment_service


class SearchPersonInput(BaseModel):
    """Input schema for searching a person."""
    name: str = Field(..., description="Person's name to search for")
    company: Optional[str] = Field(None, description="Company name to narrow search")


class SearchCompanyInput(BaseModel):
    """Input schema for searching a company."""
    company_name: str = Field(..., description="Company name to research")


class EnrichContactInput(BaseModel):
    """Input schema for enriching a contact."""
    name: str = Field(..., description="Contact's name")
    company: Optional[str] = Field(None, description="Contact's company")
    job_title: Optional[str] = Field(None, description="Contact's job title")


class SerpAPISearchPersonTool(BaseTool):
    """Tool for searching information about a person."""
    
    name: str = "search_person"
    description: str = """Search for information about a person online.
    Provide the person's name and optionally their company for more accurate results."""
    args_schema: Type[BaseModel] = SearchPersonInput
    
    def _run(self, name: str, company: str = None) -> str:
        """Search for a person online."""
        try:
            enrichment = get_enrichment_service()
            results = enrichment.search_person(name, company)
            
            if not results:
                return f"No search results found for {name}"
            
            lines = [f"**Search Results for {name}:**", ""]
            
            for i, result in enumerate(results[:5], 1):
                lines.append(f"{i}. **{result.get('title', 'No title')}**")
                lines.append(f"   {result.get('snippet', 'No description')}")
                lines.append(f"   Link: {result.get('link', 'N/A')}")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error searching for person: {str(e)}"


class SerpAPISearchCompanyTool(BaseTool):
    """Tool for researching a company."""
    
    name: str = "search_company"
    description: str = """Research a company to find information about their business, team, funding, and recent news."""
    args_schema: Type[BaseModel] = SearchCompanyInput
    
    def _run(self, company_name: str) -> str:
        """Research a company online."""
        try:
            enrichment = get_enrichment_service()
            info = enrichment.search_company(company_name)
            
            lines = [f"**Company Research: {company_name}**", ""]
            
            if info.get("linkedin_url"):
                lines.append(f"**LinkedIn:** {info['linkedin_url']}")
                lines.append("")
            
            if info.get("recent_news"):
                lines.append("**Recent News:**")
                for news in info["recent_news"]:
                    lines.append(f"- {news.get('title', 'No title')}")
                lines.append("")
            
            if info.get("search_results"):
                lines.append("**Search Results:**")
                for result in info["search_results"][:3]:
                    lines.append(f"- {result.get('title', 'No title')}")
                    lines.append(f"  {result.get('snippet', '')[:100]}...")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error researching company: {str(e)}"


class SerpAPIEnrichContactTool(BaseTool):
    """Tool for enriching contact data through web search."""
    
    name: str = "enrich_contact"
    description: str = """Enrich a contact's profile with information from web searches.
    Finds LinkedIn profile, company information, and professional background."""
    args_schema: Type[BaseModel] = EnrichContactInput
    
    def _run(self, name: str, company: str = None, job_title: str = None) -> str:
        """Enrich a contact's data through web search."""
        try:
            enrichment = get_enrichment_service()
            
            contact_data = {
                "name": name,
                "company": company,
                "job_title": job_title
            }
            
            result = enrichment.enrich_contact(contact_data)
            
            lines = [f"**Enrichment Results for {name}:**", ""]
            
            if result.get("linkedin_url"):
                lines.append(f"**LinkedIn Profile:** {result['linkedin_url']}")
            
            if result.get("summary"):
                lines.append(f"\n**Summary:** {result['summary']}")
            
            if result.get("company_info") and result["company_info"].get("linkedin_url"):
                lines.append(f"\n**Company LinkedIn:** {result['company_info']['linkedin_url']}")
            
            additional = result.get("additional_info", {})
            if additional.get("notable_achievements"):
                lines.append("\n**Notable Achievements:**")
                for achievement in additional["notable_achievements"][:3]:
                    lines.append(f"- {achievement}")
            
            if not any([result.get("linkedin_url"), result.get("summary")]):
                lines.append("Limited information found. Consider adding more context.")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error enriching contact: {str(e)}"


class SerpAPIFindLinkedInTool(BaseTool):
    """Tool for finding a person's LinkedIn profile."""
    
    name: str = "find_linkedin"
    description: str = """Find a person's LinkedIn profile URL by searching with their name and optionally company."""
    args_schema: Type[BaseModel] = SearchPersonInput
    
    def _run(self, name: str, company: str = None) -> str:
        """Find LinkedIn profile."""
        try:
            enrichment = get_enrichment_service()
            linkedin_url = enrichment.search_linkedin_profile(name, company)
            
            if linkedin_url:
                return f"Found LinkedIn profile for {name}: {linkedin_url}"
            else:
                return f"Could not find LinkedIn profile for {name}"
                
        except Exception as e:
            return f"Error finding LinkedIn: {str(e)}"
