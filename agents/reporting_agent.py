"""
Reporting Agent for generating reports and analytics.
"""

from crewai import Agent
from typing import List

from tools.google_sheets_tool import GoogleSheetsStatsTool, GoogleSheetsSearchTool
from tools.ai_tool import AIGenerateResponseTool


def create_reporting_agent() -> Agent:
    """Create the Reporting Agent."""
    
    tools = [
        GoogleSheetsStatsTool(),
        GoogleSheetsSearchTool(),
        AIGenerateResponseTool()
    ]
    
    return Agent(
        role="Analytics Specialist",
        goal="Generate comprehensive reports and statistics about contacts, providing insights and actionable analytics.",
        backstory="""You are an expert in data analysis and reporting with a keen eye for patterns and insights.
You can aggregate contact data, calculate statistics by various dimensions (classification, company, location),
and present information in clear, actionable formats. You excel at generating both summary statistics and detailed reports.
You understand what metrics are most valuable for network management and can provide strategic recommendations.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_reporting_agent_tools() -> List:
    """Get the list of tools for the reporting agent."""
    return [
        GoogleSheetsStatsTool(),
        GoogleSheetsSearchTool(),
        AIGenerateResponseTool()
    ]
