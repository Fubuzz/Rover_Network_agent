"""
Introduction Service — Manage network introductions via Airtable.

Handles:
- Creating introduction records
- Drafting intro messages
- Tracking intro status
- Suggesting potential introductions based on contact overlap
"""

import os
import logging
from typing import Optional, List, Dict
from datetime import datetime

from pyairtable import Api
from config import AirtableConfig, AIConfig

logger = logging.getLogger('network_agent')

INTRODUCTIONS_TABLE = os.getenv("AIRTABLE_INTRODUCTIONS_TABLE", "Introductions")


class IntroductionService:
    """Manages introductions between contacts."""
    
    def __init__(self):
        self.api = None
        self.table = None
        self._initialized = False
    
    def initialize(self):
        """Initialize connection to Airtable Introductions table."""
        try:
            self.api = Api(AirtableConfig.AIRTABLE_PAT)
            self.table = self.api.table(
                AirtableConfig.AIRTABLE_BASE_ID,
                INTRODUCTIONS_TABLE
            )
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to init IntroductionService: {e}")
            return False
    
    def _ensure_initialized(self):
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("IntroductionService not initialized")
    
    def create_introduction(self, connector_name: str, target_name: str, 
                          reason: str = None, status: str = "suggested",
                          intro_message: str = None) -> Optional[str]:
        """
        Create a new introduction record.
        
        Args:
            connector_name: Person who can make the intro
            target_name: Person to be introduced to
            reason: Why this intro makes sense
            status: suggested|requested|made|declined
            intro_message: Draft intro message
        
        Returns:
            Record ID if successful, None otherwise
        """
        self._ensure_initialized()
        
        try:
            fields = {
                "connector_name": connector_name,
                "target_name": target_name,
                "status": status,
                "requested_date": datetime.now().strftime("%Y-%m-%d"),
            }
            
            if reason:
                fields["reason"] = reason
            if intro_message:
                fields["intro_message_draft"] = intro_message
            
            # Try to link to actual contact records
            from services.airtable_service import get_sheets_service
            sheets = get_sheets_service()
            sheets._ensure_initialized()
            
            connector = sheets.get_contact_by_name(connector_name)
            if connector and connector.row_number:
                fields["connector_contact"] = [connector.row_number]
            
            target = sheets.get_contact_by_name(target_name)
            if target and target.row_number:
                fields["target_contact"] = [target.row_number]
            
            record = self.table.create(fields, typecast=True)
            logger.info(f"[INTRO] Created: {connector_name} → {target_name} ({status})")
            return record["id"]
            
        except Exception as e:
            logger.error(f"Error creating introduction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_introductions(self, status: str = None) -> List[Dict]:
        """Get all introductions, optionally filtered by status."""
        self._ensure_initialized()
        
        try:
            if status:
                formula = f"{{status}} = '{status}'"
                records = self.table.all(formula=formula)
            else:
                records = self.table.all()
            
            return [
                {
                    "id": r["id"],
                    "connector": r["fields"].get("connector_name", "Unknown"),
                    "target": r["fields"].get("target_name", "Unknown"),
                    "reason": r["fields"].get("reason", ""),
                    "status": r["fields"].get("status", "suggested"),
                    "requested_date": r["fields"].get("requested_date", ""),
                    "intro_date": r["fields"].get("intro_date", ""),
                    "outcome": r["fields"].get("outcome", ""),
                    "intro_message": r["fields"].get("intro_message_draft", ""),
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Error getting introductions: {e}")
            return []
    
    def update_introduction(self, record_id: str, updates: Dict) -> bool:
        """Update an introduction record."""
        self._ensure_initialized()
        try:
            self.table.update(record_id, updates, typecast=True)
            return True
        except Exception as e:
            logger.error(f"Error updating introduction: {e}")
            return False
    
    def suggest_introductions(self) -> List[Dict]:
        """
        Suggest potential introductions based on contact data.
        
        Looks for contacts in the same industry who might benefit from knowing each other,
        or contacts who could help each other (e.g., founder + investor in same sector).
        """
        from services.airtable_service import get_sheets_service
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        contacts = sheets.get_all_contacts()
        if len(contacts) < 2:
            return []
        
        suggestions = []
        
        # Strategy 1: Founder + Investor in same industry
        founders = [c for c in contacts if c.contact_type and c.contact_type.lower() in ('founder', 'professional')]
        investors = [c for c in contacts if c.contact_type and c.contact_type.lower() == 'investor']
        
        for founder in founders:
            for investor in investors:
                if founder.industry and investor.industry:
                    f_industries = set(founder.industry.lower().split(','))
                    i_industries = set(investor.industry.lower().split(','))
                    overlap = f_industries & i_industries
                    if overlap:
                        suggestions.append({
                            "connector": founder.name,
                            "target": investor.name,
                            "reason": f"Both in {', '.join(overlap)}. {founder.name} ({founder.company or 'founder'}) could benefit from meeting {investor.name} ({investor.company or 'investor'}).",
                            "type": "founder_investor_match"
                        })
        
        # Strategy 2: Same industry, different companies
        by_industry = {}
        for c in contacts:
            if c.industry:
                for ind in c.industry.lower().split(','):
                    ind = ind.strip()
                    if ind:
                        by_industry.setdefault(ind, []).append(c)
        
        for industry, group in by_industry.items():
            if len(group) >= 2:
                for i in range(min(len(group), 3)):
                    for j in range(i + 1, min(len(group), 4)):
                        c1, c2 = group[i], group[j]
                        if c1.company != c2.company:
                            # Check if this intro already exists
                            existing = [s for s in suggestions 
                                       if (s['connector'] == c1.name and s['target'] == c2.name) or
                                          (s['connector'] == c2.name and s['target'] == c1.name)]
                            if not existing:
                                suggestions.append({
                                    "connector": c1.name,
                                    "target": c2.name,
                                    "reason": f"Both in {industry}. {c1.name} ({c1.company or 'N/A'}) and {c2.name} ({c2.company or 'N/A'}) could exchange insights.",
                                    "type": "industry_peers"
                                })
        
        return suggestions[:10]  # Limit to 10 suggestions
    
    def draft_intro_message(self, connector_name: str, target_name: str, context: str = None) -> str:
        """
        Draft an introduction message using OpenAI.
        
        Args:
            connector_name: Person making/facilitating the intro
            target_name: Person being introduced
            context: Additional context about why this intro matters
        
        Returns:
            Draft message text
        """
        from services.airtable_service import get_sheets_service
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        
        connector = sheets.get_contact_by_name(connector_name)
        target = sheets.get_contact_by_name(target_name)
        
        # Build context
        connector_info = f"{connector_name}"
        if connector and connector.company:
            connector_info += f" ({connector.title or ''} at {connector.company})"
        
        target_info = f"{target_name}"
        if target and target.company:
            target_info += f" ({target.title or ''} at {target.company})"
        
        context_str = f"\nContext: {context}" if context else ""
        
        try:
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model=AIConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You write brief, warm professional introduction messages. Keep it under 100 words. Be natural, not corporate."},
                    {"role": "user", "content": f"Draft an intro message from me (Ahmed) to {connector_info}, introducing them to {target_info}.{context_str}\n\nWrite just the message, no subject line."}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error drafting intro message: {e}")
            # Fallback template
            return f"Hey {connector_name}! I'd love to connect you with {target_name}. I think you two would have a lot to talk about. Would you be open to an intro?"


# Global singleton
_introduction_service: Optional[IntroductionService] = None


def get_introduction_service() -> IntroductionService:
    """Get global IntroductionService instance."""
    global _introduction_service
    if _introduction_service is None:
        _introduction_service = IntroductionService()
    return _introduction_service
