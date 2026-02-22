"""
AI-Powered Research Synthesizer.

This module uses LLMs (Gemini/OpenAI) to:
1. Intelligently extract structured data from raw search results
2. Resolve ambiguities and conflicts between sources
3. Generate missing information through inference
4. Produce high-quality summaries and insights
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import APIConfig
from data.research_schema import (
    ResearchResult, PersonIntelligence, CompanyIntelligence, LinkedInProfile,
    SourcedValue, ConfidenceLevel, DataSource
)


logger = logging.getLogger('ai_research_synthesizer')


RESEARCH_SYNTHESIS_PROMPT = """You are an expert research analyst specializing in extracting and synthesizing information about business professionals.

I have gathered search results about a person. Please analyze and synthesize this information into a structured format.

## PERSON TO RESEARCH
Name: {name}
Company (if known): {company}
Context: {context}

## RAW SEARCH RESULTS
{search_results}

## YOUR TASK
Analyze the search results and extract ALL available information. Be thorough and accurate.

Return a JSON object with the following structure. Only include fields where you found actual evidence - do NOT guess or make up information:

```json
{{
    "person": {{
        "full_name": "Full name as found",
        "first_name": "First name",
        "last_name": "Last name",
        "current_title": "Current job title",
        "current_company": "Current company name",
        "email": "Email if found",
        "phone": "Phone if found",
        "linkedin_url": "LinkedIn profile URL if found",
        "twitter_handle": "Twitter handle if found",
        "location": "City, Country",
        "professional_summary": "2-3 sentence summary of their professional background",
        "expertise_areas": ["area1", "area2", "area3"],
        "previous_companies": ["company1", "company2"],
        "education": ["degree and school if found"],
        "key_achievements": ["achievement1", "achievement2"],
        "contact_type": "Founder|Investor|Enabler",
        "seniority": "C-Level|Founder/Executive|VP|Director|Manager|Senior IC|IC"
    }},
    "company": {{
        "name": "Company name",
        "website": "Company website URL",
        "linkedin_url": "Company LinkedIn URL",
        "description": "What the company does",
        "industry": "Industry category",
        "company_size": "Employee range or number",
        "headquarters": "City, Country",
        "funding_stage": "Seed|Series A|Series B|etc",
        "total_funding": "Amount raised (e.g., $5M)",
        "founded_year": 2020,
        "investors": ["investor1", "investor2"],
        "founders": ["founder1", "founder2"]
    }},
    "confidence": {{
        "name_verified": true,
        "title_verified": true,
        "company_verified": true,
        "overall": "HIGH|MEDIUM|LOW"
    }},
    "data_sources": ["source1_url", "source2_url"],
    "research_notes": ["Important note 1", "Any conflicts or ambiguities"]
}}
```

## RULES
1. Only include information you actually found in the search results
2. If you're uncertain about something, note it in research_notes
3. For contact_type:
   - "Founder" = Started/founded a company, co-founder, or CEO of a startup
   - "Investor" = Works at VC/PE firm, angel investor, or makes investments
   - "Enabler" = Everyone else (executives at big companies, consultants, service providers)
4. Be precise with URLs - only include if you found the exact URL
5. For funding, include the currency symbol and amount (e.g., "$5M", "$10M")
6. If you find conflicting information, note the conflict and provide the most reliable version

