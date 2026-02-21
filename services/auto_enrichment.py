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


async def deep_enrich_from_linkedin(contact_name: str, linkedin_url: str) -> Dict:
    """
    Deep enrichment via LinkedIn scraper service.
    
    Calls the scraper API (running on Ahmed's Mac) to get full profile data:
    experience, skills, education, certifications, AI summary.
    
    Args:
        contact_name: Contact's name (for logging)
        linkedin_url: LinkedIn profile URL
    
    Returns:
        Dict of enriched fields, or empty dict if service unavailable
    """
    scraper_url = os.getenv("LINKEDIN_SCRAPER_URL", "http://localhost:8585")
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{scraper_url}/scrape",
                json={"url": linkedin_url}
            )
            
            if resp.status_code != 200:
                logger.warning(f"[DEEP-ENRICH] Scraper returned {resp.status_code} for {contact_name}")
                return {}
            
            data = resp.json()
            logger.info(f"[DEEP-ENRICH] Got LinkedIn data for {contact_name}: "
                       f"{len(data.get('experience', []))} roles, "
                       f"{len(data.get('skills', []))} skills")
            
            # Map scraped data to Airtable-compatible fields
            enriched = {}
            
            if data.get("headline"):
                enriched["title"] = data["headline"]
            
            if data.get("location"):
                enriched["address"] = data["location"]
            
            if data.get("skills"):
                enriched["key_strengths"] = ", ".join(data["skills"][:20])
            
            if data.get("about"):
                enriched["company_description"] = data["about"][:2000]
            
            # Extract current company/title from latest experience
            if data.get("experience"):
                latest = data["experience"][0]
                if latest.get("company"):
                    enriched["company"] = latest["company"]
                if latest.get("title"):
                    enriched["title"] = latest["title"]
            
            # Build a rich summary for notes
            summary_parts = []
            if data.get("summary"):
                summary_parts.append(data["summary"])
            
            if data.get("education"):
                edu_lines = [f"• {e.get('degree', '')} — {e.get('school', '')} ({e.get('duration', '')})"
                            for e in data["education"]]
                summary_parts.append("\n📚 Education:\n" + "\n".join(edu_lines))
            
            if data.get("experience"):
                exp_lines = [f"• {e.get('title', '')} at {e.get('company', '')} ({e.get('duration', '')})"
                            for e in data["experience"][:5]]
                summary_parts.append("\n💼 Experience:\n" + "\n".join(exp_lines))
            
            if summary_parts:
                enriched["_linkedin_summary"] = "\n\n".join(summary_parts)
            
            # Store raw profile data for Rover's intelligence features
            enriched["_raw_linkedin"] = data
            
            return enriched
    
    except ImportError:
        logger.warning("[DEEP-ENRICH] httpx not installed — pip install httpx")
        return {}
    except Exception as e:
        logger.info(f"[DEEP-ENRICH] Scraper service unavailable for {contact_name}: {e}")
        return {}


