"""
Interaction Tracker - Track interactions with contacts and calculate relationship scores.

Implements the relationship decay & health scoring algorithm from the V3 Masterplan:
- Base: 50 (new contact)
- +20 if enriched (you invested time to learn about them)
- +10 per interaction (capped at +40)
- +15 if you've introduced them to someone
- +10 if they've been introduced to you by someone
- -5 per week of no interaction (decay)
- -20 if >3 months dormant
- Minimum: 10 (never fully lost)
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR
from data.schema import Contact
from services.airtable_service import get_sheets_service

logger = logging.getLogger('network_agent')

DB_PATH = DATA_DIR / "interactions.db"


class InteractionTracker:
    """Manages interaction tracking and relationship scoring."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize interactions database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                context TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index separately (SQLite doesn't support inline INDEX)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_timestamp 
            ON interactions (contact_name, timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def log_interaction(self, user_id: str, contact_name: str, interaction_type: str, context: str = None) -> bool:
        """
        Log an interaction with a contact.
        
        Args:
            user_id: User identifier
            contact_name: Name of the contact
            interaction_type: Type of interaction (met, called, emailed, introduced, messaged)
            context: Optional context about the interaction
        
        Returns:
            True if successful
        """
        valid_types = ["met", "called", "emailed", "introduced", "messaged", "added", "updated", "enriched"]
        if interaction_type not in valid_types:
            logger.warning(f"Invalid interaction type: {interaction_type}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO interactions (user_id, contact_name, interaction_type, context, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, contact_name, interaction_type, context, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            # Update contact fields in Airtable
            sheets = get_sheets_service()
            sheets._ensure_initialized()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get current contact to increment interaction count
            contact = sheets.get_contact_by_name(contact_name)
            if contact:
                current_count = contact.interaction_count or 0
                updates = {
                    "last_interaction_date": now,
                    "interaction_count": current_count + 1
                }
                sheets.update_contact(contact_name, updates)
                logger.info(f"[INTERACTION] Logged {interaction_type} with {contact_name} (count: {current_count + 1})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            return False
    
    def get_interactions(self, contact_name: str, limit: int = 10) -> List[Dict]:
        """
        Get recent interactions for a contact.
        
        Args:
            contact_name: Name of the contact
            limit: Maximum number of interactions to return
        
        Returns:
            List of interaction dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT interaction_type, context, timestamp
            FROM interactions
            WHERE contact_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (contact_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        interactions = [
            {
                "type": row[0],
                "context": row[1],
                "timestamp": row[2]
            }
            for row in rows
        ]
        
        return interactions
    
    def calculate_relationship_score(self, contact_name: str) -> int:
        """
        Calculate relationship score for a contact using the V3 algorithm.
        
        Scoring Algorithm:
        - Base: 50 (new contact)
        - +20 if enriched (research_quality or linkedin_summary exists)
        - +10 per interaction (capped at +40)
        - +15 if you've introduced them to someone
        - +10 if they've been introduced to you by someone
        - -5 per week of no interaction (decay)
        - -20 if >3 months dormant
        - Minimum: 10 (never fully lost)
        
        Args:
            contact_name: Name of the contact
        
        Returns:
            Relationship score (0-100)
        """
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        contact = sheets.get_contact_by_name(contact_name)
        if not contact:
            return 0
        
        # Start with base score
        score = 50
        
        # +20 if enriched (has research data)
        if contact.research_quality or contact.linkedin_summary or contact.company_description:
            score += 20
        
        # +10 per interaction (capped at +40)
        interaction_count = contact.interaction_count or 0
        interaction_bonus = min(interaction_count * 10, 40)
        score += interaction_bonus
        
        # +15 if you've introduced them to someone
        if contact.introduced_to:
            score += 15
        
        # +10 if they've been introduced to you by someone
        if contact.introduced_by:
            score += 10
        
        # Apply decay based on last interaction date
        if contact.last_interaction_date:
            try:
                last_interaction = datetime.strptime(contact.last_interaction_date, "%Y-%m-%d %H:%M:%S")
                weeks_since = (datetime.now() - last_interaction).days / 7
                
                # -5 per week of no interaction
                decay = int(weeks_since * 5)
                score -= decay
                
                # -20 additional penalty if >3 months dormant
                if weeks_since > 12:  # ~3 months
                    score -= 20
                    
            except (ValueError, TypeError):
                # Invalid date format, skip decay calculation
                pass
        
        # Clamp to valid range (10-100)
        score = max(10, min(100, score))
        
        return score
    
    def get_contacts_needing_follow_up(self, user_id: str) -> List[Contact]:
        """
        Get contacts that need follow-up (follow_up_date is today or in the past).
        
        Args:
            user_id: User identifier
        
        Returns:
            List of Contact objects
        """
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        all_contacts = sheets.get_all_contacts()
        
        today = datetime.now().date()
        contacts_to_follow_up = []
        
        for contact in all_contacts:
            if contact.follow_up_date:
                try:
                    # Parse follow_up_date (might be just date or full datetime)
                    if len(contact.follow_up_date) <= 10:
                        follow_up = datetime.strptime(contact.follow_up_date, "%Y-%m-%d").date()
                    else:
                        follow_up = datetime.strptime(contact.follow_up_date, "%Y-%m-%d %H:%M:%S").date()
                    
                    if follow_up <= today:
                        contacts_to_follow_up.append(contact)
                except (ValueError, TypeError):
                    # Invalid date format, skip
                    pass
        
        return contacts_to_follow_up
    
    def get_decaying_relationships(self, user_id: str, threshold: int = 40) -> List[tuple]:
        """
        Get contacts with decaying relationships (score below threshold).
        
        Args:
            user_id: User identifier
            threshold: Score threshold (default 40)
        
        Returns:
            List of (contact, score) tuples
        """
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        all_contacts = sheets.get_all_contacts()
        
        decaying = []
        for contact in all_contacts:
            score = self.calculate_relationship_score(contact.name)
            if score < threshold:
                decaying.append((contact, score))
        
        # Sort by score (lowest first)
        decaying.sort(key=lambda x: x[1])
        
        return decaying


# Global singleton
_interaction_tracker: Optional[InteractionTracker] = None


def get_interaction_tracker() -> InteractionTracker:
    """Get global interaction tracker instance."""
    global _interaction_tracker
    if _interaction_tracker is None:
        _interaction_tracker = InteractionTracker()
    return _interaction_tracker
