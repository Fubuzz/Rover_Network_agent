"""
Contact Crew for handling contact management workflows.
"""

from crewai import Crew, Task, Process
from typing import Dict, Any, Optional

from agents.contact_agent import create_contact_agent
from agents.classification_agent import create_classification_agent
from agents.evaluation_agent import create_evaluation_agent


class ContactCrew:
    """Crew for contact management operations."""
    
    def __init__(self):
        self.contact_agent = create_contact_agent()
        self.classification_agent = create_classification_agent()
        self.evaluation_agent = create_evaluation_agent()
    
    def add_contact(self, contact_data: Dict[str, Any]) -> str:
        """Add a new contact with classification and evaluation."""
        
        # Task 1: Add the contact
        add_task = Task(
            description=f"""Add a new contact with the following information:
            Name: {contact_data.get('name', 'Unknown')}
            Job Title: {contact_data.get('job_title', 'N/A')}
            Company: {contact_data.get('company', 'N/A')}
            Phone: {contact_data.get('phone', 'N/A')}
            Email: {contact_data.get('email', 'N/A')}
            LinkedIn: {contact_data.get('linkedin_url', 'N/A')}
            Location: {contact_data.get('location', 'N/A')}
            Notes: {contact_data.get('notes', 'N/A')}
            
            First validate the contact data, then add it to the database.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was added successfully with any validation notes."
        )
        
        # Task 2: Classify the contact
        classify_task = Task(
            description=f"""Classify the newly added contact:
            Name: {contact_data.get('name', 'Unknown')}
            Job Title: {contact_data.get('job_title', 'N/A')}
            Company: {contact_data.get('company', 'N/A')}
            
            Determine if they are a founder, investor, enabler, or professional.
            Provide confidence score and reasoning.""",
            agent=self.classification_agent,
            expected_output="Classification result with category, confidence, and reasoning.",
            context=[add_task]
        )
        
        # Task 3: Evaluate data quality
        evaluate_task = Task(
            description=f"""Evaluate the data quality of the contact:
            Name: {contact_data.get('name', 'Unknown')}
            
            Assess completeness and accuracy. Provide recommendations for improvement.""",
            agent=self.evaluation_agent,
            expected_output="Data quality assessment with score and recommendations.",
            context=[add_task, classify_task]
        )
        
        crew = Crew(
            agents=[self.contact_agent, self.classification_agent, self.evaluation_agent],
            tasks=[add_task, classify_task, evaluate_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def update_contact(self, name: str, field: str, value: str) -> str:
        """Update a contact field."""
        
        update_task = Task(
            description=f"""Update the contact named '{name}':
            Field to update: {field}
            New value: {value}
            
            First verify the contact exists, then update the specified field.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was updated successfully."
        )
        
        crew = Crew(
            agents=[self.contact_agent],
            tasks=[update_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def view_contact(self, name: str) -> str:
        """View contact details with quality assessment."""
        
        view_task = Task(
            description=f"""Retrieve and display all information for the contact named '{name}'.
            Include all available fields and metadata.""",
            agent=self.contact_agent,
            expected_output="Complete contact information formatted for display."
        )
        
        quality_task = Task(
            description=f"""Assess the data quality of the contact '{name}'.
            Provide a quality score and any recommendations for improvement.""",
            agent=self.evaluation_agent,
            expected_output="Data quality assessment with actionable recommendations.",
            context=[view_task]
        )
        
        crew = Crew(
            agents=[self.contact_agent, self.evaluation_agent],
            tasks=[view_task, quality_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def search_contacts(self, query: str) -> str:
        """Search for contacts."""
        
        search_task = Task(
            description=f"""Search for contacts matching: '{query}'
            Return a list of matching contacts with key information.""",
            agent=self.contact_agent,
            expected_output="List of matching contacts with names, companies, and classifications."
        )
        
        crew = Crew(
            agents=[self.contact_agent],
            tasks=[search_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def delete_contact(self, name: str) -> str:
        """Delete a contact."""
        
        # This would typically require user confirmation first
        delete_task = Task(
            description=f"""Delete the contact named '{name}' from the database.
            First confirm the contact exists, then remove it.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was deleted."
        )
        
        crew = Crew(
            agents=[self.contact_agent],
            tasks=[delete_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)


# Global crew instance
_contact_crew: Optional[ContactCrew] = None


def get_contact_crew() -> ContactCrew:
    """Get or create the contact crew instance."""
    global _contact_crew
    if _contact_crew is None:
        _contact_crew = ContactCrew()
    return _contact_crew
