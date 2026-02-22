"""
Contact classification service.
"""

from typing import Dict, Any, Tuple
from services.ai_service import get_ai_service
from utils.constants import CLASSIFICATION_KEYWORDS


class ClassificationService:
    """Service for classifying contacts."""
    
    def __init__(self):
        self._ai_service = None
    
    @property
    def ai_service(self):
        if self._ai_service is None:
            self._ai_service = get_ai_service()
        return self._ai_service
    
    def classify_by_rules(self, contact_data: Dict) -> Tuple[str, float]:
        """
        Classify contact using rule-based approach.
        Returns (classification, confidence).
        """
        # Combine relevant text fields
        text = " ".join([
            contact_data.get("name", ""),
            contact_data.get("job_title", ""),
            contact_data.get("company", ""),
            contact_data.get("notes", ""),
        ]).lower()
        
        scores = {category: 0 for category in CLASSIFICATION_KEYWORDS}
        total_matches = 0
        
        for category, keywords in CLASSIFICATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[category] += 1
                    total_matches += 1
        
        # Find the highest scoring category
        if total_matches == 0:
            return "unknown", 0.2
        
        max_category = max(scores, key=scores.get)
        max_score = scores[max_category]
        
        # Calculate confidence based on proportion of matches
        confidence = min(0.9, max_score / max(1, sum(scores.values())) * 0.5 + 0.4)
        
        return max_category, confidence
    
    def classify_by_ai(self, contact_data: Dict) -> Tuple[str, float]:
        """
        Classify contact using AI.
        Returns (classification, confidence).
        """
        try:
            result = self.ai_service.classify_contact(contact_data)
            return result.get("classification", "professional"), result.get("confidence", 0.5)
        except Exception as e:
            print(f"AI classification error: {e}")
            return "professional", 0.3
    
    def classify(self, contact_data: Dict, use_ai: bool = True) -> Dict[str, Any]:
        """
        Classify a contact.
        
        Returns a dict with classification, confidence, and method used.
        """
        # First, try rule-based classification
        rule_classification, rule_confidence = self.classify_by_rules(contact_data)
        
        # If rule-based is confident, use it
        if rule_confidence >= 0.7:
            return {
                "classification": rule_classification,
                "confidence": rule_confidence,
                "method": "rules"
            }
        
        # Otherwise, try AI classification if enabled
        if use_ai:
            ai_classification, ai_confidence = self.classify_by_ai(contact_data)
            
            # Use AI result if it's more confident
            if ai_confidence > rule_confidence:
                return {
                    "classification": ai_classification,
                    "confidence": ai_confidence,
                    "method": "ai"
                }
        
        # Fall back to rule-based result
        return {
            "classification": rule_classification,
            "confidence": rule_confidence,
            "method": "rules"
        }
    
    def get_classification_reasoning(self, contact_data: Dict, 
                                    classification: str) -> str:
        """
        Get a human-readable explanation for the classification.
        """
        job_title = contact_data.get("job_title", "").lower()
        company = contact_data.get("company", "").lower()
        
        reasons = []
        
        if classification == "founder":
            if any(kw in job_title for kw in ["founder", "ceo", "chief executive"]):
                reasons.append(f"Job title indicates a founding role")
            if any(kw in job_title for kw in ["entrepreneur", "started"]):
                reasons.append("Background suggests entrepreneurship")
        
        elif classification == "investor":
            if any(kw in job_title for kw in ["investor", "partner", "vc"]):
                reasons.append("Job title indicates investment role")
            if any(kw in company for kw in ["capital", "ventures", "fund"]):
                reasons.append("Company appears to be an investment firm")
        
        elif classification == "enabler":
            if any(kw in job_title for kw in ["advisor", "mentor", "consultant"]):
                reasons.append("Job title indicates advisory role")
            if any(kw in company for kw in ["accelerator", "incubator"]):
                reasons.append("Associated with startup ecosystem support")
        
        else:  # professional
            reasons.append("General professional profile")
        
        if not reasons:
            reasons.append("Classification based on overall profile analysis")
        
        return "; ".join(reasons)


# Global service instance
_classification_service = None


def get_classification_service() -> ClassificationService:
    """Get or create classification service instance."""
    global _classification_service
    if _classification_service is None:
        _classification_service = ClassificationService()
    return _classification_service
