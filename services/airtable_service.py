"""
Airtable service for contact management.
Replaces Google Sheets as the primary database backend.
"""

from pyairtable import Api, Table
from typing import List, Optional, Dict, Any
from datetime import datetime

from config import AirtableConfig, BASE_DIR
from data.schema import (
    Contact, SHEET_HEADERS, COL_INDEX,
    Match, MATCH_SHEET_HEADERS,
    Draft, DRAFT_SHEET_HEADERS, ApprovalStatus, SendStatus,
    CONTACTS_SHEET_NAME, MATCHES_SHEET_NAME, DRAFTS_SHEET_NAME
)


class AirtableService:
    """Service for interacting with Airtable."""

    def __init__(self):
        self.api: Optional[Api] = None
        self.contacts_table: Optional[Table] = None
        self.matches_table: Optional[Table] = None
        self.drafts_table: Optional[Table] = None
        self._initialized = False
        self._headers = SHEET_HEADERS  # Use schema headers
        self._v3_fields_exist = False  # Will be set True if V3 columns exist in Airtable

    def initialize(self) -> bool:
        """Initialize connection to Airtable."""
        try:
            if not AirtableConfig.AIRTABLE_PAT:
                print("Airtable PAT not configured")
                return False

            if not AirtableConfig.AIRTABLE_BASE_ID:
                print("Airtable Base ID not configured")
                return False

            self.api = Api(AirtableConfig.AIRTABLE_PAT)

            # Initialize table references
            self.contacts_table = self.api.table(
                AirtableConfig.AIRTABLE_BASE_ID,
                AirtableConfig.AIRTABLE_CONTACTS_TABLE
            )
            self.matches_table = self.api.table(
                AirtableConfig.AIRTABLE_BASE_ID,
                AirtableConfig.AIRTABLE_MATCHES_TABLE
            )
            self.drafts_table = self.api.table(
                AirtableConfig.AIRTABLE_BASE_ID,
                AirtableConfig.AIRTABLE_DRAFTS_TABLE
            )

            self._initialized = True
            
            # Check if V3 fields exist in the table schema via meta API
            try:
                import requests as _req
                _meta_r = _req.get(
                    f"https://api.airtable.com/v0/meta/bases/{AirtableConfig.AIRTABLE_BASE_ID}/tables",
                    headers={"Authorization": f"Bearer {AirtableConfig.AIRTABLE_PAT}"}
                )
                if _meta_r.status_code == 200:
                    for _t in _meta_r.json().get("tables", []):
                        if _t["name"] == AirtableConfig.AIRTABLE_CONTACTS_TABLE:
                            _field_names = {f["name"] for f in _t.get("fields", [])}
                            self._v3_fields_exist = "relationship_score" in _field_names
                            break
                else:
                    self._v3_fields_exist = False
            except Exception:
                self._v3_fields_exist = False
            
            print(f"Connected to Airtable Base: {AirtableConfig.AIRTABLE_BASE_ID} (V3 fields: {self._v3_fields_exist})")
            print(f"Tables: {AirtableConfig.AIRTABLE_CONTACTS_TABLE}, {AirtableConfig.AIRTABLE_MATCHES_TABLE}, {AirtableConfig.AIRTABLE_DRAFTS_TABLE}")
            return True

        except Exception as e:
            print(f"Failed to initialize Airtable: {e}")
            import traceback
            traceback.print_exc()
            self._initialized = False
            return False

    def _ensure_initialized(self):
        """Ensure service is initialized."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Airtable service not initialized")

    def _get_col_index(self, col_name: str) -> int:
        """Get column index by name (0-based). For compatibility."""
        if self._headers and col_name in self._headers:
            return self._headers.index(col_name)
        return COL_INDEX.get(col_name, -1)

    def _contact_to_airtable_fields(self, contact: Contact) -> Dict[str, Any]:
        """
        Convert Contact to Airtable fields dict.

        EXACT Airtable column mapping:
        contact_id, first_name, last_name, full_name, email, phone,
        contact_linkedin_url, company, title, source, relationship_strength,
        how_we_met, last_contact_date, notes, status, created_date, updated_date,
        company_description, industry, company_stage, funding_raised, founder_score,
        key_strengths, stage_fit, sector_fit, classified_date, linkedin_summary,
        contact_type, research_quality, researched_date, imported_date,
        linkedin_status, website, address, company_linkedin_url
        """
        fields = {}

        # Core Identity
        if contact.contact_id:
            fields["contact_id"] = contact.contact_id
        if contact.first_name:
            fields["first_name"] = contact.first_name
        if contact.last_name:
            fields["last_name"] = contact.last_name
        if contact.full_name:
            fields["full_name"] = contact.full_name
        if contact.email:
            # Email validation - must contain @ and .
            if "@" in contact.email and "." in contact.email.split("@")[-1]:
                fields["email"] = contact.email
        if contact.phone:
            fields["phone"] = contact.phone

        # Professional
        if contact.company:
            fields["company"] = contact.company
        if contact.title:
            fields["title"] = contact.title

        # CRITICAL: LinkedIn URLs - exact column names!
        if contact.linkedin_url:
            fields["contact_linkedin_url"] = contact.linkedin_url  # Personal LinkedIn
        if contact.linkedin_link:
            fields["company_linkedin_url"] = contact.linkedin_link  # Company LinkedIn

        # Meta
        if contact.source:
            fields["source"] = contact.source or "telegram"
        if contact.status:
            fields["status"] = contact.status
        if contact.relationship_strength:
            fields["relationship_strength"] = contact.relationship_strength
        if contact.how_we_met:
            fields["how_we_met"] = contact.how_we_met
        if contact.last_contact_date:
            fields["last_contact_date"] = contact.last_contact_date
        if contact.notes:
            fields["notes"] = contact.notes
        if contact.created_date:
            fields["created_date"] = contact.created_date
        if contact.updated_date:
            fields["updated_date"] = contact.updated_date

        # Enrichment Data
        if contact.company_description:
            fields["company_description"] = contact.company_description
        if contact.industry:
            fields["industry"] = contact.industry
        if contact.company_stage:
            fields["company_stage"] = contact.company_stage
        if contact.funding_raised:
            fields["funding_raised"] = contact.funding_raised
        if contact.founder_score:
            fields["founder_score"] = contact.founder_score
        if contact.key_strengths:
            fields["key_strengths"] = contact.key_strengths
        if contact.stage_fit:
            fields["stage_fit"] = contact.stage_fit
        if contact.sector_fit:
            fields["sector_fit"] = contact.sector_fit
        if contact.classified_date:
            fields["classified_date"] = contact.classified_date
        if contact.linkedin_summary:
            fields["linkedin_summary"] = contact.linkedin_summary
        if contact.contact_type:
            # Normalize contact_type for Airtable Single Select
            # Strip extra quotes and capitalize first letter
            ct = contact.contact_type
            if isinstance(ct, str):
                ct = ct.strip().strip('"').strip("'")  # Remove extra quotes
                # Capitalize to match Airtable choices: Founder, Investor, Enabler
                ct = ct.capitalize()
            fields["contact_type"] = ct
        if contact.research_quality:
            fields["research_quality"] = contact.research_quality
        if contact.researched_date:
            fields["researched_date"] = contact.researched_date
        if contact.imported_date:
            fields["imported_date"] = contact.imported_date
        if contact.linkedin_status:
            fields["linkedin_status"] = contact.linkedin_status
        if contact.website:
            fields["website"] = contact.website
        # Note: address field skipped - Airtable may have formatting requirements
        # if contact.address:
        #     fields["address"] = contact.address
        
        # V3 New Fields - Relationship Intelligence
        # V3 fields — only send if the columns exist in Airtable
        # These are skipped gracefully to avoid 422 UNKNOWN_FIELD_NAME errors
        v3_fields = {}
        if contact.relationship_score:
            v3_fields["relationship_score"] = contact.relationship_score
        if contact.last_interaction_date:
            v3_fields["last_interaction_date"] = contact.last_interaction_date
        if contact.interaction_count:
            v3_fields["interaction_count"] = contact.interaction_count
        if contact.follow_up_date:
            v3_fields["follow_up_date"] = contact.follow_up_date
        if contact.follow_up_reason:
            v3_fields["follow_up_reason"] = contact.follow_up_reason
        if contact.introduced_by:
            v3_fields["introduced_by"] = contact.introduced_by
        if contact.introduced_to:
            v3_fields["introduced_to"] = contact.introduced_to
        if contact.priority:
            v3_fields["priority"] = contact.priority
        if contact.relationship_stage:
            v3_fields["relationship_stage"] = contact.relationship_stage
        # Only include V3 fields if they exist in the table (test with first field)
        if v3_fields and self._v3_fields_exist:
            fields.update(v3_fields)

        return fields

    def _airtable_record_to_contact(self, record: Dict[str, Any]) -> Contact:
        """Convert Airtable record to Contact."""
        fields = record.get("fields", {})
        # Store Airtable record ID in row_number for updates/deletes
        record_id = record.get("id", "")

        contact = Contact(
            contact_id=fields.get("contact_id", ""),
            first_name=fields.get("first_name"),
            last_name=fields.get("last_name"),
            full_name=fields.get("full_name"),
            email=fields.get("email"),
            phone=fields.get("phone"),
            linkedin_url=fields.get("contact_linkedin_url"),  # Airtable column name
            company=fields.get("company"),
            title=fields.get("title"),
            source=fields.get("source", "telegram"),
            relationship_strength=fields.get("relationship_strength"),
            how_we_met=fields.get("how_we_met"),
            last_contact_date=fields.get("last_contact_date"),
            notes=fields.get("notes"),
            status=fields.get("status", "active"),
            created_date=fields.get("created_date"),
            updated_date=fields.get("updated_date"),
            company_description=fields.get("company_description"),
            industry=fields.get("industry"),
            company_stage=fields.get("company_stage"),
            funding_raised=fields.get("funding_raised"),
            founder_score=fields.get("founder_score"),
            key_strengths=fields.get("key_strengths"),
            stage_fit=fields.get("stage_fit"),
            sector_fit=fields.get("sector_fit"),
            classified_date=fields.get("classified_date"),
            linkedin_summary=fields.get("linkedin_summary"),
            contact_type=fields.get("contact_type"),
            research_quality=fields.get("research_quality"),
            researched_date=fields.get("researched_date"),
            imported_date=fields.get("imported_date"),
            linkedin_status=fields.get("linkedin_status"),
            chat_id=fields.get("chatId"),
            website=fields.get("website"),
            address=fields.get("address"),
            user_id=fields.get("userId"),
            linkedin_link=fields.get("company_linkedin_url"),  # Airtable column name
            # V3 New Fields
            relationship_score=fields.get("relationship_score"),
            last_interaction_date=fields.get("last_interaction_date"),
            interaction_count=fields.get("interaction_count", 0),
            follow_up_date=fields.get("follow_up_date"),
            follow_up_reason=fields.get("follow_up_reason"),
            introduced_by=fields.get("introduced_by"),
            introduced_to=fields.get("introduced_to"),
            priority=fields.get("priority"),
            relationship_stage=fields.get("relationship_stage"),
        )
        # Store record ID as row_number (string, but works for our purposes)
        contact.row_number = record_id
        return contact

    def add_contact(self, contact: Contact) -> bool:
        """Add a new contact to Airtable.

        Performs duplicate detection on:
        - Email (strongest signal)
        - LinkedIn URL (strong signal)
        - Phone number (last 7 digits match)
        """
        self._ensure_initialized()

        try:
            new_name = (contact.name or "").lower().strip()

            # Check for duplicates by email (strongest signal)
            if contact.email:
                existing = self.find_contact_by_email(contact.email)
                if existing:
                    existing_name = (existing.name or "").lower().strip()
                    if existing_name and new_name:
                        if existing_name == new_name or existing_name.split()[0] == new_name.split()[0]:
                            print(f"[DUPLICATE] Contact '{contact.name}' with email {contact.email} already exists - use update instead")
                            return False
                    print(f"[WARN] Email {contact.email} also used by '{existing.name}', adding '{contact.name}' as separate contact")

            # Check for duplicates by LinkedIn URL (strong signal)
            linkedin = contact.linkedin_url or contact.linkedin_link
            if linkedin and 'linkedin.com/in/' in linkedin:
                existing = self.find_contact_by_linkedin(linkedin)
                if existing:
                    existing_name = (existing.name or "").lower().strip()
                    if existing_name and new_name:
                        if existing_name == new_name or existing_name.split()[0] == new_name.split()[0]:
                            print(f"[DUPLICATE] Contact '{contact.name}' with LinkedIn {linkedin} already exists - use update instead")
                            return False
                    print(f"[WARN] LinkedIn {linkedin} also used by '{existing.name}', adding '{contact.name}' as separate contact")

            # Check for duplicates by phone (match last 7 digits)
            if contact.phone:
                existing = self.find_contact_by_phone(contact.phone)
                if existing:
                    existing_name = (existing.name or "").lower().strip()
                    if existing_name and new_name:
                        if existing_name == new_name or existing_name.split()[0] == new_name.split()[0]:
                            print(f"[DUPLICATE] Contact '{contact.name}' with phone {contact.phone} already exists - use update instead")
                            return False
                    print(f"[WARN] Phone {contact.phone} also used by '{existing.name}', adding '{contact.name}' as separate contact")

            fields = self._contact_to_airtable_fields(contact)
            self.contacts_table.create(fields, typecast=True)
            return True

        except Exception as e:
            print(f"Error adding contact: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_contact(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing contact with EXACT Airtable column mapping."""
        self._ensure_initialized()

        try:
            contact = self.get_contact_by_name(name)
            if not contact:
                return False

            record_id = contact.row_number
            if not record_id:
                return False

            # EXACT Airtable column names
            valid_airtable_fields = {
                "contact_id", "first_name", "last_name", "full_name",
                "email", "phone", "contact_linkedin_url", "company", "title",
                "source", "relationship_strength", "how_we_met", "last_contact_date",
                "notes", "status", "created_date", "updated_date", "company_description",
                "industry", "company_stage", "funding_raised", "founder_score",
                "key_strengths", "stage_fit", "sector_fit", "classified_date",
                "linkedin_summary", "contact_type", "research_quality", "researched_date",
                "imported_date", "linkedin_status", "website", "address", "company_linkedin_url",
                # V3 New Fields
                "relationship_score", "last_interaction_date", "interaction_count",
                "follow_up_date", "follow_up_reason", "introduced_by", "introduced_to",
                "priority", "relationship_stage"
            }

            # Field aliases mapping to EXACT Airtable column names
            field_to_col = {
                # Core
                "email": "email",
                "phone": "phone",
                "company": "company",
                "name": "full_name",
                "full_name": "full_name",
                "first_name": "first_name",
                "last_name": "last_name",
                "title": "title",
                "source": "source",
                "status": "status",
                # LinkedIn - CRITICAL MAPPING
                "linkedin": "contact_linkedin_url",
                "linkedin_url": "contact_linkedin_url",
                "contact_linkedin_url": "contact_linkedin_url",
                "linkedin_link": "company_linkedin_url",
                "company_linkedin": "company_linkedin_url",
                "company_linkedin_url": "company_linkedin_url",
                # Location
                "location": "address",
                "address": "address",
                # Enrichment
                "notes": "notes",
                "industry": "industry",
                "company_description": "company_description",
                "linkedin_summary": "linkedin_summary",
                "contact_type": "contact_type",
                "research_quality": "research_quality",
                "website": "website",
                # V3 New Fields
                "relationship_score": "relationship_score",
                "last_interaction_date": "last_interaction_date",
                "interaction_count": "interaction_count",
                "follow_up_date": "follow_up_date",
                "follow_up_reason": "follow_up_reason",
                "introduced_by": "introduced_by",
                "introduced_to": "introduced_to",
                "priority": "priority",
                "relationship_stage": "relationship_stage",
            }

            airtable_updates = {}
            for key, value in updates.items():
                col_name = field_to_col.get(key, key)
                # Only include fields that exist in Airtable
                if col_name in valid_airtable_fields:
                    # Email validation
                    if col_name == "email" and value:
                        if "@" not in value or "." not in value.split("@")[-1]:
                            continue  # Skip invalid email
                    # Normalize contact_type for Single Select
                    if col_name == "contact_type" and isinstance(value, str):
                        value = value.strip().strip('"').strip("'").capitalize()
                    airtable_updates[col_name] = value

            if not airtable_updates:
                print(f"No valid Airtable fields to update for {name}")
                return True

            self.contacts_table.update(record_id, airtable_updates, typecast=True)
            print(f"Updated {name} in Airtable: {list(airtable_updates.keys())}")
            return True

        except Exception as e:
            print(f"Error updating contact: {e}")
            import traceback
            traceback.print_exc()
            return False

    def delete_contact(self, name: str) -> bool:
        """Delete a contact by name."""
        self._ensure_initialized()

        try:
            contact = self.get_contact_by_name(name)
            if not contact or not contact.row_number:
                return False

            self.contacts_table.delete(contact.row_number)
            return True

        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    def update_contact_field(self, name: str, field: str, value: Any) -> bool:
        """
        Quick single-field update for a contact.
        
        Args:
            name: Contact name
            field: Field name to update
            value: New value
        
        Returns:
            True if successful
        """
        return self.update_contact(name, {field: value})
    
    def get_contacts_with_follow_ups(self) -> List[Contact]:
        """
        Get contacts with pending follow-ups (follow_up_date is set and not empty).
        
        Returns:
            List of Contact objects
        """
        self._ensure_initialized()
        
        try:
            # Get all contacts and filter client-side for robustness
            all_contacts = self.get_all_contacts()
            
            contacts_with_follow_ups = []
            for contact in all_contacts:
                if contact.follow_up_date and contact.follow_up_date.strip():
                    contacts_with_follow_ups.append(contact)
            
            return contacts_with_follow_ups
            
        except Exception as e:
            print(f"Error getting contacts with follow-ups: {e}")
            return []

    def get_contact_by_name(self, name: str) -> Optional[Contact]:
        """Get a contact by name (searches full_name and first_name + last_name)."""
        self._ensure_initialized()

        try:
            name_lower = name.lower().strip()

            # Try exact match on full_name first
            formula = f"LOWER({{full_name}}) = '{name_lower}'"
            records = self.contacts_table.all(formula=formula)

            if records:
                return self._airtable_record_to_contact(records[0])

            # Try first name match
            first_name = name_lower.split()[0] if name_lower else ""
            if first_name:
                formula = f"LOWER({{first_name}}) = '{first_name}'"
                records = self.contacts_table.all(formula=formula)

                if records:
                    # Check if the full name matches
                    for record in records:
                        contact = self._airtable_record_to_contact(record)
                        combined = f"{contact.first_name or ''} {contact.last_name or ''}".lower().strip()
                        if combined == name_lower or (contact.first_name or "").lower().strip() == name_lower:
                            return contact

            return None

        except Exception as e:
            print(f"Error getting contact: {e}")
            return None

    def get_contact_by_id(self, contact_id: str) -> Optional[Contact]:
        """Get a contact by contact_id."""
        self._ensure_initialized()

        if not contact_id:
            return None

        try:
            formula = f"{{contact_id}} = '{contact_id.strip()}'"
            records = self.contacts_table.all(formula=formula)

            if records:
                return self._airtable_record_to_contact(records[0])

            return None

        except Exception as e:
            print(f"Error getting contact by ID: {e}")
            return None

    def get_contact_dict_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a contact as a raw dict by contact_id."""
        self._ensure_initialized()

        if not contact_id:
            return None

        try:
            formula = f"{{contact_id}} = '{contact_id.strip()}'"
            records = self.contacts_table.all(formula=formula)

            if records:
                record = records[0]
                result = record.get("fields", {}).copy()
                result["row_number"] = record.get("id", "")
                return result

            return None

        except Exception as e:
            print(f"Error getting contact dict by ID: {e}")
            return None

    def find_contact_by_email(self, email: str) -> Optional[Contact]:
        """Find a contact by email."""
        self._ensure_initialized()

        try:
            email = email.lower().strip()
            formula = f"LOWER({{email}}) = '{email}'"
            records = self.contacts_table.all(formula=formula)

            if records:
                return self._airtable_record_to_contact(records[0])

            return None

        except Exception as e:
            print(f"Error finding contact by email: {e}")
            return None

    def find_contact_by_linkedin(self, linkedin_url: str) -> Optional[Contact]:
        """Find a contact by LinkedIn URL (checks both linkedin_url and contact_linkedin_url)."""
        self._ensure_initialized()

        try:
            # Normalize LinkedIn URL - extract username portion
            linkedin_url = linkedin_url.lower().strip().rstrip('/')
            if '/in/' in linkedin_url:
                # Extract just the username part for matching
                username = linkedin_url.split('/in/')[-1].split('/')[0].split('?')[0]
            else:
                username = linkedin_url

            # Search in both LinkedIn URL fields
            formula = f"FIND('{username}', LOWER({{contact_linkedin_url}}))"
            records = self.contacts_table.all(formula=formula)

            if records:
                return self._airtable_record_to_contact(records[0])

            return None

        except Exception as e:
            print(f"Error finding contact by LinkedIn: {e}")
            return None

    def find_contact_by_phone(self, phone: str) -> Optional[Contact]:
        """Find a contact by phone number (last 7 digits match)."""
        self._ensure_initialized()

        try:
            # Normalize - extract just digits
            phone_digits = ''.join(c for c in phone if c.isdigit())
            if len(phone_digits) < 7:
                return None

            # Match on last 7 digits (handles country code differences)
            last7 = phone_digits[-7:]

            # Get all contacts and check manually (Airtable doesn't support regex well)
            records = self.contacts_table.all()
            for record in records:
                fields = record.get('fields', {})
                existing_phone = fields.get('phone', '')
                if existing_phone:
                    existing_digits = ''.join(c for c in existing_phone if c.isdigit())
                    if len(existing_digits) >= 7 and existing_digits[-7:] == last7:
                        return self._airtable_record_to_contact(record)

            return None

        except Exception as e:
            print(f"Error finding contact by phone: {e}")
            return None

    def get_all_contacts(self) -> List[Contact]:
        """Get all contacts from Airtable."""
        self._ensure_initialized()

        try:
            records = self.contacts_table.all()
            contacts = []

            for record in records:
                try:
                    contact = self._airtable_record_to_contact(record)
                    if contact.name and contact.name != "Unknown":
                        contacts.append(contact)
                except Exception as e:
                    print(f"Error parsing record: {e}")
                    continue

            return contacts

        except Exception as e:
            print(f"Error getting all contacts: {e}")
            return []

    def search_contacts(self, query: str) -> List[Contact]:
        """Search contacts by name, company, or any field."""
        self._ensure_initialized()

        query = query.lower()
        all_contacts = self.get_all_contacts()

        results = []
        for contact in all_contacts:
            searchable = " ".join([
                contact.name or "",
                contact.company or "",
                contact.title or "",
                contact.email or "",
                contact.address or "",
                contact.industry or "",
                contact.notes or "",
                contact.contact_type or ""
            ]).lower()

            if query in searchable:
                results.append(contact)

        return results

    def get_contacts_by_classification(self, classification: str) -> List[Contact]:
        """Get contacts by classification/contact_type."""
        all_contacts = self.get_all_contacts()
        return [c for c in all_contacts if c.contact_type and c.contact_type.lower() == classification.lower()]

    def filter_contacts(self, criteria: dict) -> List[Contact]:
        """
        Filter contacts by multiple criteria using Airtable formula.
        Falls back to client-side filtering if the formula query fails.

        Args:
            criteria: Dict of field->value pairs, e.g.
                {"contact_type": "investor", "industry": "fintech", "address": "egypt"}

        Returns:
            List of matching Contact objects.
        """
        if not criteria:
            return self.get_all_contacts()

        # Normalize field aliases to actual Airtable column names
        alias_map = {
            "type": "contact_type",
            "classification": "contact_type",
            "location": "address",
            "country": "address",
            "city": "address",
            "region": "address",
            "sector": "industry",
            "firm": "company",
            "organization": "company",
        }
        normalized = {}
        for key, value in criteria.items():
            col = alias_map.get(key.lower(), key.lower())
            normalized[col] = str(value).lower().strip()

        self._ensure_initialized()

        # Try Airtable formula first
        try:
            parts = []
            for col, val in normalized.items():
                # Use FIND for substring match (case-insensitive via LOWER)
                safe_val = val.replace("'", "\\'")
                parts.append(f"FIND('{safe_val}', LOWER({{{col}}}))")

            formula = f"AND({', '.join(parts)})" if len(parts) > 1 else parts[0]
            records = self.contacts_table.all(formula=formula)

            if records is not None:
                contacts = []
                for record in records:
                    try:
                        contact = self._airtable_record_to_contact(record)
                        if contact.name and contact.name != "Unknown":
                            contacts.append(contact)
                    except Exception:
                        continue
                return contacts
        except Exception as e:
            print(f"[AIRTABLE] Formula filter failed ({e}), falling back to client-side")

        # Client-side fallback
        return self._client_side_filter(normalized)

    def _client_side_filter(self, criteria: dict) -> List[Contact]:
        """Filter contacts in-memory when Airtable formula fails."""
        all_contacts = self.get_all_contacts()
        results = []

        for contact in all_contacts:
            match = True
            for col, val in criteria.items():
                contact_val = getattr(contact, col, None) or ""
                if val not in contact_val.lower():
                    match = False
                    break
            if match:
                results.append(contact)

        return results

    def get_contact_stats(self) -> Dict[str, Any]:
        """Get statistics about contacts."""
        contacts = self.get_all_contacts()

        stats = {
            "total": len(contacts),
            "by_classification": {},
            "by_company": {},
            "by_location": {},
            "by_industry": {},
            "with_email": 0,
            "with_phone": 0,
            "with_linkedin": 0
        }

        for contact in contacts:
            if contact.contact_type:
                stats["by_classification"][contact.contact_type] = \
                    stats["by_classification"].get(contact.contact_type, 0) + 1

            if contact.company:
                stats["by_company"][contact.company] = \
                    stats["by_company"].get(contact.company, 0) + 1

            if contact.address:
                stats["by_location"][contact.address] = \
                    stats["by_location"].get(contact.address, 0) + 1

            if contact.industry:
                stats["by_industry"][contact.industry] = \
                    stats["by_industry"].get(contact.industry, 0) + 1

            if contact.email:
                stats["with_email"] += 1
            if contact.phone:
                stats["with_phone"] += 1
            if contact.linkedin_url or contact.linkedin_link:
                stats["with_linkedin"] += 1

        return stats

    def export_to_csv(self) -> str:
        """Export all contacts to CSV format."""
        self._ensure_initialized()

        import csv
        import io

        contacts = self.get_all_contacts()

        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(SHEET_HEADERS)

        # Write data
        for contact in contacts:
            writer.writerow(contact.to_sheet_row())

        return output.getvalue()

    def import_from_csv(self, csv_content: str) -> int:
        """Import contacts from CSV content. Returns number imported."""
        import csv
        import io

        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader, None)  # Skip header

        imported = 0
        for row in reader:
            if row:
                try:
                    contact = Contact.from_sheet_row(row)
                    if self.add_contact(contact):
                        imported += 1
                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue

        return imported

    # ===== MATCHES TABLE METHODS =====

    def get_all_contacts_as_json(self) -> List[Dict[str, Any]]:
        """Get all contacts as a list of dictionaries (JSON format)."""
        self._ensure_initialized()

        try:
            records = self.contacts_table.all()
            contacts_json = []

            for record in records:
                contact_dict = record.get("fields", {}).copy()
                contact_dict["row_number"] = record.get("id", "")
                contacts_json.append(contact_dict)

            return contacts_json

        except Exception as e:
            print(f"Error getting contacts as JSON: {e}")
            return []

    def get_founders_and_investors(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all contacts categorized as Founders and Investors."""
        all_contacts = self.get_all_contacts_as_json()

        founders = []
        investors = []

        for contact in all_contacts:
            contact_type = contact.get("contact_type", "").lower()
            if contact_type == "founder":
                founders.append(contact)
            elif contact_type == "investor":
                investors.append(contact)

        return {
            "founders": founders,
            "investors": investors
        }

    def _match_to_airtable_fields(self, match: Match) -> Dict[str, Any]:
        """Convert Match to Airtable fields dict.

        AIRTABLE FIELD TYPES (from testing):
        - Linked Record fields: founder_contact_id, investor_contact_id → need [list]
        - Single Select fields: Many name/email fields are Single Select
        - Number fields: match_score
        - Text fields: match_id, rationale fields, linkedin URLs
        - Date fields: match_date

        We build a minimal record and skip None values.
        """
        record = {}

        # DEBUG: Log the raw values coming in
        print(f"[DEBUG] match.founder_contact_id = {match.founder_contact_id!r} (type: {type(match.founder_contact_id).__name__})")
        print(f"[DEBUG] match.investor_contact_id = {match.investor_contact_id!r} (type: {type(match.investor_contact_id).__name__})")

        # 1. CONTACT ID FIELDS - These are TEXT fields, NOT Linked Records
        # Pass as plain strings (NOT wrapped in lists)
        # Handle case where it might already be a list or stringified list
        founder_id = match.founder_contact_id
        investor_id = match.investor_contact_id

        # Fix: If it's a list, extract the first element
        if isinstance(founder_id, list):
            founder_id = founder_id[0] if founder_id else ""
        if isinstance(investor_id, list):
            investor_id = investor_id[0] if investor_id else ""

        # Fix: If it's a stringified list like '["recXXX"]', parse it
        if isinstance(founder_id, str) and founder_id.startswith("["):
            try:
                import json
                parsed = json.loads(founder_id)
                if isinstance(parsed, list) and parsed:
                    founder_id = parsed[0]
            except:
                pass
        if isinstance(investor_id, str) and investor_id.startswith("["):
            try:
                import json
                parsed = json.loads(investor_id)
                if isinstance(parsed, list) and parsed:
                    investor_id = parsed[0]
            except:
                pass

        print(f"[DEBUG] After normalization: founder_id = {founder_id!r}, investor_id = {investor_id!r}")

        if founder_id:
            record["founder_contact_id"] = founder_id
        if investor_id:
            record["investor_contact_id"] = investor_id

        # 2. TEXT FIELDS (Long text / Rich text - should be safe)
        if match.match_id:
            record["match_id"] = match.match_id
        if match.match_rationale:
            record["match_rationale"] = match.match_rationale
        if match.primary_match_reason:
            record["primary_match_reason"] = match.primary_match_reason
        if match.thesis_alignment_notes:
            record["thesis_alignment_notes"] = match.thesis_alignment_notes
        if match.suggested_subject_line:
            record["suggested_subject_line"] = match.suggested_subject_line
        if match.recent_news_hook:
            record["recent_news_hook"] = match.recent_news_hook
        if match.portfolio_synergy:
            record["portfolio_synergy"] = match.portfolio_synergy
        if match.sector_overlap:
            record["sector_overlap"] = match.sector_overlap

        # 3. URL FIELDS (should be safe)
        if match.founder_linkedin:
            record["founder_linkedin"] = match.founder_linkedin
        if match.investor_linkedin:
            record["investor_linkedin"] = match.investor_linkedin

        # 4. NUMBER FIELDS
        record["match_score"] = match.match_score or 0

        # 5. DATE FIELDS
        if match.match_date:
            record["match_date"] = match.match_date

        # 6. NAME/EMAIL FIELDS (now Long Text fields in Airtable)
        if match.founder_name:
            record["founder_name"] = match.founder_name
        if match.investor_name:
            record["investor_name"] = match.investor_name
        if match.startup_name:
            record["startup_name"] = match.startup_name
        if match.investor_firm:
            record["investor_firm"] = match.investor_firm
        if match.founder_email:
            record["founder_email"] = match.founder_email
        if match.investor_email:
            record["investor_email"] = match.investor_email

        # 7. ALIGNMENT/STATUS FIELDS (now Long Text fields in Airtable)
        if match.stage_alignment:
            record["stage_alignment"] = match.stage_alignment
        if match.geo_alignment:
            record["geo_alignment"] = match.geo_alignment
        if match.intro_angle:
            record["intro_angle"] = match.intro_angle
        if match.tone_instruction:
            record["tone_instruction"] = match.tone_instruction
        if match.email_status:
            record["email_status"] = match.email_status

        # 8. BOOLEAN FIELDS
        if match.anti_portfolio_flag is not None:
            record["anti_portfolio_flag"] = match.anti_portfolio_flag

        # Clean up: Remove None values (Airtable rejects None)
        clean_record = {k: v for k, v in record.items() if v is not None}

        return clean_record

    def _airtable_record_to_match(self, record: Dict[str, Any]) -> Match:
        """Convert Airtable record to Match."""
        fields = record.get("fields", {})
        return Match.from_dict(fields)

    def add_match(self, match: Match) -> bool:
        """Add a new match to the Matches table."""
        self._ensure_initialized()

        try:
            fields = self._match_to_airtable_fields(match)
            self.matches_table.create(fields, typecast=True)
            return True

        except Exception as e:
            print(f"Error adding match: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_matches_batch(self, matches: List[Match]) -> int:
        """Add multiple matches to the Matches table. Returns count added."""
        self._ensure_initialized()

        try:
            records = []
            for match in matches:
                fields = self._match_to_airtable_fields(match)
                records.append({"fields": fields})
                print(f"[AIRTABLE] Prepared match: {match.founder_name} -> {match.investor_name}")

            if records:
                print(f"[AIRTABLE] Saving {len(records)} matches to Airtable...")
                # Airtable batch create allows up to 10 records at a time
                for i in range(0, len(records), 10):
                    batch = records[i:i+10]
                    print(f"[AIRTABLE] Batch {i//10 + 1}: {len(batch)} records")
                    # typecast=True helps Airtable auto-convert values to correct types
                    self.matches_table.batch_create([r["fields"] for r in batch], typecast=True)
                print(f"[AIRTABLE] Successfully saved {len(records)} matches")

            return len(records)

        except Exception as e:
            print(f"[AIRTABLE ERROR] Error adding matches batch: {e}")
            import traceback
            traceback.print_exc()
            return 0

    def get_all_matches(self) -> List[Match]:
        """Get all matches from the Matches table."""
        self._ensure_initialized()

        try:
            records = self.matches_table.all()
            matches = []

            for record in records:
                try:
                    match = self._airtable_record_to_match(record)
                    matches.append(match)
                except Exception as e:
                    print(f"Error parsing match record: {e}")
                    continue

            return matches

        except Exception as e:
            print(f"Error getting matches: {e}")
            return []

    def clear_matches(self, recreate_with_new_headers: bool = True) -> bool:
        """Clear all matches from the Matches table."""
        self._ensure_initialized()

        try:
            records = self.matches_table.all()
            record_ids = [r["id"] for r in records]

            # Batch delete (10 at a time)
            for i in range(0, len(record_ids), 10):
                batch = record_ids[i:i+10]
                self.matches_table.batch_delete(batch)

            print(f"[AIRTABLE] Cleared {len(record_ids)} matches")
            return True

        except Exception as e:
            print(f"Error clearing matches: {e}")
            return False

    # ===== DRAFTS TABLE METHODS =====

    def _draft_to_airtable_fields(self, draft: Draft) -> Dict[str, Any]:
        """Convert Draft to Airtable fields dict.

        Note: Date fields (sent_date, created_date) must be omitted if empty,
        not set to empty string, as Airtable cannot parse "" as a date.
        """
        fields = {
            "draft_id": draft.draft_id,
            "match_id": draft.match_id or "",
            "founder_name": draft.founder_name or "",
            "founder_email": draft.founder_email or "",
            "investor_name": draft.investor_name or "",
            "investor_email": draft.investor_email or "",
            "investor_company_name": draft.investor_company_name or "",
            "startup_name": draft.startup_name or "",
            "startup_linkedin": draft.startup_linkedin or "",
            "investor_company_linkedin": draft.investor_company_linkedin or "",
            "startup_description": draft.startup_description or "",
            "startup_milestone": draft.startup_milestone or "",
            "email_subject": draft.email_subject or "",
            "email_body": draft.email_body or "",
            "approval_status": draft.approval_status,
            "reviewer_notes": draft.reviewer_notes or "",
            "send_status": draft.send_status,
        }

        # Only include date fields if they have a value (Airtable can't parse "")
        if draft.created_date:
            fields["created_date"] = draft.created_date
        if draft.sent_date:
            fields["sent_date"] = draft.sent_date

        return fields

    def _airtable_record_to_draft(self, record: Dict[str, Any]) -> Draft:
        """Convert Airtable record to Draft."""
        fields = record.get("fields", {})
        fields["row_number"] = record.get("id", "")
        return Draft.from_dict(fields)

    def add_draft(self, draft: Draft) -> bool:
        """Add a new draft to the Drafts table."""
        self._ensure_initialized()

        try:
            fields = self._draft_to_airtable_fields(draft)
            self.drafts_table.create(fields)
            return True

        except Exception as e:
            print(f"Error adding draft: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_drafts_batch(self, drafts: List[Draft]) -> int:
        """Add multiple drafts to the Drafts table. Returns count added."""
        self._ensure_initialized()

        try:
            records = []
            for draft in drafts:
                fields = self._draft_to_airtable_fields(draft)
                records.append(fields)

            if records:
                # Airtable batch create allows up to 10 records at a time
                for i in range(0, len(records), 10):
                    batch = records[i:i+10]
                    self.drafts_table.batch_create(batch)

            return len(records)

        except Exception as e:
            print(f"Error adding drafts batch: {e}")
            return 0

    def get_all_drafts(self) -> List[Draft]:
        """Get all drafts from the Drafts table."""
        self._ensure_initialized()

        try:
            records = self.drafts_table.all()
            drafts = []

            for record in records:
                try:
                    draft = self._airtable_record_to_draft(record)
                    drafts.append(draft)
                except Exception as e:
                    print(f"Error parsing draft record: {e}")
                    continue

            return drafts

        except Exception as e:
            print(f"Error getting drafts: {e}")
            return []

    def get_pending_drafts(self) -> List[Dict[str, Any]]:
        """Get drafts with PENDING approval status."""
        self._ensure_initialized()

        try:
            formula = "{approval_status} = 'PENDING'"
            records = self.drafts_table.all(formula=formula)
            pending_drafts = []

            for record in records:
                draft_dict = record.get("fields", {}).copy()
                draft_dict["row_number"] = record.get("id", "")
                pending_drafts.append(draft_dict)

            return pending_drafts

        except Exception as e:
            print(f"Error getting pending drafts: {e}")
            return []

    def get_approved_drafts(self) -> List[Dict[str, Any]]:
        """Get drafts with APPROVED status that haven't been sent.

        Note: Uses client-side filtering to handle whitespace/newlines in values.
        Airtable formula filters don't match 'APPROVED\\n' to 'APPROVED'.
        """
        self._ensure_initialized()

        try:
            # Fetch all drafts and filter client-side for robustness
            records = self.drafts_table.all()
            approved_drafts = []

            for record in records:
                draft_dict = record.get("fields", {}).copy()
                draft_dict["row_number"] = record.get("id", "")

                # Normalize approval_status (strip whitespace, uppercase)
                approval_status = str(draft_dict.get("approval_status", "")).strip().upper()
                send_status = str(draft_dict.get("send_status", "")).strip()

                # Check if approved and not yet sent
                if approval_status in ("APPROVED", "TRUE", "YES") and send_status != "Sent":
                    approved_drafts.append(draft_dict)

            return approved_drafts

        except Exception as e:
            print(f"Error getting approved drafts: {e}")
            return []

    def update_draft_status(self, row_number: str, send_status: str, sent_date: str = None) -> bool:
        """Update draft send status and sent date."""
        self._ensure_initialized()

        try:
            updates = {"send_status": send_status}
            if sent_date:
                updates["sent_date"] = sent_date

            self.drafts_table.update(row_number, updates)
            return True

        except Exception as e:
            print(f"Error updating draft status: {e}")
            return False

    def update_match_email_status(self, match_id: str, email_status: str) -> bool:
        """Update match email_status in the Matches table."""
        self._ensure_initialized()

        try:
            formula = f"{{match_id}} = '{match_id}'"
            records = self.matches_table.all(formula=formula)

            if records:
                record_id = records[0]["id"]
                self.matches_table.update(record_id, {"email_status": email_status})
                return True

            return False

        except Exception as e:
            print(f"Error updating match email status: {e}")
            return False

    def get_high_quality_matches_for_drafting(self, min_score: int = 70) -> List[Dict[str, Any]]:
        """Get matches with score > min_score and email_status empty/Pending."""
        self._ensure_initialized()

        try:
            records = self.matches_table.all()
            high_quality_matches = []

            for record in records:
                fields = record.get("fields", {})
                match_dict = fields.copy()
                match_dict["row_number"] = record.get("id", "")

                try:
                    score = int(match_dict.get("match_score", 0))
                except (ValueError, TypeError):
                    score = 0

                email_status = match_dict.get("email_status", "").strip().lower()

                if score >= min_score and email_status in ["", "pending", "drafted"]:
                    high_quality_matches.append(match_dict)

            return high_quality_matches

        except Exception as e:
            print(f"Error getting high quality matches: {e}")
            return []

    def clear_drafts(self, recreate_with_new_headers: bool = True) -> bool:
        """Clear all drafts from the Drafts table."""
        self._ensure_initialized()

        try:
            records = self.drafts_table.all()
            record_ids = [r["id"] for r in records]

            # Batch delete (10 at a time)
            for i in range(0, len(record_ids), 10):
                batch = record_ids[i:i+10]
                self.drafts_table.batch_delete(batch)

            print(f"[AIRTABLE] Cleared {len(record_ids)} drafts")
            return True

        except Exception as e:
            print(f"Error clearing drafts: {e}")
            return False

    # Compatibility methods for worksheet access (not needed for Airtable but keep for interface)
    def get_matches_worksheet(self):
        """For compatibility - returns matches table reference."""
        return self.matches_table

    def get_drafts_worksheet(self):
        """For compatibility - returns drafts table reference."""
        return self.drafts_table


# Global service instance
_sheets_service: Optional[AirtableService] = None


def get_sheets_service() -> AirtableService:
    """Get or create Airtable service instance.

    Note: Function name kept as get_sheets_service() for import compatibility.
    """
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = AirtableService()
    return _sheets_service
