"""
Google Sheets service for contact management.
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Optional, Dict, Any
from datetime import datetime

from config import GoogleSheetsConfig, BASE_DIR
from data.schema import (
    Contact, SHEET_HEADERS, COL_INDEX,
    Match, MATCH_SHEET_HEADERS,
    Draft, DRAFT_SHEET_HEADERS, ApprovalStatus, SendStatus,
    CONTACTS_SHEET_NAME, MATCHES_SHEET_NAME, DRAFTS_SHEET_NAME
)


class GoogleSheetsService:
    """Service for interacting with Google Sheets."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self):
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        self.worksheet: Optional[gspread.Worksheet] = None
        self._initialized = False
        self._headers = None
    
    def initialize(self) -> bool:
        """Initialize connection to Google Sheets."""
        try:
            # Load credentials
            creds_path = BASE_DIR / GoogleSheetsConfig.CREDENTIALS_FILE
            
            if not creds_path.exists():
                print(f"Credentials file not found at {creds_path}")
                return False
            
            credentials = Credentials.from_service_account_file(
                str(creds_path),
                scopes=self.SCOPES
            )
            
            self.client = gspread.authorize(credentials)
            
            # Open spreadsheet - try by ID first, then by name as fallback
            sheet_id = GoogleSheetsConfig.get_sheet_id()
            
            try:
                if sheet_id:
                    self.spreadsheet = self.client.open_by_key(sheet_id)
                else:
                    # Try by name
                    self.spreadsheet = self.client.open("Contacts_DataBase")
            except Exception as e:
                print(f"Could not open by ID ({sheet_id}), trying by name...")
                try:
                    self.spreadsheet = self.client.open("Contacts_DataBase")
                except Exception as e2:
                    # Last resort: open first available sheet
                    all_sheets = self.client.openall()
                    if all_sheets:
                        self.spreadsheet = all_sheets[0]
                        print(f"Opened first available sheet: {self.spreadsheet.title}")
                    else:
                        print(f"No sheets available: {e2}")
                        return False
            
            # Get the contacts worksheet (Sheet 1, named "contacts")
            try:
                self.worksheet = self.spreadsheet.worksheet(CONTACTS_SHEET_NAME)
            except gspread.WorksheetNotFound:
                # Fall back to first sheet if "contacts" not found
                self.worksheet = self.spreadsheet.sheet1
                print(f"Note: '{CONTACTS_SHEET_NAME}' sheet not found, using first sheet")

            # Get headers from first row
            self._headers = self.worksheet.row_values(1)

            self._initialized = True
            print(f"Connected to Google Sheet: {self.spreadsheet.title}")
            print(f"Contacts worksheet: {self.worksheet.title} with {len(self._headers)} columns")
            return True
            
        except Exception as e:
            print(f"Failed to initialize Google Sheets: {e}")
            import traceback
            traceback.print_exc()
            self._initialized = False
            return False
    
    def _ensure_initialized(self):
        """Ensure service is initialized."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Google Sheets service not initialized")
    
    def _get_col_index(self, col_name: str) -> int:
        """Get column index by name (0-based)."""
        if self._headers and col_name in self._headers:
            return self._headers.index(col_name)
        # Fallback to predefined mapping
        return COL_INDEX.get(col_name, -1)
    
    def add_contact(self, contact: Contact) -> bool:
        """Add a new contact to the sheet."""
        self._ensure_initialized()

        try:
            # Check for duplicates by email - BUT only block if it's the SAME person
            # Different people can share email (e.g., company-wide alias)
            if contact.email:
                existing = self.find_contact_by_email(contact.email)
                if existing:
                    # Check if it's truly the same person (name match)
                    existing_name = (existing.name or "").lower().strip()
                    new_name = (contact.name or "").lower().strip()

                    # If names are similar, it's probably the same person - skip (should use update instead)
                    if existing_name and new_name:
                        # Check for exact match or first name match
                        if existing_name == new_name or existing_name.split()[0] == new_name.split()[0]:
                            print(f"Contact '{contact.name}' with email {contact.email} already exists - use update instead")
                            return False

                    # Different names but same email - allow but warn
                    print(f"Note: Email {contact.email} also used by '{existing.name}', but adding '{contact.name}' as separate contact")

            # Add the contact
            row = contact.to_sheet_row()
            
            # Ensure row matches header count
            while len(row) < len(self._headers):
                row.append("")
            row = row[:len(self._headers)]  # Trim if too long
            
            self.worksheet.append_row(row)
            return True
            
        except Exception as e:
            print(f"Error adding contact: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_contact(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing contact."""
        self._ensure_initialized()
        
        try:
            # Find the contact
            contact = self.get_contact_by_name(name)
            if not contact:
                return False
            
            row_number = contact.row_number
            if not row_number:
                return False
            
            # Apply updates using field mapping
            field_to_col = {
                "email": "email",
                "phone": "phone",
                "company": "company",
                "title": "title",
                "job_title": "title",
                "linkedin": "linkedin_url",
                "linkedin_url": "linkedin_url",
                "location": "address",
                "address": "address",
                "notes": "notes",
                "classification": "contact_type",
                "contact_type": "contact_type",
                "industry": "industry",
                "how_we_met": "how_we_met",
                "tags": "key_strengths",
            }
            
            for key, value in updates.items():
                col_name = field_to_col.get(key, key)
                col_idx = self._get_col_index(col_name)
                if col_idx >= 0:
                    # gspread uses 1-based indexing
                    self.worksheet.update_cell(row_number, col_idx + 1, value)
            
            # Update the updated_date
            updated_col = self._get_col_index("updated_date")
            if updated_col >= 0:
                self.worksheet.update_cell(row_number, updated_col + 1, 
                                          datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            return True
            
        except Exception as e:
            print(f"Error updating contact: {e}")
            return False
    
    def delete_contact(self, name: str) -> bool:
        """Delete a contact by name."""
        self._ensure_initialized()
        
        try:
            contact = self.get_contact_by_name(name)
            if not contact or not contact.row_number:
                return False
            
            self.worksheet.delete_rows(contact.row_number)
            return True
            
        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    def get_contact_by_name(self, name: str) -> Optional[Contact]:
        """Get a contact by name (searches full_name and first_name + last_name)."""
        self._ensure_initialized()
        
        try:
            name_lower = name.lower().strip()
            all_values = self.worksheet.get_all_values()
            
            # Get column indices
            full_name_col = self._get_col_index("full_name")
            first_name_col = self._get_col_index("first_name")
            last_name_col = self._get_col_index("last_name")
            
            for i, row in enumerate(all_values[1:], start=2):  # Skip header
                if not row:
                    continue
                
                # Check full_name
                if full_name_col >= 0 and len(row) > full_name_col:
                    if row[full_name_col].lower().strip() == name_lower:
                        return Contact.from_sheet_row(row, row_number=i)
                
                # Check first_name + last_name
                if first_name_col >= 0 and last_name_col >= 0:
                    if len(row) > max(first_name_col, last_name_col):
                        combined = f"{row[first_name_col]} {row[last_name_col]}".lower().strip()
                        if combined == name_lower or row[first_name_col].lower().strip() == name_lower:
                            return Contact.from_sheet_row(row, row_number=i)
            
            return None

        except Exception as e:
            print(f"Error getting contact: {e}")
            return None

    def get_contact_by_id(self, contact_id: str) -> Optional[Contact]:
        """Get a contact by contact_id (for Sheet 1 lookups from Matches)."""
        self._ensure_initialized()

        if not contact_id:
            return None

        try:
            all_values = self.worksheet.get_all_values()
            contact_id_col = self._get_col_index("contact_id")

            if contact_id_col < 0:
                return None

            for i, row in enumerate(all_values[1:], start=2):  # Skip header
                if len(row) > contact_id_col and row[contact_id_col].strip() == contact_id.strip():
                    return Contact.from_sheet_row(row, row_number=i)

            return None

        except Exception as e:
            print(f"Error getting contact by ID: {e}")
            return None

    def get_contact_dict_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a contact as a raw dict by contact_id.

        This reads actual column headers from the sheet, so it works with
        columns like 'contact_linkedin_url' and 'company_linkedin_url'.
        """
        self._ensure_initialized()

        if not contact_id:
            return None

        try:
            all_values = self.worksheet.get_all_values()
            if not all_values:
                return None

            headers = all_values[0]  # Actual headers from sheet
            contact_id_col = headers.index("contact_id") if "contact_id" in headers else -1

            if contact_id_col < 0:
                return None

            for row in all_values[1:]:  # Skip header
                if len(row) > contact_id_col and row[contact_id_col].strip() == contact_id.strip():
                    # Create dict with actual headers
                    return {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}

            return None

        except Exception as e:
            print(f"Error getting contact dict by ID: {e}")
            return None

    def find_contact_by_email(self, email: str) -> Optional[Contact]:
        """Find a contact by email."""
        self._ensure_initialized()
        
        try:
            email = email.lower().strip()
            all_values = self.worksheet.get_all_values()
            email_col = self._get_col_index("email")
            
            if email_col < 0:
                return None
            
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) > email_col and row[email_col].lower().strip() == email:
                    return Contact.from_sheet_row(row, row_number=i)
            
            return None
            
        except Exception as e:
            print(f"Error finding contact by email: {e}")
            return None
    
    def get_all_contacts(self) -> List[Contact]:
        """Get all contacts from the sheet."""
        self._ensure_initialized()
        
        try:
            all_values = self.worksheet.get_all_values()
            contacts = []
            
            for i, row in enumerate(all_values[1:], start=2):  # Skip header
                if row and any(row):  # Has some data
                    try:
                        contact = Contact.from_sheet_row(row, row_number=i)
                        if contact.name and contact.name != "Unknown":
                            contacts.append(contact)
                    except Exception as e:
                        print(f"Error parsing row {i}: {e}")
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
            # Search across multiple fields
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
            # By classification/contact_type
            if contact.contact_type:
                stats["by_classification"][contact.contact_type] = \
                    stats["by_classification"].get(contact.contact_type, 0) + 1
            
            # By company
            if contact.company:
                stats["by_company"][contact.company] = \
                    stats["by_company"].get(contact.company, 0) + 1
            
            # By location
            if contact.address:
                stats["by_location"][contact.address] = \
                    stats["by_location"].get(contact.address, 0) + 1
            
            # By industry
            if contact.industry:
                stats["by_industry"][contact.industry] = \
                    stats["by_industry"].get(contact.industry, 0) + 1
            
            # Field completeness
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
        
        all_values = self.worksheet.get_all_values()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        for row in all_values:
            writer.writerow(row)
        
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
                    # Create contact from CSV row (assuming same format)
                    contact = Contact.from_sheet_row(row)
                    if self.add_contact(contact):
                        imported += 1
                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue
        
        return imported

    # ===== MATCHES SHEET METHODS =====

    def get_matches_worksheet(self) -> Optional[gspread.Worksheet]:
        """Get or create the Matches worksheet (Sheet 2)."""
        self._ensure_initialized()

        try:
            # Try to get existing Matches worksheet
            try:
                matches_ws = self.spreadsheet.worksheet(MATCHES_SHEET_NAME)
                return matches_ws
            except gspread.WorksheetNotFound:
                # Create the Matches worksheet
                matches_ws = self.spreadsheet.add_worksheet(
                    title=MATCHES_SHEET_NAME,
                    rows=1000,
                    cols=len(MATCH_SHEET_HEADERS)
                )
                # Add headers
                matches_ws.append_row(MATCH_SHEET_HEADERS)
                print(f"Created '{MATCHES_SHEET_NAME}' worksheet with {len(MATCH_SHEET_HEADERS)} columns")
                return matches_ws

        except Exception as e:
            print(f"Error getting/creating Matches worksheet: {e}")
            return None

    def get_all_contacts_as_json(self) -> List[Dict[str, Any]]:
        """Get all contacts as a list of dictionaries (JSON format)."""
        self._ensure_initialized()

        try:
            all_values = self.worksheet.get_all_values()
            if not all_values:
                return []

            headers = all_values[0]
            contacts_json = []

            for i, row in enumerate(all_values[1:], start=2):  # Skip header
                if row and any(row):  # Has some data
                    contact_dict = {}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            contact_dict[header] = row[j]
                        else:
                            contact_dict[header] = ""
                    contact_dict["row_number"] = i
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

    def add_match(self, match: Match) -> bool:
        """Add a new match to the Matches sheet."""
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return False

            row = match.to_sheet_row()

            # Ensure row matches header count
            while len(row) < len(MATCH_SHEET_HEADERS):
                row.append("")
            row = row[:len(MATCH_SHEET_HEADERS)]

            matches_ws.append_row(row)
            return True

        except Exception as e:
            print(f"Error adding match: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_matches_batch(self, matches: List[Match]) -> int:
        """Add multiple matches to the Matches sheet. Returns count added."""
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return 0

            rows = []
            for match in matches:
                row = match.to_sheet_row()
                while len(row) < len(MATCH_SHEET_HEADERS):
                    row.append("")
                rows.append(row[:len(MATCH_SHEET_HEADERS)])

            if rows:
                matches_ws.append_rows(rows)

            return len(rows)

        except Exception as e:
            print(f"Error adding matches batch: {e}")
            return 0

    def get_all_matches(self) -> List[Match]:
        """Get all matches from the Matches sheet."""
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return []

            all_values = matches_ws.get_all_values()
            matches = []

            if len(all_values) <= 1:  # Only header or empty
                return []

            headers = all_values[0]

            for row in all_values[1:]:
                if row and any(row):
                    match_dict = {}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            match_dict[header] = row[j]
                    try:
                        match = Match.from_dict(match_dict)
                        matches.append(match)
                    except Exception as e:
                        print(f"Error parsing match row: {e}")
                        continue

            return matches

        except Exception as e:
            print(f"Error getting matches: {e}")
            return []

    def clear_matches(self, recreate_with_new_headers: bool = True) -> bool:
        """
        Clear all matches from the Matches sheet.
        If recreate_with_new_headers=True, deletes the sheet and recreates with current schema.
        """
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return False

            if recreate_with_new_headers:
                # DELETE the entire sheet and recreate with correct headers
                print("[SHEETS] Deleting Matches sheet to recreate with new schema...")
                self.spreadsheet.del_worksheet(matches_ws)
                # Recreate - get_matches_worksheet will create with correct headers
                new_ws = self.get_matches_worksheet()
                print(f"[SHEETS] Recreated Matches sheet with {len(MATCH_SHEET_HEADERS)} columns")
                return new_ws is not None
            else:
                # Just clear data, keep existing headers
                all_values = matches_ws.get_all_values()
                if len(all_values) > 1:
                    matches_ws.delete_rows(2, len(all_values))
                return True

        except Exception as e:
            print(f"Error clearing matches: {e}")
            return False

    # ===== DRAFTS SHEET METHODS =====

    def get_drafts_worksheet(self) -> Optional[gspread.Worksheet]:
        """Get or create the Drafts worksheet (Sheet 3)."""
        self._ensure_initialized()

        try:
            # Try to get existing Drafts worksheet
            try:
                drafts_ws = self.spreadsheet.worksheet(DRAFTS_SHEET_NAME)
                return drafts_ws
            except gspread.WorksheetNotFound:
                # Create the Drafts worksheet
                drafts_ws = self.spreadsheet.add_worksheet(
                    title=DRAFTS_SHEET_NAME,
                    rows=1000,
                    cols=len(DRAFT_SHEET_HEADERS)
                )
                # Add headers
                drafts_ws.append_row(DRAFT_SHEET_HEADERS)
                print(f"Created '{DRAFTS_SHEET_NAME}' worksheet with {len(DRAFT_SHEET_HEADERS)} columns")
                return drafts_ws

        except Exception as e:
            print(f"Error getting/creating Drafts worksheet: {e}")
            return None

    def add_draft(self, draft: Draft) -> bool:
        """Add a new draft to the Drafts sheet."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return False

            row = draft.to_sheet_row()

            # Ensure row matches header count
            while len(row) < len(DRAFT_SHEET_HEADERS):
                row.append("")
            row = row[:len(DRAFT_SHEET_HEADERS)]

            drafts_ws.append_row(row)
            return True

        except Exception as e:
            print(f"Error adding draft: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_drafts_batch(self, drafts: List[Draft]) -> int:
        """Add multiple drafts to the Drafts sheet. Returns count added."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return 0

            rows = []
            for draft in drafts:
                row = draft.to_sheet_row()
                while len(row) < len(DRAFT_SHEET_HEADERS):
                    row.append("")
                rows.append(row[:len(DRAFT_SHEET_HEADERS)])

            if rows:
                drafts_ws.append_rows(rows)

            return len(rows)

        except Exception as e:
            print(f"Error adding drafts batch: {e}")
            return 0

    def get_all_drafts(self) -> List[Draft]:
        """Get all drafts from the Drafts sheet."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return []

            all_values = drafts_ws.get_all_values()
            drafts = []

            if len(all_values) <= 1:  # Only header or empty
                return []

            headers = all_values[0]

            for i, row in enumerate(all_values[1:], start=2):
                if row and any(row):
                    draft_dict = {"row_number": i}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            draft_dict[header] = row[j]
                    try:
                        draft = Draft.from_dict(draft_dict)
                        drafts.append(draft)
                    except Exception as e:
                        print(f"Error parsing draft row: {e}")
                        continue

            return drafts

        except Exception as e:
            print(f"Error getting drafts: {e}")
            return []

    def get_pending_drafts(self) -> List[Dict[str, Any]]:
        """Get drafts with PENDING approval status."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return []

            all_values = drafts_ws.get_all_values()
            if len(all_values) <= 1:
                return []

            headers = all_values[0]
            pending_drafts = []

            for i, row in enumerate(all_values[1:], start=2):
                if row and any(row):
                    draft_dict = {"row_number": i}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            draft_dict[header] = row[j]
                    # Filter for PENDING
                    if draft_dict.get("approval_status", "").upper() == "PENDING":
                        pending_drafts.append(draft_dict)

            return pending_drafts

        except Exception as e:
            print(f"Error getting pending drafts: {e}")
            return []

    def get_approved_drafts(self) -> List[Dict[str, Any]]:
        """Get drafts with APPROVED status that haven't been sent."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return []

            all_values = drafts_ws.get_all_values()
            if len(all_values) <= 1:
                return []

            headers = all_values[0]
            approved_drafts = []

            for i, row in enumerate(all_values[1:], start=2):
                if row and any(row):
                    draft_dict = {"row_number": i}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            draft_dict[header] = row[j]
                    # Filter for APPROVED and not Sent
                    approval = draft_dict.get("approval_status", "").upper()
                    send_status = draft_dict.get("send_status", "")
                    if approval in ["APPROVED", "TRUE"] and send_status != "Sent":
                        approved_drafts.append(draft_dict)

            return approved_drafts

        except Exception as e:
            print(f"Error getting approved drafts: {e}")
            return []

    def update_draft_status(self, row_number: int, send_status: str, sent_date: str = None) -> bool:
        """Update draft send status and sent date."""
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return False

            headers = drafts_ws.row_values(1)

            # Find column indices
            send_status_col = headers.index("send_status") + 1 if "send_status" in headers else -1
            sent_date_col = headers.index("sent_date") + 1 if "sent_date" in headers else -1

            if send_status_col > 0:
                drafts_ws.update_cell(row_number, send_status_col, send_status)

            if sent_date_col > 0 and sent_date:
                drafts_ws.update_cell(row_number, sent_date_col, sent_date)

            return True

        except Exception as e:
            print(f"Error updating draft status: {e}")
            return False

    def update_match_email_status(self, match_id: str, email_status: str) -> bool:
        """Update match email_status in the Matches sheet."""
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return False

            all_values = matches_ws.get_all_values()
            if len(all_values) <= 1:
                return False

            headers = all_values[0]
            match_id_col = headers.index("match_id") if "match_id" in headers else -1
            email_status_col = headers.index("email_status") + 1 if "email_status" in headers else -1

            if match_id_col < 0 or email_status_col <= 0:
                return False

            # Find the row with this match_id
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) > match_id_col and row[match_id_col] == match_id:
                    matches_ws.update_cell(i, email_status_col, email_status)
                    return True

            return False

        except Exception as e:
            print(f"Error updating match email status: {e}")
            return False

    def get_high_quality_matches_for_drafting(self, min_score: int = 70) -> List[Dict[str, Any]]:
        """Get matches with score > min_score and email_status empty/Pending."""
        self._ensure_initialized()

        try:
            matches_ws = self.get_matches_worksheet()
            if not matches_ws:
                return []

            all_values = matches_ws.get_all_values()
            if len(all_values) <= 1:
                return []

            headers = all_values[0]
            high_quality_matches = []

            for i, row in enumerate(all_values[1:], start=2):
                if row and any(row):
                    match_dict = {"row_number": i}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            match_dict[header] = row[j]

                    # Filter criteria: score > min_score AND email_status is empty/Pending
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
        """
        Clear all drafts from the Drafts sheet.
        If recreate_with_new_headers=True, deletes the sheet and recreates with current schema.
        This fixes column misalignment issues when the schema has changed.
        """
        self._ensure_initialized()

        try:
            drafts_ws = self.get_drafts_worksheet()
            if not drafts_ws:
                return False

            if recreate_with_new_headers:
                # DELETE the entire sheet and recreate with correct headers
                print("[SHEETS] Deleting Drafts sheet to recreate with new schema...")
                if self.spreadsheet:
                    self.spreadsheet.del_worksheet(drafts_ws)
                    # Recreate - get_drafts_worksheet will create with correct headers
                    new_ws = self.get_drafts_worksheet()
                    print(f"[SHEETS] Recreated Drafts sheet with {len(DRAFT_SHEET_HEADERS)} columns")
                    print(f"[SHEETS] Headers: {DRAFT_SHEET_HEADERS}")
                    return new_ws is not None
                return False
            else:
                # Just clear data, keep existing headers
                all_values = drafts_ws.get_all_values()
                if len(all_values) > 1:
                    drafts_ws.delete_rows(2, len(all_values))
                return True

        except Exception as e:
            print(f"Error clearing drafts: {e}")
            return False


# Global service instance
_sheets_service: Optional[GoogleSheetsService] = None


def get_sheets_service() -> GoogleSheetsService:
    """Get or create Google Sheets service instance."""
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = GoogleSheetsService()
    return _sheets_service
