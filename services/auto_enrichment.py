"""
Auto-Enrichment Service — Automatically research contacts after they're saved.

When a contact is added with just a name (and maybe company), this service:
1. Searches the web for info about them
2. Extracts LinkedIn profile, title, company details, industry
3. Updates the contact in Airtable automatically
"""

import os
import logging
import asyncio
from typing import Optional, Dict

logger = logging.getLogger('network_agent')


async def auto_enrich_contact(name: str, company: str = None) -> Dict:
    """
    Auto-enrich a contact by searching the web.
    
    Args:
        name: Contact's full name
        company: Optional company name for better search results
    
    Returns:
        Dict of discovered fields
    """
    import openai
    
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Step 1: Web search via Tavily
    discovered = {}
    search_results = await _search_person(name, company)
    
    if not search_results:
        logger.info(f"[AUTO-ENRICH] No search results for {name}")
        return discovered
    
    # Step 2: Use LLM to extract structured info from search results
    try:
        search_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
            for r in search_results[:5]
        ])
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Extract professional information from search results. Return ONLY a JSON object with these fields (omit any you can't determine):
{
    "title": "job title",
    "company": "company name",
    "industry": "industry",
    "company_description": "brief company description",
    "linkedin_url": "linkedin profile URL",
    "contact_type": "founder|investor|enabler|professional",
    "company_stage": "startup|growth|enterprise",
    "key_strengths": "notable achievements or skills",
    "location": "city, country"
}
Return ONLY valid JSON, nothing else."""},
                {"role": "user", "content": f"Person: {name}\nCompany: {company or 'Unknown'}\n\nSearch results:\n{search_text}"}
            ],
            temperature=0,
            max_tokens=500
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        if "```" in result_text:
            result_text = result_text.split("```")[1].replace("json", "").strip()
        
        discovered = json.loads(result_text)
        logger.info(f"[AUTO-ENRICH] Discovered for {name}: {list(discovered.keys())}")
        
    except Exception as e:
        logger.error(f"[AUTO-ENRICH] LLM extraction error: {e}")
    
    # Step 3: Apply discovered fields to Airtable
    if discovered:
        try:
            from services.airtable_service import get_sheets_service
            sheets = get_sheets_service()
            sheets._ensure_initialized()
            
            # Map discovered fields to Airtable column names
            field_map = {
                "title": "title",
                "company": "company",
                "industry": "industry",
                "company_description": "company_description",
                "linkedin_url": "contact_linkedin_url",
                "contact_type": "contact_type",
                "company_stage": "company_stage",
                "key_strengths": "key_strengths",
                "location": "address",
            }
            
            updates = {}
            for key, airtable_field in field_map.items():
                if key in discovered and discovered[key]:
                    updates[airtable_field] = discovered[key]
            
            if updates:
                # Only update fields that are currently empty
                contact = sheets.get_contact_by_name(name)
                if contact:
                    filtered_updates = {}
                    for field, value in updates.items():
                        current = getattr(contact, field.replace("contact_linkedin_url", "linkedin_url"), None)
                        if not current:
                            filtered_updates[field] = value
                    
                    if filtered_updates:
                        sheets.update_contact(name, filtered_updates)
                        logger.info(f"[AUTO-ENRICH] Updated {name} with: {list(filtered_updates.keys())}")
                    else:
                        logger.info(f"[AUTO-ENRICH] No empty fields to update for {name}")
        except Exception as e:
            logger.error(f"[AUTO-ENRICH] Airtable update error: {e}")
    
    return discovered


async def _search_person(name: str, company: str = None) -> list:
    """Search for a person using Tavily API."""
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    
    if not tavily_key:
        logger.warning("[AUTO-ENRICH] No Tavily API key configured")
        return []
    
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        
        query = f"{name}"
        if company:
            query += f" {company}"
        query += " LinkedIn professional"
        
        result = client.search(query=query, max_results=5, search_depth="basic")
        return result.get("results", [])
        
    except Exception as e:
        logger.error(f"[AUTO-ENRICH] Tavily search error: {e}")
        return []


async def extract_business_card(image_path: str) -> Optional[Dict]:
    """
    Extract contact information from a business card image using GPT-4o Vision.
    
    Args:
        image_path: Path to the business card image
    
    Returns:
        Dict with extracted contact fields, or None
    """
    import openai
    import base64
    
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """Extract all contact information from this business card image. Return ONLY a JSON object with these fields (omit any not visible):
{
    "name": "full name",
    "title": "job title",
    "company": "company name",
    "email": "email address",
    "phone": "phone number",
    "linkedin_url": "linkedin URL if visible",
    "website": "company website",
    "address": "physical address",
    "notes": "any other visible info"
}
Return ONLY valid JSON."""},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract contact information from this business card:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]}
            ],
            temperature=0,
            max_tokens=500
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        if "```" in result_text:
            result_text = result_text.split("```")[1].replace("json", "").strip()
        
        extracted = json.loads(result_text)
        logger.info(f"[OCR] Extracted from business card: {list(extracted.keys())}")
        return extracted
        
    except Exception as e:
        logger.error(f"[OCR] Business card extraction error: {e}")
        return None