Return ONLY the JSON object, no other text."""


class AIResearchSynthesizer:
    """
    Uses AI to intelligently synthesize research results.
    """
    
    def __init__(self):
        self._openai_client = None
        self._gemini_client = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of AI clients."""
        if self._initialized:
            return
        
        # Try OpenAI first
        try:
            import openai
            if APIConfig.OPENAI_API_KEY:
                self._openai_client = openai.OpenAI(api_key=APIConfig.OPENAI_API_KEY)
                logger.info("OpenAI client initialized for research synthesis")
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")
        
        # Try Gemini as fallback
        if not self._openai_client:
            try:
                import google.generativeai as genai
                if APIConfig.GEMINI_API_KEY:
                    genai.configure(api_key=APIConfig.GEMINI_API_KEY)
                    self._gemini_client = genai.GenerativeModel('gemini-1.5-flash')
                    logger.info("Gemini client initialized for research synthesis")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
        
        self._initialized = True
    
    def synthesize_research(self, name: str, company: str = None,
                           search_results: List[Dict[str, Any]] = None,
                           context: str = None) -> Dict[str, Any]:
        """
        Use AI to synthesize raw search results into structured data.
        """
        self._initialize()
        
        if not search_results:
            return {"error": "No search results to synthesize"}
        
        # Format search results for the prompt
        formatted_results = self._format_search_results(search_results)
        
        prompt = RESEARCH_SYNTHESIS_PROMPT.format(
            name=name,
            company=company or "Unknown",
            context=context or "No additional context",
            search_results=formatted_results
        )
        
        # Call AI
        if self._openai_client:
            return self._call_openai(prompt)
        elif self._gemini_client:
            return self._call_gemini(prompt)
        else:
            logger.error("No AI client available for synthesis")
            return {"error": "No AI client available"}
    
    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for the prompt."""
        formatted = []
        for i, result in enumerate(results[:15], 1):  # Limit to 15 results
            formatted.append(f"""
