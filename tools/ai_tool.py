"""
CrewAI tool for AI operations (classification, parsing, OCR).
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

from services.ai_service import get_ai_service
from services.classification import get_classification_service


class ClassifyContactInput(BaseModel):
    """Input schema for contact classification."""
    name: str = Field(..., description="Contact's name")
    job_title: str = Field(None, description="Contact's job title")
    company: str = Field(None, description="Contact's company")
    notes: str = Field(None, description="Additional notes about the contact")


class ParseTextInput(BaseModel):
    """Input schema for parsing text."""
    text: str = Field(..., description="Text containing contact information to parse")


class GenerateResponseInput(BaseModel):
    """Input schema for generating responses."""
    query: str = Field(..., description="User query to respond to")
    context: str = Field(None, description="Additional context for the response")


class AIClassifyContactTool(BaseTool):
    """Tool for classifying contacts using AI."""
    
    name: str = "classify_contact"
    description: str = """Classify a contact into one of these categories:
    - founder: Founders, CEOs, entrepreneurs
    - investor: VCs, angels, investment professionals
    - enabler: Advisors, mentors, consultants
    - professional: Other professionals
    
    Returns the classification and confidence score."""
    args_schema: Type[BaseModel] = ClassifyContactInput
    
    def _run(self, name: str, job_title: str = None, 
             company: str = None, notes: str = None) -> str:
        """Classify a contact using AI."""
        try:
            classification_service = get_classification_service()
            
            contact_data = {
                "name": name,
                "job_title": job_title,
                "company": company,
                "notes": notes
            }
            
            result = classification_service.classify(contact_data)
            
            classification = result.get("classification", "professional")
            confidence = result.get("confidence", 0)
            method = result.get("method", "unknown")
            
            reasoning = classification_service.get_classification_reasoning(
                contact_data, classification
            )
            
            return f"""**Classification Result:**
- Category: {classification.upper()}
- Confidence: {confidence:.0%}
- Method: {method}
- Reasoning: {reasoning}"""
            
        except Exception as e:
            return f"Error classifying contact: {str(e)}"


class AIParseContactTool(BaseTool):
    """Tool for parsing contact information from text using AI."""
    
    name: str = "parse_contact_info"
    description: str = """Extract structured contact information from unstructured text.
    Identifies name, job title, company, phone, email, LinkedIn, location, and other details."""
    args_schema: Type[BaseModel] = ParseTextInput
    
    def _run(self, text: str) -> str:
        """Parse contact information from text."""
        try:
            ai_service = get_ai_service()
            result = ai_service.parse_contact_info(text)
            
            if not result:
                return "Could not extract contact information from the provided text."
            
            lines = ["**Extracted Contact Information:**", ""]
            
            field_names = {
                "name": "Name",
                "job_title": "Job Title",
                "company": "Company",
                "phone": "Phone",
                "email": "Email",
                "linkedin_url": "LinkedIn",
                "location": "Location",
                "notes": "Notes"
            }
            
            for field, label in field_names.items():
                value = result.get(field)
                if value:
                    lines.append(f"**{label}:** {value}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error parsing contact info: {str(e)}"


class AIGenerateResponseTool(BaseTool):
    """Tool for generating natural language responses."""
    
    name: str = "generate_response"
    description: str = """Generate a helpful response to a user query about contacts or networking.
    Provide context for more relevant responses."""
    args_schema: Type[BaseModel] = GenerateResponseInput
    
    def _run(self, query: str, context: str = None) -> str:
        """Generate a response using AI."""
        try:
            ai_service = get_ai_service()
            response = ai_service.generate_response(query, context)
            return response
            
        except Exception as e:
            return f"Error generating response: {str(e)}"


class AISummarizeEnrichmentTool(BaseTool):
    """Tool for summarizing enrichment search results."""
    
    name: str = "summarize_enrichment"
    description: str = """Summarize search results to create a professional profile summary.
    Takes search results and creates a cohesive narrative about the person."""
    
    def _run(self, name: str, search_results: str) -> str:
        """Summarize enrichment data."""
        try:
            ai_service = get_ai_service()
            
            # Parse search results if it's a string
            import json
            if isinstance(search_results, str):
                try:
                    results = json.loads(search_results)
                except:
                    results = [{"snippet": search_results}]
            else:
                results = search_results
            
            summary = ai_service.enrich_with_summary(
                {"name": name},
                results if isinstance(results, list) else [results]
            )
            
            if summary:
                lines = [f"**Profile Summary for {name}:**", ""]
                
                if summary.get("summary"):
                    lines.append(summary["summary"])
                
                if summary.get("notable_achievements"):
                    lines.append("\n**Notable Achievements:**")
                    for achievement in summary["notable_achievements"]:
                        lines.append(f"- {achievement}")
                
                return "\n".join(lines)
            
            return f"Could not generate summary for {name}"
            
        except Exception as e:
            return f"Error summarizing: {str(e)}"
