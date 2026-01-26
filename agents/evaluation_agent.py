"""
Evaluation Agent for assessing data quality and operation performance.
"""

from crewai import Agent
from typing import List

from tools.validation_tool import ValidationContactTool, DataQualityAssessmentTool
from tools.airtable_tool import AirtableGetContactTool, AirtableStatsTool


def create_evaluation_agent() -> Agent:
    """Create the Evaluation Agent."""
    
    tools = [
        ValidationContactTool(),
        DataQualityAssessmentTool(),
        AirtableGetContactTool(),
        AirtableStatsTool()
    ]
    
    return Agent(
        role="Quality Assurance Specialist",
        goal="Evaluate data quality, completeness, and accuracy of contact records, identifying areas for improvement.",
        backstory="""You are an expert in data quality assessment with high standards for accuracy and completeness.
You systematically evaluate contact records against quality criteria, identify missing or incomplete information,
validate data formats and accuracy, and provide clear improvement recommendations.
You understand what constitutes a high-quality contact record and can score data quality objectively.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_evaluation_agent_tools() -> List:
    """Get the list of tools for the evaluation agent."""
    return [
        ValidationContactTool(),
        DataQualityAssessmentTool(),
        AirtableGetContactTool(),
        AirtableStatsTool()
    ]
