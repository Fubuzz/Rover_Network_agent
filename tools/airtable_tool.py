"""
CrewAI tool for Airtable operations.
"""

from crewai.tools import BaseTool
from typing import Optional, Type, Any
from pydantic import BaseModel, Field

from services.airtable_service import get_sheets_service
from data.schema import Contact


class AddContactInput(BaseModel):
    """Input schema for adding a contact."""
    name: str = Field(..., description="Contact's full name")
    job_title: Optional[str] = Field(None, description="Job title or position")
    company: Optional[str] = Field(None, description="Company name")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    location: Optional[str] = Field(None, description="Location (city, country)")
    classification: Optional[str] = Field(None, description="Classification: founder, investor, enabler, professional")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    notes: Optional[str] = Field(None, description="Additional notes")


class SearchContactInput(BaseModel):
    """Input schema for searching contacts."""
    query: str = Field(..., description="Search query (name, company, or any field)")


class GetContactInput(BaseModel):
    """Input schema for getting a specific contact."""
    name: str = Field(..., description="Contact's name to retrieve")


class UpdateContactInput(BaseModel):
    """Input schema for updating a contact."""
    name: str = Field(..., description="Name of contact to update")
    field: str = Field(..., description="Field to update")
    value: str = Field(..., description="New value for the field")


class AirtableAddContactTool(BaseTool):
    """Tool for adding contacts to Airtable."""

    name: str = "add_contact"
    description: str = """Add a new contact to the network database.
    Provide the contact's information including name (required), job_title, company, phone, email, linkedin_url, location, classification, tags, and notes."""
    args_schema: Type[BaseModel] = AddContactInput

    def _run(self, name: str, job_title: str = None, company: str = None,
             phone: str = None, email: str = None, linkedin_url: str = None,
             location: str = None, classification: str = None,
             tags: str = None, notes: str = None) -> str:
        """Add a contact to Airtable."""
        try:
            sheets = get_sheets_service()

            contact = Contact(
                name=name,
                job_title=job_title,
                company=company,
                phone=phone,
                email=email,
                linkedin_url=linkedin_url,
                location=location,
                classification=classification,
                tags=tags.split(",") if tags else [],
                notes=notes
            )

            success = sheets.add_contact(contact)

            if success:
                return f"Successfully added contact: {name}"
            else:
                return f"Failed to add contact: {name}. Contact may already exist."

        except Exception as e:
            return f"Error adding contact: {str(e)}"


class AirtableSearchTool(BaseTool):
    """Tool for searching contacts in Airtable."""

    name: str = "search_contacts"
    description: str = """Search for contacts in the network database.
    Search by name, company, job title, location, or any other field."""
    args_schema: Type[BaseModel] = SearchContactInput

    def _run(self, query: str) -> str:
        """Search contacts in Airtable."""
        try:
            sheets = get_sheets_service()
            contacts = sheets.search_contacts(query)

            if not contacts:
                return f"No contacts found matching '{query}'"

            results = []
            for contact in contacts[:10]:  # Limit to 10 results
                result = f"- {contact.name}"
                if contact.company:
                    result += f" at {contact.company}"
                if contact.classification:
                    result += f" [{contact.classification}]"
                results.append(result)

            return f"Found {len(contacts)} contact(s):\n" + "\n".join(results)

        except Exception as e:
            return f"Error searching contacts: {str(e)}"


class AirtableGetContactTool(BaseTool):
    """Tool for retrieving a specific contact."""

    name: str = "get_contact"
    description: str = """Get detailed information about a specific contact by name."""
    args_schema: Type[BaseModel] = GetContactInput

    def _run(self, name: str) -> str:
        """Get contact details from Airtable."""
        try:
            sheets = get_sheets_service()
            contact = sheets.get_contact_by_name(name)

            if not contact:
                return f"Contact '{name}' not found."

            details = [
                f"**{contact.name}**",
                f"Job Title: {contact.job_title or 'N/A'}",
                f"Company: {contact.company or 'N/A'}",
                f"Email: {contact.email or 'N/A'}",
                f"Phone: {contact.phone or 'N/A'}",
                f"LinkedIn: {contact.linkedin_url or 'N/A'}",
                f"Location: {contact.location or 'N/A'}",
                f"Classification: {contact.classification or 'N/A'}",
                f"Tags: {', '.join(contact.tags) if contact.tags else 'None'}",
                f"Notes: {contact.notes or 'None'}"
            ]

            return "\n".join(details)

        except Exception as e:
            return f"Error getting contact: {str(e)}"


class AirtableUpdateContactTool(BaseTool):
    """Tool for updating a contact."""

    name: str = "update_contact"
    description: str = """Update a specific field for a contact.
    Specify the contact name, field to update, and new value."""
    args_schema: Type[BaseModel] = UpdateContactInput

    def _run(self, name: str, field: str, value: str) -> str:
        """Update a contact in Airtable."""
        try:
            sheets = get_sheets_service()

            # Map common field names
            field_map = {
                "job_title": "job_title",
                "title": "job_title",
                "position": "job_title",
                "company": "company",
                "organization": "company",
                "phone": "phone",
                "email": "email",
                "linkedin": "linkedin_url",
                "linkedin_url": "linkedin_url",
                "location": "location",
                "classification": "classification",
                "notes": "notes"
            }

            mapped_field = field_map.get(field.lower(), field)

            success = sheets.update_contact(name, {mapped_field: value})

            if success:
                return f"Successfully updated {field} for {name}"
            else:
                return f"Failed to update contact. Contact '{name}' may not exist."

        except Exception as e:
            return f"Error updating contact: {str(e)}"


class AirtableStatsTool(BaseTool):
    """Tool for getting contact statistics."""

    name: str = "get_contact_stats"
    description: str = """Get statistics about all contacts in the database.
    Returns counts by classification, company, location, and data completeness."""

    def _run(self) -> str:
        """Get contact statistics from Airtable."""
        try:
            sheets = get_sheets_service()
            stats = sheets.get_contact_stats()

            lines = [
                f"**Contact Statistics**",
                f"Total Contacts: {stats['total']}",
                "",
                "**By Classification:**"
            ]

            for classification, count in stats.get('by_classification', {}).items():
                lines.append(f"  - {classification}: {count}")

            lines.append("")
            lines.append("**Data Completeness:**")
            lines.append(f"  - With Email: {stats['with_email']}")
            lines.append(f"  - With Phone: {stats['with_phone']}")
            lines.append(f"  - With LinkedIn: {stats['with_linkedin']}")

            return "\n".join(lines)

        except Exception as e:
            return f"Error getting stats: {str(e)}"
