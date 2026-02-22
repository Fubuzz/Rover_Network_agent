"""
Reporting Crew for generating reports and analytics.
"""

from crewai import Crew, Task, Process
from typing import Optional

from agents.reporting_agent import create_reporting_agent
from agents.evaluation_agent import create_evaluation_agent
from config import LoggingConfig


class ReportingCrew:
    """Crew for generating reports and analytics."""
    
    def __init__(self):
        self.reporting_agent = create_reporting_agent()
        self.evaluation_agent = create_evaluation_agent()
    
    def generate_stats(self) -> str:
        """Generate overall contact statistics."""
        
        stats_task = Task(
            description="""Generate comprehensive statistics about all contacts:
            - Total count
            - Breakdown by classification (founder, investor, enabler, professional)
            - Top companies
            - Top locations
            - Data completeness metrics
            
            Present the statistics in a clear, organized format.""",
            agent=self.reporting_agent,
            expected_output="Comprehensive statistics report."
        )
        
        crew = Crew(
            agents=[self.reporting_agent],
            tasks=[stats_task],
            process=Process.sequential,
            verbose=LoggingConfig.DEBUG_MODE
        )
        
        result = crew.kickoff()
        return str(result)
    
    def generate_stats_by_attribute(self, attribute: str) -> str:
        """Generate statistics filtered by a specific attribute."""
        
        stats_task = Task(
            description=f"""Generate statistics about contacts grouped by '{attribute}':
            - Count per {attribute}
            - Distribution analysis
            - Key insights
            
            Focus on the {attribute} dimension of the data.""",
            agent=self.reporting_agent,
            expected_output=f"Statistics report grouped by {attribute}."
        )
        
        crew = Crew(
            agents=[self.reporting_agent],
            tasks=[stats_task],
            process=Process.sequential,
            verbose=LoggingConfig.DEBUG_MODE
        )
        
        result = crew.kickoff()
        return str(result)
    
    def generate_contact_report(self, name: str) -> str:
        """Generate a detailed report for a specific contact."""
        
        # Task 1: Get contact details
        details_task = Task(
            description=f"""Generate a comprehensive report for contact '{name}':
            - All contact information
            - Classification and reasoning
            - Data quality assessment
            - Any enriched data available
            - Relationship history (notes, last contacted)
            
            Create a detailed, professional report.""",
            agent=self.reporting_agent,
            expected_output="Detailed contact report."
        )
        
        # Task 2: Quality evaluation
        quality_task = Task(
            description=f"""Evaluate the data quality for contact '{name}' as part of the report.
            Include completeness score and recommendations.""",
            agent=self.evaluation_agent,
            expected_output="Data quality section for the report.",
            context=[details_task]
        )
        
        crew = Crew(
            agents=[self.reporting_agent, self.evaluation_agent],
            tasks=[details_task, quality_task],
            process=Process.sequential,
            verbose=LoggingConfig.DEBUG_MODE
        )
        
        result = crew.kickoff()
        return str(result)
    
    def generate_network_insights(self) -> str:
        """Generate insights about the overall network."""
        
        insights_task = Task(
            description="""Analyze the contact network and provide insights:
            - Network composition (types of contacts)
            - Strongest industries/sectors
            - Geographic distribution
            - Data quality overview
            - Recommendations for network growth
            
            Provide actionable insights for better networking.""",
            agent=self.reporting_agent,
            expected_output="Network insights report with recommendations."
        )
        
        crew = Crew(
            agents=[self.reporting_agent],
            tasks=[insights_task],
            process=Process.sequential,
            verbose=LoggingConfig.DEBUG_MODE
        )
        
        result = crew.kickoff()
        return str(result)


# Global crew instance
_reporting_crew: Optional[ReportingCrew] = None


def get_reporting_crew() -> ReportingCrew:
    """Get or create the reporting crew instance."""
    global _reporting_crew
    if _reporting_crew is None:
        _reporting_crew = ReportingCrew()
    return _reporting_crew