### Result {i}
**URL:** {result.get('url', 'N/A')}
**Title:** {result.get('title', 'N/A')}
**Content:** {result.get('content', result.get('snippet', 'N/A'))[:500]}
""")
        return "\n".join(formatted)
    
    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI for synthesis."""
        try:
            response = self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a research analyst. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"OpenAI synthesis error: {e}")
            return {"error": str(e)}
    
    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Call Gemini for synthesis."""
        try:
            response = self._gemini_client.generate_content(prompt)
            content = response.text
            
            # Extract JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Gemini synthesis error: {e}")
            return {"error": str(e)}
    
    def enrich_research_result(self, result: ResearchResult,
                               search_results: List[Dict[str, Any]]) -> ResearchResult:
        """
        Use AI to enrich a ResearchResult with synthesized data.
        """
        # Extract full name from search query (query is "Name Company" format)
        if result.person and result.person.full_name:
            name = result.person.full_name
        elif result.search_query:
            # search_query is "Name Company" — extract the name portion
            # If we know the company, strip it from the query to get the name
            query = result.search_query
            if result.company and result.company.name:
                name = query.replace(result.company.name, "").strip()
            elif result.person and result.person.current_company:
                name = query.replace(result.person.current_company, "").strip()
            else:
                name = query
            name = name if name else "Unknown"
        else:
            name = "Unknown"
        company = None
        if result.person and result.person.current_company:
            company = result.person.current_company
        elif result.company:
            company = result.company.name
        
        synthesis = self.synthesize_research(
            name=name,
            company=company,
            search_results=search_results
        )
        
        if "error" in synthesis:
            result.warnings.append(f"AI synthesis failed: {synthesis['error']}")
            return result
        
        # Apply synthesized person data
        if "person" in synthesis and synthesis["person"]:
            person_data = synthesis["person"]
            
            if not result.person:
                result.person = PersonIntelligence(
                    full_name=person_data.get("full_name", name)
                )
            
            # Only update if we got new data
            if person_data.get("current_title") and not result.person.current_title:
                result.person.current_title = person_data["current_title"]
            
            if person_data.get("current_company") and not result.person.current_company:
                result.person.current_company = person_data["current_company"]
            
            if person_data.get("linkedin_url") and not result.person.linkedin_url:
                result.person.linkedin_url = person_data["linkedin_url"]
                result.field_mappings["linkedin_url"] = SourcedValue(
                    value=person_data["linkedin_url"],
                    confidence=ConfidenceLevel.MEDIUM,
                    source=DataSource.AI_INFERENCE
                )
            
            if person_data.get("email") and not result.person.email:
                result.person.email = person_data["email"]
            
            if person_data.get("phone") and not result.person.phone:
                result.person.phone = person_data["phone"]
            
            if person_data.get("location") and not result.person.location:
                result.person.location = person_data["location"]
            
            if person_data.get("professional_summary") and not result.person.professional_summary:
                result.person.professional_summary = person_data["professional_summary"]
            
            if person_data.get("expertise_areas"):
                existing = set(result.person.expertise_areas)
                for area in person_data["expertise_areas"]:
                    if area not in existing:
                        result.person.expertise_areas.append(area)
            
            if person_data.get("contact_type") and not result.person.contact_type:
                result.person.contact_type = person_data["contact_type"]
            
            if person_data.get("seniority") and not result.person.seniority:
                result.person.seniority = person_data["seniority"]
        
        # Apply synthesized company data
        if "company" in synthesis and synthesis["company"]:
            company_data = synthesis["company"]
            
            if not result.company and company_data.get("name"):
                result.company = CompanyIntelligence(name=company_data["name"])
            
            if result.company:
                if company_data.get("website") and not result.company.website:
                    result.company.website = company_data["website"]
                
                if company_data.get("linkedin_url") and not result.company.linkedin_url:
                    result.company.linkedin_url = company_data["linkedin_url"]
                
                if company_data.get("description") and not result.company.description:
                    result.company.description = company_data["description"]
                
                if company_data.get("industry") and not result.company.industry:
                    result.company.industry = company_data["industry"]
                
                if company_data.get("company_size") and not result.company.company_size:
                    result.company.company_size = company_data["company_size"]
                
                if company_data.get("headquarters") and not result.company.headquarters:
                    result.company.headquarters = company_data["headquarters"]
                
                if company_data.get("funding_stage") and not result.company.funding_stage:
                    result.company.funding_stage = company_data["funding_stage"]
                
                if company_data.get("total_funding") and not result.company.total_funding:
                    result.company.total_funding = company_data["total_funding"]
                
                if company_data.get("founded_year") and not result.company.founded_year:
                    result.company.founded_year = company_data["founded_year"]
                
                if company_data.get("investors"):
                    existing = set(result.company.investors)
                    for investor in company_data["investors"]:
                        if investor not in existing:
                            result.company.investors.append(investor)
                
                if company_data.get("founders"):
                    existing = set(result.company.founders)
                    for founder in company_data["founders"]:
                        if founder not in existing:
                            result.company.founders.append(founder)
        
        # Update confidence based on AI synthesis
        if "confidence" in synthesis:
            conf = synthesis["confidence"]
            overall = conf.get("overall", "LOW").upper()
            
            if overall == "HIGH":
                result.overall_confidence = ConfidenceLevel.HIGH
            elif overall == "MEDIUM":
                result.overall_confidence = ConfidenceLevel.MEDIUM
            else:
                result.overall_confidence = ConfidenceLevel.LOW
            
            if conf.get("name_verified"):
                result.accuracy_indicators.append("Name verified by AI")
            if conf.get("title_verified"):
                result.accuracy_indicators.append("Title verified by AI")
            if conf.get("company_verified"):
                result.accuracy_indicators.append("Company verified by AI")
        
        # Add research notes
        if "research_notes" in synthesis and synthesis["research_notes"]:
            result.research_notes.extend(synthesis["research_notes"])
        
        # Store data sources
        if "data_sources" in synthesis:
            for url in synthesis["data_sources"]:
                result.raw_search_results.append({"url": url, "source": "ai_identified"})
        
        return result


# Global instance
_synthesizer: Optional[AIResearchSynthesizer] = None


def get_synthesizer() -> AIResearchSynthesizer:
    """Get or create the AI synthesizer instance."""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = AIResearchSynthesizer()
    return _synthesizer
