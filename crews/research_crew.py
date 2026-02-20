"""
Research Crew - Orchestrates deep contact research.

This crew coordinates research tasks:
1. LinkedIn profile discovery
2. Company intelligence gathering
3. Person background research
4. Data synthesis and validation
"""

from crewai import Crew, Task, Process
from typing import Optional, Dict, Any
import logging

from agents.research_agent import create_research_agent, DEEP_RESEARCH_TASK
from services.research_engine import get_research_engine
from services.ai_research_synthesizer import get_synthesizer
from data.research_schema import ResearchRequest, ResearchResult


logger = logging.getLogger('research_crew')


class ResearchCrew:
    """
    Orchestrates comprehensive contact research.
    
    This crew can be called directly for research tasks,
    providing a high-level interface to the research engine.
    """
    
    def __init__(self):
        self.engine = get_research_engine()
        self.synthesizer = get_synthesizer()
        self._crew = None
        self._agent = None
    
    def _ensure_crew(self):
        """Lazily initialize the CrewAI crew."""
        if self._crew is None:
            self._agent = create_research_agent()
            # We'll create tasks dynamically based on the request
    
    def research_person(self, name: str, company: str = None,
                       context: str = None) -> ResearchResult:
        """
        Perform comprehensive research on a person.
        
        This is the main entry point for research.
        Returns structured data ready for contact creation.
        """
        logger.info(f"[CREW] Starting research for: {name} (company: {company})")
        
        request = ResearchRequest(
            name=name,
            company=company,
            context_notes=context,
            depth="standard"
        )
        
        # Use the research engine directly (faster than CrewAI for this)
        result = self.engine.research(request)
        
        # Optionally enhance with AI synthesis
        if result.raw_search_results:
            result = self.synthesizer.enrich_research_result(
                result, 
                result.raw_search_results
            )
        
        logger.info(
            f"[CREW] Research complete: {name} - "
            f"confidence={result.overall_confidence.value}, "
            f"completeness={result.completeness_score:.0%}"
        )
        
        return result
    
    def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Research a company for detailed information.
        """
        logger.info(f"[CREW] Researching company: {company_name}")
        
        company = self.engine.quick_company_search(company_name)
        
        if not company:
            return {"error": f"Could not find information about {company_name}"}
        
        return {
            "name": company.name,
            "website": company.website,
            "linkedin_url": company.linkedin_url,
            "industry": company.industry,
            "company_size": company.company_size,
            "headquarters": company.headquarters,
            "funding_stage": company.funding_stage,
            "total_funding": company.total_funding,
            "description": company.description,
            "founders": company.founders,
            "investors": company.investors,
            "confidence": company.confidence.value
        }
    
    def find_linkedin(self, name: str, company: str = None) -> Optional[str]:
        """
        Quick LinkedIn profile lookup.
        """
        return self.engine.quick_linkedin_search(name, company)
    
    def research_for_contact_creation(self, name: str, company: str = None,
                                      known_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Research specifically for creating a contact record.
        
        Returns a dict that can be directly used to create/update a Contact.
        """
        logger.info(f"[CREW] Research for contact creation: {name}")
        
        # Build request with known data
        request = ResearchRequest(
            name=name,
            company=company,
            known_title=known_data.get("title") if known_data else None,
            known_email=known_data.get("email") if known_data else None,
            known_location=known_data.get("location") if known_data else None,
            known_linkedin=known_data.get("linkedin_url") if known_data else None,
            depth="standard"
        )
        
        # Research
        result = self.engine.research(request)
        
        # Get contact field mapping
        mapping = result.get_contact_field_mapping()
        
        # Add metadata
        mapping["_research_confidence"] = result.overall_confidence.value
        mapping["_research_completeness"] = f"{result.completeness_score:.0%}"
        mapping["_warnings"] = result.warnings
        mapping["_research_notes"] = result.research_notes
        
        return mapping
    
    def get_research_summary(self, name: str, company: str = None) -> str:
        """
        Get a human-readable research summary.
        """
        result = self.research_person(name, company)
        return result.get_research_summary()

    def scrape_linkedin_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape a LinkedIn profile directly for comprehensive data.

        Requires LINKEDIN_SCRAPER_ENABLED=true and LinkedIn credentials in .env.

        Args:
            profile_url: Full LinkedIn profile URL

        Returns:
            Dict with profile data or error message
        """
        from config import LinkedInConfig, FeatureFlags

        if not FeatureFlags.LINKEDIN_SCRAPER:
            return {"error": "LinkedIn scraper is disabled. Set LINKEDIN_SCRAPER_ENABLED=true in .env."}

        if not LinkedInConfig.is_configured():
            return {"error": "LinkedIn credentials not configured. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env."}

        try:
            from services.linkedin_scraper import LinkedInScraperService

            scraper = LinkedInScraperService(
                headless=LinkedInConfig.LINKEDIN_HEADLESS,
                page_timeout=LinkedInConfig.LINKEDIN_PAGE_TIMEOUT,
                element_timeout=LinkedInConfig.LINKEDIN_ELEMENT_TIMEOUT,
                linkedin_email=LinkedInConfig.LINKEDIN_EMAIL,
                linkedin_password=LinkedInConfig.LINKEDIN_PASSWORD,
                user_data_dir=LinkedInConfig.CHROME_USER_DATA_DIR or None,
            )

            profile = scraper.scrape_profile_data(profile_url)

            return {
                "name": profile.name,
                "headline": profile.headline,
                "about": profile.about,
                "location": profile.location,
                "experience": profile.experience,
                "education": profile.education,
                "skills": profile.skills,
                "certifications": profile.certifications,
                "source": "linkedin_scraper",
                "confidence": "high"
            }
        except Exception as e:
            logger.error(f"LinkedIn scraping failed: {e}")
            return {"error": str(e)}


def create_research_crew() -> Crew:
    """
    Create a CrewAI crew for research tasks.
    
    This creates a full CrewAI setup for more complex research workflows.
    For simple lookups, use ResearchCrew directly.
    """
    agent = create_research_agent()
    
    # Default task (will be customized per request)
    default_task = Task(
        description="Research the target person comprehensively",
        expected_output="Structured research findings with confidence scores",
        agent=agent
    )
    
    return Crew(
        agents=[agent],
        tasks=[default_task],
        process=Process.sequential,
        verbose=True
    )


# Global instance
_research_crew: Optional[ResearchCrew] = None


def get_research_crew() -> ResearchCrew:
    """Get or create the research crew instance."""
    global _research_crew
    if _research_crew is None:
        _research_crew = ResearchCrew()
    return _research_crew


# Convenience functions
def research_person(name: str, company: str = None) -> ResearchResult:
    """Quick access to person research."""
    return get_research_crew().research_person(name, company)


def find_linkedin(name: str, company: str = None) -> Optional[str]:
    """Quick access to LinkedIn search."""
    return get_research_crew().find_linkedin(name, company)


def research_company(company_name: str) -> Dict[str, Any]:
    """Quick access to company research."""
    return get_research_crew().research_company(company_name)


def scrape_linkedin_profile(profile_url: str) -> Dict[str, Any]:
    """Quick access to LinkedIn profile scraping."""
    return get_research_crew().scrape_linkedin_profile(profile_url)
