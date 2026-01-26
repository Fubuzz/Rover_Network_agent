"""
Troubleshooting Agent for error handling and problem resolution.
"""

from crewai import Agent
from typing import List

from tools.airtable_tool import AirtableGetContactTool, AirtableSearchTool
from tools.validation_tool import ValidationContactTool, DataQualityAssessmentTool
from tools.ai_tool import AIGenerateResponseTool


def create_troubleshooting_agent() -> Agent:
    """Create the Troubleshooting Agent."""
    
    tools = [
        AirtableGetContactTool(),
        AirtableSearchTool(),
        ValidationContactTool(),
        DataQualityAssessmentTool(),
        AIGenerateResponseTool()
    ]
    
    return Agent(
        role="Problem Resolution Specialist",
        goal="Identify, diagnose, and resolve errors, issues, and inconsistencies in the contact management system.",
        backstory="""You are an expert in debugging and problem-solving with a systematic approach to issue resolution.
You can identify errors and exceptions, diagnose root causes, suggest and implement fixes, and prevent error recurrence.
You have access to multiple tools to investigate issues across the system.
You log issues for analysis and work to continuously improve system reliability.""",
        tools=tools,
        verbose=True,
        allow_delegation=True,  # Can delegate to other agents for help
        memory=True
    )


def get_troubleshooting_agent_tools() -> List:
    """Get the list of tools for the troubleshooting agent."""
    return [
        AirtableGetContactTool(),
        AirtableSearchTool(),
        ValidationContactTool(),
        DataQualityAssessmentTool(),
        AIGenerateResponseTool()
    ]