async def auto_enrich_contact(name: str, company: str = None, linkedin_url: str = None) -> Dict:
    """
    Auto-enrich a contact by searching the web.
    
    If a LinkedIn URL is available and the scraper service is running,
    does deep enrichment first. Falls back to Tavily + GPT-4o-mini.
    
    Args:
        name: Contact's full name
        company: Optional company name for better search results
        linkedin_url: Optional LinkedIn URL for deep enrichment
    
    Returns:
        Dict of discovered fields
    """
    import openai
    
    # Try deep LinkedIn enrichment first
    linkedin_enriched = {}
    if linkedin_url:
        linkedin_enriched = await deep_enrich_from_linkedin(name, linkedin_url)
    
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Step 1: Web search via Tavily (use LinkedIn URL as anchor if available)
    discovered = {}
    search_results = await _search_person(name, company, linkedin_url=linkedin_url)
    
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
                {"role": "user", "content": f"Person: {name}\nCompany: {company or 'Unknown'}\nLinkedIn: {linkedin_url or 'Unknown'}\n\nIMPORTANT: Only extract info about THIS specific person. If search results mention other people with similar names, ignore them.\n\nSearch results:\n{search_text}"}
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
    
    # Merge: LinkedIn deep data takes priority, Tavily fills gaps
    if linkedin_enriched:
        # Remove internal keys before merging
        raw_linkedin = linkedin_enriched.pop("_raw_linkedin", None)
        linkedin_summary = linkedin_enriched.pop("_linkedin_summary", None)
        
        # LinkedIn data fills first, Tavily fills remaining gaps
        for key, value in linkedin_enriched.items():
            if key not in discovered or not discovered[key]:
                discovered[key] = value
    
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
                    # NEVER overwrite user-provided data — only fill empty fields
                    # Map Airtable field names to Contact attribute names
                    field_to_attr = {
                        "contact_linkedin_url": "linkedin_url",
                        "title": "title",
                        "company": "company",
                        "industry": "industry",
                        "company_description": "company_description",
                        "contact_type": "contact_type",
                        "company_stage": "company_stage",
                        "key_strengths": "key_strengths",
                        "address": "address",
                    }
                    filtered_updates = {}
                    for field, value in updates.items():
                        attr_name = field_to_attr.get(field, field)
                        current = getattr(contact, attr_name, None)
                        if not current:
                            filtered_updates[field] = value
                        else:
                            logger.info(f"[AUTO-ENRICH] Skipping {field} — already has value: {current[:50] if isinstance(current, str) else current}")
                    
                    if filtered_updates:
                        sheets.update_contact(name, filtered_updates)
                        logger.info(f"[AUTO-ENRICH] Updated {name} with: {list(filtered_updates.keys())}")
                    else:
                        logger.info(f"[AUTO-ENRICH] No empty fields to update for {name}")
        except Exception as e:
            logger.error(f"[AUTO-ENRICH] Airtable update error: {e}")
    
    return discovered


async def _search_person(name: str, company: str = None, linkedin_url: str = None) -> list:
    """Search for a person using Tavily API.
    
    When a LinkedIn URL is available, searches for that specific profile
    to avoid matching wrong people with similar names.
    """
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    
    if not tavily_key:
        logger.warning("[AUTO-ENRICH] No Tavily API key configured")
        return []
    
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        
        results = []
        
        # Strategy 1: If we have a LinkedIn URL, search for it directly
        if linkedin_url:
            # Clean the URL (remove tracking params)
            clean_url = linkedin_url.split("?")[0].rstrip("/")
            
            # Extract the slug for a targeted search
            slug = ""
            if "/in/" in clean_url:
                slug = clean_url.split("/in/")[-1].replace("-", " ")
                # Remove the ID suffix (e.g. "8aa36b107")
                import re
                slug = re.sub(r'\b[a-f0-9]{6,}\b', '', slug).strip()
            
            # Search with LinkedIn URL directly — most accurate
            try:
                result = client.search(
                    query=f"site:linkedin.com {clean_url} {name}",
                    max_results=3,
                    search_depth="basic",
                    include_domains=["linkedin.com"]
                )
                results.extend(result.get("results", []))
                logger.info(f"[AUTO-ENRICH] LinkedIn-targeted search got {len(results)} results")
            except Exception as e:
                logger.debug(f"[AUTO-ENRICH] LinkedIn-targeted search failed: {e}")
            
            # Also do a general search with the name for company/industry context
            try:
                general_query = f'"{name}"'
                if company:
                    general_query += f" {company}"
                elif slug:
                    general_query += f" {slug}"
                general_query += " professional"
                
                result = client.search(query=general_query, max_results=3, search_depth="basic")
                results.extend(result.get("results", []))
            except Exception as e:
                logger.debug(f"[AUTO-ENRICH] General search failed: {e}")
        else:
            # No LinkedIn URL — original behavior
            query = f"{name}"
            if company:
                query += f" {company}"
            query += " LinkedIn professional"
            
            result = client.search(query=query, max_results=5, search_depth="basic")
            results = result.get("results", [])
        
        logger.info(f"[AUTO-ENRICH] Total search results for {name}: {len(results)}")
        return results
        
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
