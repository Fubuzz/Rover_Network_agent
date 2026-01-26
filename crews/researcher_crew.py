"""
Researcher Crew for dedicated web research tasks.
Single-minded focus on finding information about people and companies.
"""

from crewai import Crew, Task, Process
from typing import Dict, Any, Optional

from agents.researcher_agent import create_researcher_agent


class ResearcherCrew:
    """Crew dedicated to research tasks."""

    def __init__(self):
        self.researcher = create_researcher_agent()

    def search_linkedin(self, name: str, company: str = None, location: str = None) -> str:
        """Find a person's LinkedIn profile."""

        context = f"Name: {name}"
        if company:
            context += f", Company: {company}"
        if location:
            context += f", Location: {location}"

        task = Task(
            description=f"""Find the LinkedIn profile for this person:

{context}

Steps:
1. Use find_linkedin_profile tool with the name and any additional context
2. If not found, try variations:
   - With just the name
   - With company added
   - With different name spellings
3. Return the LinkedIn URL if found, or explain why it couldn't be found

IMPORTANT: Only return personal LinkedIn profiles (/in/), never company pages.""",
            agent=self.researcher,
            expected_output="LinkedIn profile URL or explanation of why not found."
        )

        crew = Crew(
            agents=[self.researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return str(result)

    def research_person(self, name: str, company: str = None) -> str:
        """Comprehensive research on a person."""

        context = f"Name: {name}"
        if company:
            context += f", Company: {company}"

        task = Task(
            description=f"""Research this person comprehensively:

{context}

Find and report on:
1. LinkedIn profile URL (use find_linkedin_profile or web_search with site:linkedin.com/in)
2. Professional background and current role
3. Company information (if known)
4. Any notable achievements or news mentions
5. Social media presence if relevant

Use multiple search strategies if needed. Be thorough but concise in your report.""",
            agent=self.researcher,
            expected_output="Comprehensive research report with LinkedIn URL, background, and key findings."
        )

        crew = Crew(
            agents=[self.researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return str(result)

    def research_company(self, company_name: str) -> str:
        """Research a company comprehensively."""

        task = Task(
            description=f"""Research this company comprehensively:

Company: {company_name}

Find and report on:
1. What the company does (products/services)
2. LinkedIn company page URL
3. Industry and sector
4. Any funding information
5. Recent news or announcements
6. Key people/founders if findable

Use the research_company tool and web_search as needed.""",
            agent=self.researcher,
            expected_output="Comprehensive company research report."
        )

        crew = Crew(
            agents=[self.researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return str(result)

    def search_general(self, query: str) -> str:
        """General web search for any topic."""

        task = Task(
            description=f"""Search for information about:

Query: {query}

Perform a thorough web search and return relevant results.
Summarize the key findings in a clear, organized manner.""",
            agent=self.researcher,
            expected_output="Search results summary with key findings."
        )

        crew = Crew(
            agents=[self.researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return str(result)

    def find_contact_info(self, name: str, company: str = None) -> Dict[str, Any]:
        """Find contact information including LinkedIn, email patterns, etc."""

        context = f"Name: {name}"
        if company:
            context += f", Company: {company}"

        task = Task(
            description=f"""Find contact information for:

{context}

Search for:
1. LinkedIn profile URL (highest priority)
2. Professional email (if publicly available)
3. Company website
4. Other professional profiles (Twitter/X, GitHub, etc.)

Return structured results with any information found.""",
            agent=self.researcher,
            expected_output="Contact information including LinkedIn, email, and other profiles."
        )

        crew = Crew(
            agents=[self.researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()

        # Parse result into structured format
        result_str = str(result)
        return {
            "name": name,
            "company": company,
            "research_result": result_str,
            "linkedin_url": self._extract_linkedin_url(result_str)
        }

    def _extract_linkedin_url(self, text: str) -> Optional[str]:
        """Extract LinkedIn URL from text."""
        import re
        match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', text)
        return match.group(0) if match else None


# Global instance
_researcher_crew: Optional[ResearcherCrew] = None


def get_researcher_crew() -> ResearcherCrew:
    """Get or create researcher crew instance."""
    global _researcher_crew
    if _researcher_crew is None:
        _researcher_crew = ResearcherCrew()
    return _researcher_crew
