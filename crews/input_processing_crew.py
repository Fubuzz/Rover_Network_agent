"""
Input Processing Crew for handling various input types.
"""

from crewai import Crew, Task, Process
from typing import Optional

from agents.input_agent import create_input_agent
from agents.contact_agent import create_contact_agent
from agents.classification_agent import create_classification_agent
from agents.evaluation_agent import create_evaluation_agent


class InputProcessingCrew:
    """Crew for processing various input types."""
    
    def __init__(self):
        self.input_agent = create_input_agent()
        self.contact_agent = create_contact_agent()
        self.classification_agent = create_classification_agent()
        self.evaluation_agent = create_evaluation_agent()
    
    def process_text(self, text: str) -> str:
        """Process natural language text to extract and add contact."""
        
        # Task 1: Parse the text
        parse_task = Task(
            description=f"""Parse the following text to extract contact information:
            
            {text}
            
            Extract: name, job title, company, phone, email, LinkedIn, location, and any other details.""",
            agent=self.input_agent,
            expected_output="Structured contact information extracted from the text."
        )
        
        # Task 2: Add the contact
        add_task = Task(
            description="""Add the extracted contact information to the database.
            Validate the data before adding.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was added.",
            context=[parse_task]
        )
        
        # Task 3: Classify
        classify_task = Task(
            description="""Classify the newly added contact.
            Determine if they are a founder, investor, enabler, or professional.""",
            agent=self.classification_agent,
            expected_output="Classification result with category and confidence.",
            context=[parse_task, add_task]
        )
        
        crew = Crew(
            agents=[self.input_agent, self.contact_agent, self.classification_agent],
            tasks=[parse_task, add_task, classify_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def process_voice(self, transcript: str) -> str:
        """Process a voice transcript to extract and add contact."""
        
        # Task 1: Parse voice transcript
        parse_task = Task(
            description=f"""Parse the following voice transcript to extract contact information:
            
            "{transcript}"
            
            Handle common speech patterns and extract structured data.""",
            agent=self.input_agent,
            expected_output="Structured contact information extracted from the voice transcript."
        )
        
        # Task 2: Validate and add
        add_task = Task(
            description="""Validate and add the extracted contact to the database.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was added.",
            context=[parse_task]
        )
        
        # Task 3: Classify
        classify_task = Task(
            description="""Classify the contact based on the extracted information.""",
            agent=self.classification_agent,
            expected_output="Classification with category and confidence.",
            context=[parse_task, add_task]
        )
        
        crew = Crew(
            agents=[self.input_agent, self.contact_agent, self.classification_agent],
            tasks=[parse_task, add_task, classify_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def process_image(self, image_description: str) -> str:
        """Process image extraction results to add contact."""
        
        # Task 1: Parse image extraction
        parse_task = Task(
            description=f"""Parse the following information extracted from an image:
            
            {image_description}
            
            Structure the data as contact information.""",
            agent=self.input_agent,
            expected_output="Structured contact information from image extraction."
        )
        
        # Task 2: Validate and add
        add_task = Task(
            description="""Validate and add the contact from the image to the database.""",
            agent=self.contact_agent,
            expected_output="Confirmation that the contact was added.",
            context=[parse_task]
        )
        
        # Task 3: Evaluate quality
        evaluate_task = Task(
            description="""Evaluate the quality of the extracted data.
            Note any fields that may need verification.""",
            agent=self.evaluation_agent,
            expected_output="Quality assessment of the extracted data.",
            context=[parse_task, add_task]
        )
        
        crew = Crew(
            agents=[self.input_agent, self.contact_agent, self.evaluation_agent],
            tasks=[parse_task, add_task, evaluate_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def process_bulk(self, entries: str) -> str:
        """Process bulk import of multiple contacts."""
        
        # Task 1: Parse bulk entries
        parse_task = Task(
            description=f"""Parse the following bulk contact entries:
            
            {entries}
            
            Extract each contact's information and prepare for batch import.""",
            agent=self.input_agent,
            expected_output="List of structured contact records ready for import."
        )
        
        # Task 2: Add all contacts
        add_task = Task(
            description="""Add all the parsed contacts to the database.
            Track which were added successfully and any failures.""",
            agent=self.contact_agent,
            expected_output="Summary of bulk import: how many added, any failures.",
            context=[parse_task]
        )
        
        # Task 3: Overall assessment
        assess_task = Task(
            description="""Assess the overall quality of the bulk import.
            Provide summary statistics and recommendations.""",
            agent=self.evaluation_agent,
            expected_output="Bulk import quality assessment and summary.",
            context=[parse_task, add_task]
        )
        
        crew = Crew(
            agents=[self.input_agent, self.contact_agent, self.evaluation_agent],
            tasks=[parse_task, add_task, assess_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)


# Global crew instance
_input_crew: Optional[InputProcessingCrew] = None


def get_input_processing_crew() -> InputProcessingCrew:
    """Get or create the input processing crew instance."""
    global _input_crew
    if _input_crew is None:
        _input_crew = InputProcessingCrew()
    return _input_crew
