"""
Local SQLite storage for contacts when Google Sheets is unavailable.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json

from config import LOGS_DIR
from data.schema import Contact


class LocalContactStorage:
    """Local SQLite storage for contacts."""
    
    def __init__(self):
        self.db_path = LOGS_DIR / "contacts_local.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                linkedin_url TEXT,
                company TEXT,
                title TEXT,
                source TEXT DEFAULT 'telegram',
                how_we_met TEXT,
                notes TEXT,
                status TEXT DEFAULT 'active',
                contact_type TEXT,
                industry TEXT,
                address TEXT,
                user_id TEXT,
                created_date TEXT,
                updated_date TEXT,
                extra_data TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_contact(self, contact: Contact) -> bool:
        """Add a contact to local storage."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO contacts (
                    contact_id, first_name, last_name, full_name, email, phone,
                    linkedin_url, company, title, source, how_we_met, notes,
                    status, contact_type, industry, address, user_id,
                    created_date, updated_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contact.contact_id,
                contact.first_name,
                contact.last_name,
                contact.full_name or contact.name,
                contact.email,
                contact.phone,
                contact.linkedin_url,
                contact.company,
                contact.title,
                contact.source,
                contact.how_we_met,
                contact.notes,
                contact.status,
                contact.contact_type,
                contact.industry,
                contact.address,
                contact.user_id,
                now,
                now
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            print(f"Error adding contact to local storage: {e}")
            return False
    
    def get_contact_by_name(self, name: str) -> Optional[Contact]:
        """Get a contact by name."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM contacts 
                WHERE LOWER(full_name) = LOWER(?) 
                   OR LOWER(first_name) = LOWER(?)
                   OR (LOWER(first_name) || ' ' || LOWER(last_name)) = LOWER(?)
            """, (name, name, name))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._row_to_contact(row)
            return None
            
        except Exception as e:
            print(f"Error getting contact: {e}")
            return None
    
    def get_all_contacts(self) -> List[Contact]:
        """Get all contacts."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM contacts WHERE status = 'active' ORDER BY created_date DESC")
            
            rows = cursor.fetchall()
            conn.close()
            
            return [self._row_to_contact(row) for row in rows]
            
        except Exception as e:
            print(f"Error getting all contacts: {e}")
            return []
    
    def search_contacts(self, query: str) -> List[Contact]:
        """Search contacts."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            search = f"%{query}%"
            cursor.execute("""
                SELECT * FROM contacts 
                WHERE full_name LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                   OR company LIKE ? OR title LIKE ? OR email LIKE ? OR notes LIKE ?
            """, (search, search, search, search, search, search, search))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [self._row_to_contact(row) for row in rows]
            
        except Exception as e:
            print(f"Error searching contacts: {e}")
            return []
    
    def update_contact(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update a contact."""
        try:
            contact = self.get_contact_by_name(name)
            if not contact:
                return False
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Build update query
            set_clauses = []
            values = []
            
            field_mapping = {
                'email': 'email', 'phone': 'phone', 'company': 'company',
                'title': 'title', 'job_title': 'title', 'notes': 'notes',
                'contact_type': 'contact_type', 'classification': 'contact_type',
                'address': 'address', 'location': 'address', 'industry': 'industry',
                'linkedin_url': 'linkedin_url', 'linkedin': 'linkedin_url'
            }
            
            for key, value in updates.items():
                db_field = field_mapping.get(key, key)
                set_clauses.append(f"{db_field} = ?")
                values.append(value)
            
            set_clauses.append("updated_date = ?")
            values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            values.append(contact.contact_id)
            
            query = f"UPDATE contacts SET {', '.join(set_clauses)} WHERE contact_id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error updating contact: {e}")
            return False
    
    def delete_contact(self, name: str) -> bool:
        """Delete a contact (soft delete)."""
        try:
            contact = self.get_contact_by_name(name)
            if not contact:
                return False
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE contacts SET status = 'deleted', updated_date = ? WHERE contact_id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), contact.contact_id)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error deleting contact: {e}")
            return False
    
    def get_contact_stats(self) -> Dict[str, Any]:
        """Get contact statistics."""
        contacts = self.get_all_contacts()
        
        stats = {
            "total": len(contacts),
            "by_classification": {},
            "by_company": {},
            "by_location": {},
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
            if contact.email:
                stats["with_email"] += 1
            if contact.phone:
                stats["with_phone"] += 1
            if contact.linkedin_url:
                stats["with_linkedin"] += 1
        
        return stats
    
    def _row_to_contact(self, row: sqlite3.Row) -> Contact:
        """Convert database row to Contact object."""
        return Contact(
            contact_id=row['contact_id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            full_name=row['full_name'],
            email=row['email'],
            phone=row['phone'],
            linkedin_url=row['linkedin_url'],
            company=row['company'],
            title=row['title'],
            source=row['source'],
            how_we_met=row['how_we_met'],
            notes=row['notes'],
            status=row['status'],
            contact_type=row['contact_type'],
            industry=row['industry'],
            address=row['address'],
            user_id=row['user_id'],
            created_date=row['created_date'],
            updated_date=row['updated_date']
        )


# Global instance
_local_storage: Optional[LocalContactStorage] = None


def get_local_storage() -> LocalContactStorage:
    """Get or create local storage instance."""
    global _local_storage
    if _local_storage is None:
        _local_storage = LocalContactStorage()
    return _local_storage
