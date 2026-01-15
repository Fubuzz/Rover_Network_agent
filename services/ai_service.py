"""
AI Service for classification, parsing, and OCR using OpenAI and Gemini.
"""

import os
import base64
from typing import Optional, Dict, List, Any
import json

import openai
import google.generativeai as genai

from config import APIConfig, FeatureFlags


class AIService:
    """Service for AI-powered operations."""
    
    def __init__(self):
        self._openai_client = None
        self._gemini_model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize AI clients."""
        # Initialize OpenAI
        if APIConfig.OPENAI_API_KEY:
            openai.api_key = APIConfig.OPENAI_API_KEY
            self._openai_client = openai.OpenAI(api_key=APIConfig.OPENAI_API_KEY)
        
        # Initialize Gemini
        if APIConfig.GEMINI_API_KEY:
            genai.configure(api_key=APIConfig.GEMINI_API_KEY)
            self._gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    
    def _call_openai(self, prompt: str, system_prompt: str = None,
                     model: str = "gpt-3.5-turbo") -> Optional[str]:
        """Call OpenAI API."""
        if not self._openai_client:
            return None
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self._openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None
    
    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API."""
        if not self._gemini_model:
            return None
        
        try:
            response = self._gemini_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
    
    def _call_ai(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Call AI with fallback."""
        # Try OpenAI first
        result = self._call_openai(prompt, system_prompt)
        if result:
            return result
        
        # Fallback to Gemini
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        return self._call_gemini(full_prompt)
    
    def classify_contact(self, contact_info: Dict) -> Dict[str, Any]:
        """
        Classify a contact as founder, investor, enabler, or professional.
        
        Returns:
            Dict with 'classification' and 'confidence' keys.
        """
        system_prompt = """You are a contact classification expert. 
Classify contacts into one of these categories:
- founder: Founders, co-founders, CEOs of startups, entrepreneurs
- investor: VCs, angel investors, PE partners, investment professionals
- enabler: Advisors, mentors, consultants, accelerator/incubator members
- professional: All other professionals (managers, engineers, etc.)

Return a JSON object with 'classification' and 'confidence' (0-1) keys."""

        prompt = f"""Classify this contact:
Name: {contact_info.get('name', 'Unknown')}
Job Title: {contact_info.get('job_title', 'N/A')}
Company: {contact_info.get('company', 'N/A')}
Notes: {contact_info.get('notes', 'N/A')}

Return only valid JSON."""

        try:
            response = self._call_ai(prompt, system_prompt)
            if response:
                # Parse JSON from response
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                
                result = json.loads(response)
                return {
                    "classification": result.get("classification", "professional"),
                    "confidence": result.get("confidence", 0.5)
                }
        except Exception as e:
            print(f"Classification error: {e}")
        
        return {"classification": "professional", "confidence": 0.3}
    
    def parse_contact_info(self, text: str) -> Dict[str, Any]:
        """
        Parse contact information from natural language text.
        """
        system_prompt = """You are a contact information extraction expert.
Extract contact details from the given text and return a JSON object with these fields:
- name: Full name
- job_title: Job title or position
- company: Company or organization name
- phone: Phone number
- email: Email address
- linkedin_url: LinkedIn profile URL
- location: City, country, or address
- notes: Any other relevant information

Only include fields that are explicitly mentioned or can be reasonably inferred.
Return only valid JSON."""

        prompt = f"Extract contact information from this text:\n\n{text}"

        try:
            response = self._call_ai(prompt, system_prompt)
            if response:
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                
                return json.loads(response)
        except Exception as e:
            print(f"Parsing error: {e}")
        
        return {}
    
    def extract_from_image(self, image_data: bytes, 
                          image_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Extract contact information from an image (e.g., business card).
        Uses OpenAI Vision API.
        """
        if not FeatureFlags.IMAGE_OCR:
            return {}
        
        if not self._openai_client:
            return {}
        
        try:
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            response = self._openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract all contact information from this image 
(likely a business card or document). Return a JSON object with:
- name, job_title, company, phone, email, linkedin_url, location
Only include fields that are visible. Return only valid JSON."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            if content:
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                return json.loads(content)
                
        except Exception as e:
            print(f"Image extraction error: {e}")
        
        return {}
    
    def transcribe_audio(self, audio_data: bytes, 
                        filename: str = "audio.ogg") -> Optional[str]:
        """
        Transcribe audio using OpenAI Whisper API.
        """
        if not FeatureFlags.VOICE_TRANSCRIPTION:
            return None
        
        if not self._openai_client:
            return None
        
        try:
            # Create a file-like object
            import io
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename
            
            response = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
            return response.text
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
    
    def enrich_with_summary(self, contact_info: Dict, 
                           search_results: List[Dict]) -> Dict[str, Any]:
        """
        Create a summary of search results for contact enrichment.
        """
        system_prompt = """You are a research analyst. 
Summarize the search results to enrich a contact's profile.
Focus on professional background, achievements, and relevant news.
Return a JSON object with:
- summary: Brief professional summary
- notable_achievements: List of achievements
- recent_news: Any recent news or updates
- additional_info: Any other relevant information"""

        search_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in search_results[:5]
        ])

        prompt = f"""Contact: {contact_info.get('name', 'Unknown')} at {contact_info.get('company', 'Unknown')}

Search Results:
{search_text}

Summarize this information to enrich the contact profile. Return only valid JSON."""

        try:
            response = self._call_ai(prompt, system_prompt)
            if response:
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                
                return json.loads(response)
        except Exception as e:
            print(f"Enrichment summary error: {e}")
        
        return {}
    
    def generate_response(self, query: str, context: str = None) -> str:
        """
        Generate a natural language response for user queries.
        """
        system_prompt = """You are a helpful network management assistant.
Help users manage their professional contacts and network.
Be concise and helpful in your responses."""

        prompt = query
        if context:
            prompt = f"Context:\n{context}\n\nUser query: {query}"

        response = self._call_ai(prompt, system_prompt)
        return response or "I'm sorry, I couldn't process that request."


# Global service instance
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """Get or create AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
