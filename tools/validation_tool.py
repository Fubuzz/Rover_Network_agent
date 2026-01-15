"""
CrewAI tool for data validation.
"""

from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field

from utils.validators import (
    validate_email, validate_phone, validate_linkedin_url,
    validate_name, validate_classification, validate_contact_data,
    format_phone_number, normalize_email, normalize_linkedin_url
)


class ValidateEmailInput(BaseModel):
    """Input schema for email validation."""
    email: str = Field(..., description="Email address to validate")


class ValidatePhoneInput(BaseModel):
    """Input schema for phone validation."""
    phone: str = Field(..., description="Phone number to validate")


class ValidateLinkedInInput(BaseModel):
    """Input schema for LinkedIn URL validation."""
    url: str = Field(..., description="LinkedIn URL to validate")


class ValidateContactInput(BaseModel):
    """Input schema for full contact validation."""
    name: str = Field(..., description="Contact's name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL")
    classification: Optional[str] = Field(None, description="Classification")


class ValidationEmailTool(BaseTool):
    """Tool for validating email addresses."""
    
    name: str = "validate_email"
    description: str = """Validate an email address format. Returns whether the email is valid and any error message."""
    args_schema: Type[BaseModel] = ValidateEmailInput
    
    def _run(self, email: str) -> str:
        """Validate an email address."""
        is_valid, error = validate_email(email)
        
        if is_valid:
            normalized = normalize_email(email)
            return f"Email '{normalized}' is valid."
        else:
            return f"Email validation failed: {error}"


class ValidationPhoneTool(BaseTool):
    """Tool for validating phone numbers."""
    
    name: str = "validate_phone"
    description: str = """Validate a phone number format. Returns whether the phone is valid and the formatted version."""
    args_schema: Type[BaseModel] = ValidatePhoneInput
    
    def _run(self, phone: str) -> str:
        """Validate a phone number."""
        is_valid, error = validate_phone(phone)
        
        if is_valid:
            formatted = format_phone_number(phone)
            return f"Phone number is valid. Formatted: {formatted}"
        else:
            return f"Phone validation failed: {error}"


class ValidationLinkedInTool(BaseTool):
    """Tool for validating LinkedIn URLs."""
    
    name: str = "validate_linkedin"
    description: str = """Validate a LinkedIn profile URL. Returns whether the URL is valid and the normalized version."""
    args_schema: Type[BaseModel] = ValidateLinkedInInput
    
    def _run(self, url: str) -> str:
        """Validate a LinkedIn URL."""
        is_valid, error = validate_linkedin_url(url)
        
        if is_valid:
            normalized = normalize_linkedin_url(url)
            return f"LinkedIn URL is valid. Normalized: {normalized}"
        else:
            return f"LinkedIn validation failed: {error}"


class ValidationContactTool(BaseTool):
    """Tool for validating complete contact data."""
    
    name: str = "validate_contact"
    description: str = """Validate all fields of a contact record. Returns validation status and any errors found."""
    args_schema: Type[BaseModel] = ValidateContactInput
    
    def _run(self, name: str, email: str = None, phone: str = None,
             linkedin_url: str = None, classification: str = None) -> str:
        """Validate all contact fields."""
        data = {
            "name": name,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "classification": classification
        }
        
        is_valid, errors = validate_contact_data(data)
        
        if is_valid:
            return "All contact fields are valid."
        else:
            return f"Validation errors:\n" + "\n".join(f"- {e}" for e in errors)


class DataQualityAssessmentTool(BaseTool):
    """Tool for assessing data quality of a contact."""
    
    name: str = "assess_data_quality"
    description: str = """Assess the data quality and completeness of a contact record.
    Returns a quality score and recommendations for improvement."""
    args_schema: Type[BaseModel] = ValidateContactInput
    
    def _run(self, name: str, email: str = None, phone: str = None,
             linkedin_url: str = None, classification: str = None) -> str:
        """Assess contact data quality."""
        
        # Calculate completeness score
        fields = {
            "name": (name, 20),  # field, weight
            "email": (email, 25),
            "phone": (phone, 15),
            "linkedin_url": (linkedin_url, 25),
            "classification": (classification, 15)
        }
        
        score = 0
        missing = []
        
        for field, (value, weight) in fields.items():
            if value:
                score += weight
            else:
                missing.append(field)
        
        # Validate existing fields
        data = {
            "name": name,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "classification": classification
        }
        
        is_valid, errors = validate_contact_data(data)
        
        # Adjust score for invalid data
        if errors:
            score = max(0, score - len(errors) * 10)
        
        # Generate assessment
        lines = [
            f"**Data Quality Assessment for {name}**",
            "",
            f"**Quality Score:** {score}%",
            "",
            f"**Completeness:**"
        ]
        
        if missing:
            lines.append(f"Missing fields: {', '.join(missing)}")
        else:
            lines.append("All key fields present.")
        
        if errors:
            lines.append("")
            lines.append("**Validation Issues:**")
            for error in errors:
                lines.append(f"- {error}")
        
        lines.append("")
        lines.append("**Recommendations:**")
        
        if "email" in missing:
            lines.append("- Add email address for better contact options")
        if "linkedin_url" in missing:
            lines.append("- Add LinkedIn profile for professional networking")
        if "classification" in missing:
            lines.append("- Classify contact for better organization")
        if not missing and not errors:
            lines.append("- Contact data is complete and valid")
        
        return "\n".join(lines)
