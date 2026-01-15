"""
Enrichment Crew for researching and enriching contact data.
Enhanced with comprehensive data enrichment capabilities.
"""

import json
from crewai import Crew, Task, Process
from typing import Dict, Any, Optional, List
from datetime import datetime

from agents.enrichment_agent import create_enrichment_agent
from agents.data_enrichment_agent import (
    create_data_enrichment_agent,
    parse_enrichment_input,
    needs_enrichment,
    get_contacts_needing_enrichment
)
from agents.evaluation_agent import create_evaluation_agent
from agents.contact_agent import create_contact_agent
from services.enrichment import get_enrichment_service
from services.google_sheets import get_sheets_service


class EnrichmentCrew:
    """Crew for contact enrichment workflows."""

    def __init__(self):
        self.enrichment_agent = create_enrichment_agent()
        self.data_enrichment_agent = create_data_enrichment_agent()
        self.evaluation_agent = create_evaluation_agent()
        self.contact_agent = create_contact_agent()
        self._enrichment_service = None

    @property
    def enrichment_service(self):
        if self._enrichment_service is None:
            self._enrichment_service = get_enrichment_service()
        return self._enrichment_service
    
    def enrich_contact(self, name: str, company: str = None) -> str:
        """Enrich a contact with online research."""
        
        # Task 1: Get current contact info
        get_task = Task(
            description=f"""Retrieve the current information for contact '{name}'.
            We need this to understand what data we already have.""",
            agent=self.contact_agent,
            expected_output="Current contact information."
        )
        
        # Task 2: Enrich with research
        enrich_task = Task(
            description=f"""Research and enrich the contact:
            Name: {name}
            Company: {company or 'Unknown'}
            
            Find:
            1. LinkedIn profile URL
            2. Professional background
            3. Company information
            4. Recent news or achievements
            
            Provide a comprehensive enrichment report.""",
            agent=self.enrichment_agent,
            expected_output="Enrichment report with LinkedIn, background, company info, and news.",
            context=[get_task]
        )
        
        # Task 3: Evaluate enriched data
        evaluate_task = Task(
            description=f"""Evaluate the quality and accuracy of the enriched data for '{name}'.
            Verify the information looks accurate and complete.""",
            agent=self.evaluation_agent,
            expected_output="Evaluation of enriched data quality.",
            context=[enrich_task]
        )
        
        # Task 4: Update contact with enriched data
        update_task = Task(
            description=f"""Update the contact '{name}' with the enriched information.
            Add any new LinkedIn URLs, company info, or notes discovered.""",
            agent=self.contact_agent,
            expected_output="Confirmation that contact was updated with enriched data.",
            context=[enrich_task, evaluate_task]
        )
        
        crew = Crew(
            agents=[self.contact_agent, self.enrichment_agent, self.evaluation_agent],
            tasks=[get_task, enrich_task, evaluate_task, update_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def research_company(self, company_name: str) -> str:
        """Research a company."""
        
        research_task = Task(
            description=f"""Research the company '{company_name}'.
            Find:
            1. Company LinkedIn page
            2. Recent news and updates
            3. Key information (industry, size, funding if available)
            4. Notable people at the company
            
            Provide a comprehensive company research report.""",
            agent=self.enrichment_agent,
            expected_output="Company research report with all available information."
        )
        
        crew = Crew(
            agents=[self.enrichment_agent],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def find_linkedin(self, name: str, company: str = None) -> str:
        """Find a person's LinkedIn profile."""

        find_task = Task(
            description=f"""Find the LinkedIn profile for:
            Name: {name}
            Company: {company or 'Unknown'}

            Search for their LinkedIn profile URL.""",
            agent=self.enrichment_agent,
            expected_output="LinkedIn profile URL or indication that it wasn't found."
        )

        crew = Crew(
            agents=[self.enrichment_agent],
            tasks=[find_task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return str(result)

    def enrich_contact_comprehensive(self, user_input: str) -> Dict[str, Any]:
        """
        Perform comprehensive contact enrichment from user input.
        Parses input to extract name and company, then enriches.
        Returns structured enrichment data.
        """
        # Parse input to extract name and company
        parsed = parse_enrichment_input(user_input)
        name = parsed.get("name", "")
        company = parsed.get("company")

        if not name:
            return {
                "full_name": "NA",
                "status": "Failed",
                "notes": "No name provided for enrichment."
            }

        # Use enrichment service for comprehensive enrichment
        result = self.enrichment_service.enrich_contact_comprehensive(name, company)
        return result

    def enrich_contact_data(self, name: str, company: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich a contact with comprehensive data.
        Returns structured JSON enrichment data.
        """
        return self.enrichment_service.enrich_contact_comprehensive(name, company)

    def enrich_and_update_contact(self, name: str, company: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich a contact and update it in the database.
        Returns enrichment result and update status.
        """
        # Get enrichment data
        enrichment = self.enrichment_service.enrich_contact_comprehensive(name, company)

        # Try to update the contact in Google Sheets
        update_success = False
        try:
            sheets = get_sheets_service()
            sheets._ensure_initialized()

            # Map enrichment fields to contact fields
            updates = {}

            # Only add non-NA values
            # Map enrichment fields to Google Sheet columns
            field_mappings = {
                "title": "title",
                "contact_linkedin_url": "linkedin_url",  # Personal LinkedIn -> linkedin_url column
                "company_linkedin_url": "linkedin_link",  # Company LinkedIn -> linkedin_link column
                "company_description": "company_description",
                "industry": "industry",
                "company_stage": "company_stage",
                "funding_raised": "funding_raised",
                "linkedin_summary": "linkedin_summary",
                "contact_type": "contact_type",  # Founder, Enabler, or Investor
                "website": "website",
                "address": "address",
                "key_strengths": "key_strengths",
                "founder_score": "founder_score",
                "sector_fit": "sector_fit",
                "company": "company",
            }

            for enrich_field, sheet_field in field_mappings.items():
                value = enrichment.get(enrich_field)
                if value and value != "NA":
                    updates[sheet_field] = value

            # Always add these fields
            if enrichment.get("research_quality"):
                updates["research_quality"] = enrichment["research_quality"]
            if enrichment.get("researched_date"):
                updates["researched_date"] = enrichment["researched_date"]

            if updates:
                # Try to find and update the contact
                update_success = sheets.update_contact(name, updates)

                # If not found by full name, try first name
                if not update_success and " " in name:
                    first_name = name.split()[0]
                    update_success = sheets.update_contact(first_name, updates)

                print(f"Update result for {name}: {update_success}, updates: {list(updates.keys())}")

        except Exception as e:
            print(f"Failed to update contact in sheets: {e}")
            import traceback
            traceback.print_exc()

        return {
            "enrichment": enrichment,
            "updated_in_db": update_success
        }

    def enrich_bulk(self, contacts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Enrich multiple contacts in bulk.
        If no contacts provided, fetches all contacts needing enrichment.
        """
        if contacts is None:
            # Get all contacts from sheets that need enrichment
            try:
                sheets = get_sheets_service()
                sheets._ensure_initialized()
                all_contacts = sheets.get_all_contacts()

                # Filter to those needing enrichment
                contacts_data = [c.to_dict() for c in all_contacts]
                contacts = get_contacts_needing_enrichment(contacts_data)
            except Exception as e:
                return {
                    "error": f"Failed to fetch contacts: {e}",
                    "total": 0,
                    "enriched": 0
                }

        return self.enrichment_service.enrich_contacts_bulk(contacts)

    def get_contacts_needing_enrichment(self) -> List[Dict[str, Any]]:
        """Get list of contacts that need enrichment."""
        try:
            sheets = get_sheets_service()
            sheets._ensure_initialized()
            all_contacts = sheets.get_all_contacts()

            result = []
            for contact in all_contacts:
                contact_dict = contact.to_dict()
                if needs_enrichment(contact_dict):
                    result.append({
                        "name": contact.name,
                        "company": contact.company,
                        "missing_fields": self._get_missing_fields(contact_dict)
                    })

            return result
        except Exception as e:
            print(f"Error getting contacts needing enrichment: {e}")
            return []

    def _get_missing_fields(self, contact: Dict[str, Any]) -> List[str]:
        """Get list of missing/empty fields for a contact."""
        key_fields = ["company", "title", "linkedin_url", "industry",
                      "company_description", "contact_type"]
        missing = []
        for field in key_fields:
            value = contact.get(field)
            if not value or value == "NA" or str(value).strip() == "":
                missing.append(field)
        return missing

    def format_enrichment_output(self, enrichment: Dict[str, Any]) -> str:
        """Format enrichment data as a nice display string."""
        name = enrichment.get("full_name", "Unknown")

        output = f"Running enrichment for {name}...\n\n"
        output += json.dumps(enrichment, indent=2, ensure_ascii=False)

        return output


# Global crew instance
_enrichment_crew: Optional[EnrichmentCrew] = None


def get_enrichment_crew() -> EnrichmentCrew:
    """Get or create the enrichment crew instance."""
    global _enrichment_crew
    if _enrichment_crew is None:
        _enrichment_crew = EnrichmentCrew()
    return _enrichment_crew
