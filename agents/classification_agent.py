"""
Classification Agent for categorizing contacts.
"""

from crewai import Agent
from typing import List

from tools.ai_tool import AIClassifyContactTool, AIGenerateResponseTool
from tools.validation_tool import ValidationContactTool


def create_classification_agent() -> Agent:
    """Create the Classification Agent."""
    
    tools = [
        AIClassifyContactTool(),
        AIGenerateResponseTool(),
        ValidationContactTool()
    ]
    
    return Agent(
        role="Categorization Specialist",
        goal="Accurately classify contacts into appropriate categories (founder, investor, enabler, professional) based on their professional profile.",
        backstory="""You are an expert in professional categorization with deep understanding of business roles and ecosystems.
You can accurately identify founders and entrepreneurs, distinguish investors and VCs, recognize enablers like advisors and mentors,
and properly categorize other professionals. You analyze job titles, company information, and context clues to make accurate classifications.
You provide confidence scores and reasoning for your classifications.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_classification_agent_tools() -> List:
    """Get the list of tools for the classification agent."""
    return [
        AIClassifyContactTool(),
        AIGenerateResponseTool(),
        ValidationContactTool()
    ]
