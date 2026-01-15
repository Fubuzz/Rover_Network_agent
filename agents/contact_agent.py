"""
Contact Management Agent for handling contact CRUD operations.
"""

from crewai import Agent
from typing import List

from tools.google_sheets_tool import (
    GoogleSheetsAddContactTool,
    GoogleSheetsSearchTool,
    GoogleSheetsGetContactTool,
    GoogleSheetsUpdateContactTool,
    GoogleSheetsStatsTool
)
from tools.validation_tool import ValidationContactTool, DataQualityAssessmentTool


def create_contact_agent() -> Agent:
    """Create the Contact Management Agent."""
    
    tools = [
        GoogleSheetsAddContactTool(),
        GoogleSheetsSearchTool(),
        GoogleSheetsGetContactTool(),
        GoogleSheetsUpdateContactTool(),
        GoogleSheetsStatsTool(),
        ValidationContactTool(),
        DataQualityAssessmentTool()
    ]
    
    return Agent(
        role="Data Entry Specialist",
        goal="Accurately add, update, and manage contact information in the network database while ensuring data quality and integrity.",
        backstory="""You are an expert in contact management with exceptional attention to detail. 
You have years of experience managing professional networks and understand the importance of accurate, 
complete contact information. You always validate data before saving and detect potential duplicates.
You ensure every contact record is as complete as possible and properly formatted.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_contact_agent_tools() -> List:
    """Get the list of tools for the contact agent."""
    return [
        GoogleSheetsAddContactTool(),
        GoogleSheetsSearchTool(),
        GoogleSheetsGetContactTool(),
        GoogleSheetsUpdateContactTool(),
        GoogleSheetsStatsTool(),
        ValidationContactTool(),
        DataQualityAssessmentTool()
    ]
