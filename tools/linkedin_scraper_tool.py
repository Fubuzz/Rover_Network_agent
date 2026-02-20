"""
LinkedIn Profile Scraper Tool for CrewAI.

Provides direct LinkedIn profile data extraction via browser automation.
This is a heavyweight tool that opens a Chrome browser to scrape full profile data
including experience, education, skills, and certifications.
"""

import logging
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from config import LinkedInConfig, FeatureFlags


logger = logging.getLogger('linkedin_scraper_tool')


class LinkedInProfileScraperInput(BaseModel):
    """Input for LinkedIn profile scraping."""
    profile_url: str = Field(
        description="Full LinkedIn profile URL (e.g., https://www.linkedin.com/in/username)"
    )


class LinkedInProfileScraperTool(BaseTool):
    """
    Scrape a LinkedIn profile for comprehensive data.

    This tool opens a Chrome browser to directly scrape LinkedIn profile data.
    It extracts: name, headline, about, location, full experience history,
    education, all skills, and certifications.

    Use this ONLY when you have a specific LinkedIn profile URL and need
    detailed profile data. For just finding a LinkedIn URL, use linkedin_search.
    """
    name: str = "scrape_linkedin_profile"
    description: str = """Scrape a LinkedIn profile page to extract detailed profile data.

    Requires a full LinkedIn profile URL (e.g., https://www.linkedin.com/in/username).

    Returns comprehensive profile data including:
    - Name, headline, about section, location
    - Full work experience history (all roles with titles, companies, durations, descriptions)
    - Education history (schools, degrees, dates)
    - Complete skills list
    - Certifications and licenses

    WARNING: This is slow (10-30 seconds). Only use when you need detailed profile data.
    For just finding a LinkedIn URL, use linkedin_search instead."""
    args_schema: Type[BaseModel] = LinkedInProfileScraperInput

    def _run(self, profile_url: str) -> str:
        """Execute LinkedIn profile scraping."""
        logger.info(f"[TOOL] scrape_linkedin_profile: {profile_url}")

        # Validate feature flag
        if not FeatureFlags.LINKEDIN_SCRAPER:
            return (
                "LinkedIn scraper is disabled. "
                "Set LINKEDIN_SCRAPER_ENABLED=true in .env to enable it."
            )

        # Validate configuration
        if not LinkedInConfig.is_configured():
            return (
                "LinkedIn credentials not configured. "
                "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env file."
            )

        # Validate URL format
        if "linkedin.com/in/" not in profile_url:
            return (
                f"Invalid LinkedIn profile URL: {profile_url}. "
                "URL must contain 'linkedin.com/in/' "
                "(e.g., https://www.linkedin.com/in/username)"
            )

        try:
            # Lazy import to avoid requiring selenium at module load time
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
            return self._format_profile(profile, profile_url)

        except ImportError as e:
            return (
                f"LinkedIn scraper dependencies not installed: {e}. "
                "Run: pip install selenium undetected-chromedriver beautifulsoup4 lxml"
            )
        except RuntimeError as e:
            return f"LinkedIn scraping failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error scraping LinkedIn: {e}", exc_info=True)
            return f"LinkedIn scraping error: {str(e)}"

    def _format_profile(self, profile, profile_url: str) -> str:
        """Format scraped profile data for agent consumption."""
        lines = []

        lines.append("## LINKEDIN PROFILE DATA (Scraped)")
        lines.append(f"**URL:** {profile_url}")
        lines.append("")

        # Basic info
        lines.append("### BASIC INFO")
        if profile.name:
            lines.append(f"- **Name:** {profile.name}")
        if profile.headline:
            lines.append(f"- **Headline:** {profile.headline}")
        if profile.location:
            lines.append(f"- **Location:** {profile.location}")
        if profile.about:
            lines.append(f"- **About:** {profile.about[:500]}")
        lines.append("")

        # Experience
        if profile.experience:
            lines.append(f"### EXPERIENCE ({len(profile.experience)} roles)")
            for i, exp in enumerate(profile.experience, 1):
                title = exp.get('title', 'Unknown')
                company = exp.get('company', 'Unknown')
                duration = exp.get('duration', '')
                description = exp.get('description', '')
                lines.append(f"**{i}. {title}** at {company}")
                if duration:
                    lines.append(f"   Duration: {duration}")
                if description:
                    lines.append(f"   {description[:200]}")
            lines.append("")

        # Education
        if profile.education:
            lines.append(f"### EDUCATION ({len(profile.education)} entries)")
            for edu in profile.education:
                school = edu.get('school', 'Unknown')
                degree = edu.get('degree', '')
                duration = edu.get('duration', '')
                line = f"- **{school}**"
                if degree:
                    line += f" - {degree}"
                if duration:
                    line += f" ({duration})"
                lines.append(line)
            lines.append("")

        # Skills
        if profile.skills:
            lines.append(f"### SKILLS ({len(profile.skills)} total)")
            lines.append(", ".join(profile.skills))
            lines.append("")

        # Certifications
        if profile.certifications:
            lines.append(f"### CERTIFICATIONS ({len(profile.certifications)} total)")
            for cert in profile.certifications:
                name = cert.get('name', 'Unknown')
                issuer = cert.get('issuer', '')
                date = cert.get('date', '')
                line = f"- **{name}**"
                if issuer:
                    line += f" by {issuer}"
                if date:
                    line += f" ({date})"
                lines.append(line)
            lines.append("")

        # Data quality summary
        lines.append("### DATA QUALITY")
        lines.append(f"- Experience entries: {len(profile.experience)}")
        lines.append(f"- Education entries: {len(profile.education)}")
        lines.append(f"- Skills found: {len(profile.skills)}")
        lines.append(f"- Certifications: {len(profile.certifications)}")
        lines.append(f"- Source: Direct LinkedIn scraping (high confidence)")

        return "\n".join(lines)


# Tool instance for easy import
linkedin_profile_scraper_tool = LinkedInProfileScraperTool()


def get_linkedin_scraper_tools():
    """Get LinkedIn scraper tools for agent use."""
    return [LinkedInProfileScraperTool()]
