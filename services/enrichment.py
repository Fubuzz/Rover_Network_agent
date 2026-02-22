"""
Enrichment service using Tavily for web searches.
Enhanced with comprehensive contact data enrichment.
"""

import logging
import json
import re
import time
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, List, Any

from config import APIConfig
from services.ai_service import get_ai_service

logger = logging.getLogger('network_agent')


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Decorator for retrying API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for wait time between retries
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = backoff_factor ** attempt
                        logger.warning(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}")
                        logger.warning(f"[RETRY] Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
            logger.error(f"[RETRY] All {max_retries} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

# Enrichment field definitions
ENRICHMENT_FIELDS = [
    "full_name", "company", "title", "linkedin_url", "company_description",
    "industry", "company_stage", "funding_raised", "linkedin_summary",
    "contact_type", "research_quality", "email", "phone", "website",
    "address", "key_strengths", "founder_score", "sector_fit", "stage_fit",
    "notes", "researched_date", "status"
]


class EnrichmentService:
    """Service for enriching contact data through web searches."""

    def __init__(self):
        self.api_key = APIConfig.TAVILY_API_KEY
        self._ai_service = None
        self._api_valid = None  # Track if API key is valid
        self._api_invalid_since = None  # Timestamp when API was marked invalid
        self._api_retry_cooldown = 300  # Retry after 5 minutes
        self._last_error = None
        self._tavily_client = None

    @property
    def ai_service(self):
        if self._ai_service is None:
            self._ai_service = get_ai_service()
        return self._ai_service

    @property
    def tavily_client(self):
        """Lazy-load Tavily client."""
        if self._tavily_client is None and self.api_key:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=self.api_key)
            except ImportError:
                logger.error("tavily-python not installed. Run: pip install tavily-python")
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
        return self._tavily_client

    @retry_with_backoff(max_retries=3, backoff_factor=2.0, exceptions=(ConnectionError, TimeoutError))
    def _search(self, query: str, num_results: int = 10) -> List[Dict]:
        """Perform a web search using Tavily with automatic retry on failure."""
        if not self.api_key:
            logger.warning("Tavily API key not configured")
            self._last_error = "API key not configured"
            return []

        # Skip if API key is invalid, but allow retry after cooldown
        if self._api_valid is False:
            import time
            if (self._api_invalid_since and
                    time.time() - self._api_invalid_since < self._api_retry_cooldown):
                return []
            # Cooldown expired, allow retry
            logger.info("API key cooldown expired, retrying...")
            self._api_valid = None

        if not self.tavily_client:
            self._last_error = "Tavily client not initialized"
            return []

        try:
            response = self.tavily_client.search(
                query=query,
                max_results=num_results,
                include_answer=False
            )

            results = response.get("results", [])
            self._api_valid = True
            self._api_invalid_since = None

            logger.info(f"Tavily search '{query}' returned {len(results)} results")

            return [
                {
                    "title": r.get("title", ""),
                    "link": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "source": r.get("url", "").split("/")[2] if r.get("url") else ""
                }
                for r in results
            ]

        except Exception as e:
            import time
            error_msg = str(e)
            logger.error(f"Tavily search error: {error_msg}")
            self._last_error = error_msg
            if "Invalid API key" in error_msg or "401" in error_msg:
                self._api_valid = False
                self._api_invalid_since = time.time()
                return []
            # Re-raise non-auth errors so @retry_with_backoff can retry them
            raise

    def get_last_error(self) -> Optional[str]:
        """Get the last error message from Tavily."""
        return self._last_error

    def is_available(self) -> bool:
        """Check if Tavily is available and working."""
        return self._api_valid is not False and bool(self.api_key)
    
    def search_person(self, name: str, company: str = None) -> List[Dict]:
        """Search for information about a person."""
        query = name
        if company:
            query = f"{name} {company}"
        
        return self._search(query)
    
    def search_linkedin_profile(self, name: str, company: str = None) -> Optional[str]:
        """Search for a person's LinkedIn profile."""
        query = f"site:linkedin.com/in {name}"
        if company:
            query = f"{query} {company}"

        results = self._search(query, num_results=5)

        for result in results:
            link = result.get("link", "")
            # CRITICAL: Only return personal profiles (/in/), NEVER company pages
            if self._is_personal_linkedin(link):
                return link

        return None

    def _is_personal_linkedin(self, url: str) -> bool:
        """Check if a LinkedIn URL is a personal profile (not company/school)."""
        if not url:
            return False
        url_lower = url.lower()
        # Personal profiles contain /in/
        if "/in/" in url_lower:
            # Make sure it's not a false positive
            if "/company/" not in url_lower and "/school/" not in url_lower:
                return True
        return False

    def _is_company_linkedin(self, url: str) -> bool:
        """Check if a LinkedIn URL is a company page."""
        if not url:
            return False
        url_lower = url.lower()
        return "/company/" in url_lower

    def _validate_and_route_linkedin(self, url: str, result: Dict[str, Any]):
        """
        Validate a LinkedIn URL and route it to the correct field.
        - /in/ URLs go to contact_linkedin_url
        - /company/ URLs go to company_linkedin_url
        """
        if not url:
            return

        if self._is_personal_linkedin(url):
            if result.get("contact_linkedin_url") == "NA":
                result["contact_linkedin_url"] = url
                logger.info(f"Routed personal LinkedIn: {url}")
        elif self._is_company_linkedin(url):
            if result.get("company_linkedin_url") == "NA":
                result["company_linkedin_url"] = url
                logger.info(f"Routed company LinkedIn: {url}")
    
    def search_company(self, company_name: str) -> Dict[str, Any]:
        """Search for company information."""
        logger.info(f"Searching for company: '{company_name}'")

        # Search for company info
        results = self._search(f"{company_name} company information")
        
        # Search for company LinkedIn
        linkedin_results = self._search(f"site:linkedin.com/company {company_name}", 3)
        
        # Search for recent news
        news_results = self._search(f"{company_name} news", 5)
        
        # Compile results
        company_info = {
            "name": company_name,
            "search_results": results[:5],
            "linkedin_url": None,
            "recent_news": [],
            "summary": None
        }
        
        # Extract LinkedIn URL
        for result in linkedin_results:
            link = result.get("link", "")
            if "linkedin.com/company/" in link:
                company_info["linkedin_url"] = link
                break
        
        # Extract recent news
        company_info["recent_news"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", "")
            }
            for r in news_results[:3]
        ]
        
        return company_info
    
    def enrich_contact(self, contact_data: Dict) -> Dict[str, Any]:
        """
        Enrich contact data with online search.
        
        Returns enrichment data to be added to the contact.
        """
        name = contact_data.get("name", "")
        company = contact_data.get("company", "")
        
        if not name:
            return {}
        
        enrichment = {
            "search_performed": True,
            "search_timestamp": None,
            "linkedin_url": None,
            "company_info": None,
            "summary": None,
            "additional_info": {}
        }
        
        from datetime import datetime
        enrichment["search_timestamp"] = datetime.now().isoformat()
        
        # Search for the person
        person_results = self.search_person(name, company)
        
        # Find LinkedIn profile if not already present
        if not contact_data.get("linkedin_url"):
            linkedin_url = self.search_linkedin_profile(name, company)
            if linkedin_url:
                enrichment["linkedin_url"] = linkedin_url
        
        # Search for company info
        if company:
            company_info = self.search_company(company)
            enrichment["company_info"] = company_info
        
        # Use AI to summarize findings
        if person_results:
            summary = self.ai_service.enrich_with_summary(
                contact_data,
                person_results
            )
            enrichment["summary"] = summary.get("summary", "")
            enrichment["additional_info"] = summary
        
        return enrichment
    
    def research_topic(self, query: str) -> Dict[str, Any]:
        """
        Research a specific topic or query.
        Returns structured research results.
        """
        results = self._search(query)

        return {
            "query": query,
            "results": results,
            "result_count": len(results)
        }

    def enrich_contact_comprehensive(self, name: str, company: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform comprehensive contact enrichment.
        Returns a structured result matching the expected enrichment format.
        """
        logger.info(f"Starting comprehensive enrichment for: {name} (company: {company})")

        # Initialize result with NA values
        result = self._create_empty_enrichment(name, company)

        # Validate input
        if not name or name.lower() in ["unknown", "na", "n/a", "generic user"]:
            result["notes"] = "Input too vague to perform search."
            result["status"] = "Failed"
            return result

        # Check if this is a company-only search
        is_company_search = self._is_company_search(name)

        try:
            # Search for person/company info
            if is_company_search:
                self._enrich_company(name, result)
            else:
                self._enrich_person(name, company, result)

            # Extract additional info from LinkedIn summary
            self._extract_from_linkedin_summary(result)

            # Determine final status and quality
            self._calculate_enrichment_quality(result)

        except Exception as e:
            logger.error(f"Enrichment error for {name}: {e}")
            result["notes"] = f"Enrichment error: {str(e)}"
            result["status"] = "Failed"
            result["research_quality"] = "Low"

        result["researched_date"] = datetime.now().strftime("%Y-%m-%d")
        return result

    def _create_empty_enrichment(self, name: str = None, company: str = None) -> Dict[str, Any]:
        """Create an empty enrichment result with NA values."""
        return {
            "full_name": name or "NA",
            "company": company or "NA",
            "title": "NA",
            "contact_linkedin_url": "NA",  # Personal LinkedIn profile
            "company_linkedin_url": "NA",  # Company LinkedIn page
            "company_description": "NA",
            "industry": "NA",
            "company_stage": "NA",
            "funding_raised": "NA",
            "linkedin_summary": "NA",
            "contact_type": "NA",  # Founder, Enabler, or Investor
            "research_quality": "Low",
            "email": "NA",
            "phone": "NA",
            "website": "NA",
            "address": "NA",
            "key_strengths": "NA",
            "founder_score": "NA",
            "sector_fit": "NA",
            "stage_fit": "NA",
            "notes": "NA",
            "researched_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "Failed"
        }

    def _is_company_search(self, name: str) -> bool:
        """Check if the search query is for a company rather than a person."""
        company_indicators = [
            "capital", "ventures", "fund", "partners", "inc", "corp", "llc",
            "ltd", "limited", "group", "holdings", "combinator", "labs"
        ]
        name_lower = name.lower()
        return any(indicator in name_lower for indicator in company_indicators)

    def _enrich_person(self, name: str, company: str, result: Dict[str, Any]):
        """Enrich data for a person."""
        # Search for person info
        person_results = self.search_person(name, company)

        # Find personal LinkedIn profile
        linkedin_url = self.search_linkedin_profile(name, company)
        if linkedin_url:
            result["contact_linkedin_url"] = linkedin_url

        # Search for company info if provided
        if company:
            company_info = self.search_company(company)
            # Get company LinkedIn URL
            if company_info.get("linkedin_url"):
                result["company_linkedin_url"] = company_info["linkedin_url"]
            self._extract_company_info(company_info, result)

        # Use AI to analyze and summarize
        if person_results:
            try:
                ai_enrichment = self.ai_service.enrich_with_summary(
                    {"name": name, "company": company or ""},
                    person_results
                )
                self._merge_ai_enrichment(ai_enrichment, result)
            except Exception as e:
                logger.warning(f"AI enrichment failed: {e}")

        # Extract info from search results
        self._extract_person_info(person_results, result, name, company)

        # Determine contact_type based on findings (Founder, Enabler, or Investor)
        self._determine_contact_type(result, person_results)

    def _enrich_company(self, company_name: str, result: Dict[str, Any]):
        """Enrich data for a company entity."""
        result["full_name"] = "NA"
        result["company"] = company_name

        # Search for company
        company_info = self.search_company(company_name)

        if company_info.get("linkedin_url"):
            result["company_linkedin_url"] = company_info["linkedin_url"]

        # Determine company type - map to Investor for VC firms
        name_lower = company_name.lower()
        if any(x in name_lower for x in ["capital", "ventures", "fund", "partners"]):
            result["contact_type"] = "Investor"
            result["industry"] = "Venture Capital"
        elif "combinator" in name_lower or "accelerator" in name_lower or "labs" in name_lower:
            result["contact_type"] = "Enabler"  # Accelerators are enablers
            result["industry"] = "Venture Capital"
        else:
            result["contact_type"] = "Enabler"  # Default companies to Enabler

        self._extract_company_info(company_info, result)

    def _extract_person_info(self, results: List[Dict], result: Dict[str, Any],
                              name: str, company: str = None):
        """Extract person information from search results."""
        if not results:
            return

        # Look for title patterns
        title_patterns = [
            r"(?:CEO|CTO|CFO|COO|CMO|CPO)",
            r"(?:Chief\s+\w+\s+Officer)",
            r"(?:Founder|Co-Founder|Cofounder)",
            r"(?:Director|Manager|VP|Vice President)",
            r"(?:Partner|Managing Partner)",
            r"(?:Engineer|Developer|Designer)"
        ]

        for res in results:
            snippet = res.get("snippet", "") + " " + res.get("title", "")

            # Try to extract title
            if result["title"] == "NA":
                for pattern in title_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        result["title"] = match.group(0)
                        break

            # Try to extract location
            location_patterns = [
                r"(?:Cairo|Dubai|Riyadh|San Francisco|New York|London|Berlin)[,\s]+(?:Egypt|UAE|KSA|CA|NY|UK|Germany)?",
                r"(?:Egypt|UAE|Saudi Arabia|United States|UK|Germany)"
            ]
            if result["address"] == "NA":
                for pattern in location_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        result["address"] = match.group(0).strip()
                        break

    def _extract_company_info(self, company_info: Dict[str, Any], result: Dict[str, Any]):
        """Extract company information from search results."""
        if not company_info:
            return

        search_results = company_info.get("search_results", [])

        for res in search_results:
            snippet = res.get("snippet", "") + " " + res.get("title", "")
            link = res.get("link", "")

            # Extract website if not already set
            if result["website"] == "NA" and link:
                # Try to extract domain
                domain_match = re.search(r"https?://(?:www\.)?([^/]+)", link)
                if domain_match and "linkedin" not in link and "google" not in link:
                    result["website"] = domain_match.group(1)

            # Look for funding info
            if result["funding_raised"] == "NA":
                funding_match = re.search(r"\$[\d.]+[MBK]?\+?(?:\s*(?:million|billion))?", snippet, re.IGNORECASE)
                if funding_match:
                    result["funding_raised"] = funding_match.group(0)

            # Look for industry keywords
            if result["industry"] == "NA":
                industry_keywords = {
                    "fintech": "Fintech",
                    "artificial intelligence": "Artificial Intelligence",
                    "ai company": "Artificial Intelligence",
                    "healthcare": "Healthcare",
                    "healthtech": "Healthtech",
                    "e-commerce": "E-commerce",
                    "real estate": "Real Estate / Proptech",
                    "proptech": "Real Estate / Proptech",
                    "transportation": "Transportation / Mobility",
                    "mobility": "Transportation / Mobility",
                    "technology": "Technology",
                    "software": "Technology",
                    "retail": "Retail",
                    "banking": "Banking",
                    "consulting": "Consulting"
                }
                snippet_lower = snippet.lower()
                for keyword, industry in industry_keywords.items():
                    if keyword in snippet_lower:
                        result["industry"] = industry
                        break

    def _determine_contact_type(self, result: Dict[str, Any], search_results: List[Dict] = None):
        """
        Determine contact_type as Founder, Enabler, or Investor.

        Classification logic:
        - Founder: Founders, Co-founders, CEOs of startups
        - Investor: VCs, Angels, Partners at investment firms
        - Enabler: Everyone else (executives, consultants, advisors, etc.)
        """
        if result.get("contact_type") not in ["NA", None]:
            # Already set, validate it's one of the three
            if result["contact_type"] not in ["Founder", "Enabler", "Investor"]:
                result["contact_type"] = "Enabler"  # Default invalid values
            return

        title = (result.get("title") or "").lower()
        company = (result.get("company") or "").lower()
        summary = (result.get("linkedin_summary") or "").lower()

        # Combine all text for analysis
        all_text = f"{title} {company} {summary}"
        if search_results:
            for res in search_results:
                all_text += " " + res.get("snippet", "").lower()
                all_text += " " + res.get("title", "").lower()

        # Check for Investor indicators
        investor_keywords = [
            "investor", "venture capital", "vc ", "angel investor",
            "general partner", "managing partner", "partner at",
            "investment", "fund manager", "portfolio"
        ]
        investor_company_keywords = [
            "capital", "ventures", "fund", "investment", "partners"
        ]

        for keyword in investor_keywords:
            if keyword in all_text:
                result["contact_type"] = "Investor"
                return

        for keyword in investor_company_keywords:
            if keyword in company:
                result["contact_type"] = "Investor"
                return

        # Check for Founder indicators
        founder_keywords = [
            "founder", "co-founder", "cofounder", "founding",
            "started", "built", "created the company"
        ]
        founder_titles = [
            "ceo", "chief executive", "cto", "chief technology",
            "coo", "chief operating"
        ]

        for keyword in founder_keywords:
            if keyword in all_text:
                result["contact_type"] = "Founder"
                return

        # CEOs/CTOs of startups are likely founders
        for title_keyword in founder_titles:
            if title_keyword in title:
                # Check if it's a startup context
                startup_indicators = ["startup", "tech", "saas", "ai", "fintech", "healthtech"]
                if any(ind in all_text for ind in startup_indicators):
                    result["contact_type"] = "Founder"
                    return

        # Default to Enabler (executives, advisors, consultants, etc.)
        result["contact_type"] = "Enabler"

    def _merge_ai_enrichment(self, ai_data: Dict[str, Any], result: Dict[str, Any]):
        """Merge AI-generated enrichment data."""
        if not ai_data:
            return

        # Map AI fields to result fields
        field_mapping = {
            "summary": "linkedin_summary",
            "title": "title",
            "company": "company",
            "industry": "industry",
            "location": "address",
            "key_strengths": "key_strengths"
        }

        for ai_field, result_field in field_mapping.items():
            if ai_data.get(ai_field) and result[result_field] == "NA":
                result[result_field] = ai_data[ai_field]

    def _extract_from_linkedin_summary(self, result: Dict[str, Any]):
        """Extract company, industry, and other info from LinkedIn summary."""
        summary = result.get("linkedin_summary", "")
        if not summary or summary == "NA":
            return

        summary_lower = summary.lower()

        # Extract company if missing - look for patterns like "at Company", "of Company", "CEO of Company"
        if result.get("company") == "NA":
            company_patterns = [
                r"(?:CEO|CTO|COO|CFO|CMO|Founder|Co-Founder|Cofounder|Chief \w+ Officer|Director|VP|Head|Manager|Officer)\s+(?:of|at)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\.|,|where|a\s+|the\s+|$)",
                r"(?:works at|working at|joined)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\.|,|as|$)",
                r"(?:founded|co-founded|cofounded)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\.|,|$)",
            ]
            for pattern in company_patterns:
                match = re.search(pattern, summary, re.IGNORECASE)
                if match:
                    company = match.group(1).strip()
                    # Clean up common suffixes
                    company = re.sub(r'\s+(where|a|the|is|was)$', '', company, flags=re.IGNORECASE)
                    if company and len(company) > 1:
                        result["company"] = company
                        break

        # Extract industry based on keywords in summary
        if result.get("industry") == "NA":
            industry_map = {
                "fintech": "Fintech",
                "financial": "Finance",
                "banking": "Banking",
                "insurance": "Insurance",
                "healthtech": "Healthtech",
                "healthcare": "Healthcare",
                "health": "Healthcare",
                "medical": "Healthcare",
                "pharmacy": "Pharmaceutical",
                "pharmaceutical": "Pharmaceutical",
                "edtech": "EdTech",
                "education": "Education",
                "e-commerce": "E-commerce",
                "ecommerce": "E-commerce",
                "retail": "Retail",
                "real estate": "Real Estate",
                "proptech": "Real Estate / Proptech",
                "property": "Real Estate",
                "logistics": "Logistics",
                "supply chain": "Logistics",
                "transportation": "Transportation",
                "mobility": "Transportation / Mobility",
                "ai": "Artificial Intelligence",
                "artificial intelligence": "Artificial Intelligence",
                "machine learning": "Artificial Intelligence",
                "software": "Technology",
                "tech": "Technology",
                "technology": "Technology",
                "saas": "SaaS",
                "cloud": "Cloud Computing",
                "marketing": "Marketing",
                "advertising": "Marketing / Advertising",
                "media": "Media",
                "entertainment": "Media / Entertainment",
                "food": "Food & Beverage",
                "agriculture": "Agriculture",
                "agtech": "AgTech",
                "construction": "Construction",
                "energy": "Energy",
                "cleantech": "CleanTech",
                "consulting": "Consulting",
                "legal": "Legal",
                "hr": "Human Resources",
                "recruitment": "Human Resources",
                "travel": "Travel",
                "hospitality": "Hospitality",
                "gaming": "Gaming",
                "sports": "Sports",
                "fashion": "Fashion",
                "beauty": "Beauty",
                "startup": "Startups",
            }
            for keyword, industry in industry_map.items():
                if keyword in summary_lower:
                    result["industry"] = industry
                    break

        # Extract key strengths from summary
        if result.get("key_strengths") == "NA":
            strength_keywords = [
                "leadership", "strategy", "strategic", "sales", "marketing",
                "operations", "engineering", "product", "growth", "fundraising",
                "partnerships", "business development", "scaling", "technology",
                "innovation", "digital transformation", "analytics", "data"
            ]
            found_strengths = []
            for keyword in strength_keywords:
                if keyword in summary_lower:
                    found_strengths.append(keyword.title())
            if found_strengths:
                result["key_strengths"] = ", ".join(found_strengths[:4])

    def _calculate_enrichment_quality(self, result: Dict[str, Any]):
        """Calculate research quality and status based on filled fields."""
        # Count non-NA fields
        key_fields = ["full_name", "company", "title", "contact_linkedin_url",
                      "company_description", "industry", "contact_type"]
        filled_key_fields = sum(1 for f in key_fields if result.get(f, "NA") != "NA")

        all_filled = sum(1 for v in result.values() if v and v != "NA")

        # Determine quality
        if filled_key_fields >= 5:
            result["research_quality"] = "High"
        elif filled_key_fields >= 3:
            result["research_quality"] = "Medium"
        else:
            result["research_quality"] = "Low"

        # Determine status
        if filled_key_fields >= 4:
            result["status"] = "Enriched"
        elif filled_key_fields >= 2:
            result["status"] = "Partial"
        else:
            result["status"] = "Failed"

    def enrich_contacts_bulk(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enrich multiple contacts in bulk.
        Returns summary and individual results.
        """
        results = {
            "total": len(contacts),
            "enriched": 0,
            "partial": 0,
            "failed": 0,
            "contacts": []
        }

        for contact in contacts:
            name = contact.get("full_name") or contact.get("name", "")
            company = contact.get("company", "")

            if not name:
                continue

            enrichment = self.enrich_contact_comprehensive(name, company)

            if enrichment["status"] == "Enriched":
                results["enriched"] += 1
            elif enrichment["status"] == "Partial":
                results["partial"] += 1
            else:
                results["failed"] += 1

            results["contacts"].append({
                "original": contact,
                "enrichment": enrichment
            })

        return results


# Global service instance
_enrichment_service: Optional[EnrichmentService] = None


def get_enrichment_service() -> EnrichmentService:
    """Get or create enrichment service instance."""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = EnrichmentService()
    return _enrichment_service
