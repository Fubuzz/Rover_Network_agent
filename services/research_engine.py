"""
Deep Research Engine - Multi-Source, Cross-Validated Research.

This engine orchestrates comprehensive research across multiple sources:
1. LinkedIn (personal profiles and company pages)
2. Company websites and about pages
3. News and press releases
4. Funding databases (Crunchbase-style)
5. Social media presence

The engine:
- Runs multiple search strategies in parallel
- Cross-validates data from different sources
- Assigns confidence scores based on source reliability
- Aggregates and deduplicates results
- Returns structured data that maps to Contact fields
"""

import asyncio
import logging
import re
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from config import APIConfig
from data.research_schema import (
    ResearchResult, ResearchRequest, 
    PersonIntelligence, CompanyIntelligence, LinkedInProfile,
    SourcedValue, ConfidenceLevel, DataSource
)


logger = logging.getLogger('research_engine')


class SearchStrategy:
    """Base class for search strategies."""
    
    def __init__(self, tavily_client, ai_service):
        self.tavily = tavily_client
        self.ai = ai_service
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Execute search and return raw results."""
        if not self.tavily:
            return []
        
        try:
            response = self.tavily.search(
                query=query,
                max_results=max_results,
                include_answer=False
            )
            return response.get("results", [])
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
            return []


class LinkedInSearchStrategy(SearchStrategy):
    """Strategy for finding LinkedIn profiles."""
    
    def search_person_profile(self, name: str, company: str = None, 
                              location: str = None) -> Optional[str]:
        """
        Find a person's LinkedIn profile URL with multiple search approaches.
        """
        queries = []
        
        # Strategy 1: Direct LinkedIn search
        base_query = f"site:linkedin.com/in {name}"
        if company:
            queries.append(f"{base_query} {company}")
        queries.append(base_query)
        
        # Strategy 2: Include location if available
        if location:
            queries.append(f"{base_query} {location}")
        
        # Strategy 3: Try with quotes for exact name
        queries.append(f'site:linkedin.com/in "{name}"')
        
        for query in queries:
            results = self.search(query, max_results=5)
            
            for result in results:
                url = result.get("url", "")
                title = result.get("title", "").lower()
                
                # Verify it's a personal profile (/in/) not company
                if "/in/" in url and "/company/" not in url:
                    # Basic name verification
                    name_parts = name.lower().split()
                    if any(part in title for part in name_parts):
                        return url
        
        return None
    
    def search_company_page(self, company_name: str) -> Optional[str]:
        """Find a company's LinkedIn page."""
        queries = [
            f"site:linkedin.com/company {company_name}",
            f'site:linkedin.com/company "{company_name}"',
        ]
        
        for query in queries:
            results = self.search(query, max_results=3)
            
            for result in results:
                url = result.get("url", "")
                if "/company/" in url:
                    return url
        
        return None
    
    def extract_profile_data(self, profile_url: str, name: str) -> LinkedInProfile:
        """
        Extract data from LinkedIn profile search results.
        """
        profile = LinkedInProfile(profile_url=profile_url)
        
        # Search for profile details
        query = f"site:linkedin.com {name} profile"
        results = self.search(query, max_results=5)
        
        for result in results:
            snippet = result.get("content", "") + " " + result.get("title", "")
            url = result.get("url", "")
            
            # Only use results from the same profile
            if profile_url and profile_url not in url:
                continue
            
            # Extract headline/title
            if not profile.headline:
                # Patterns like "John Smith - CEO at Company | LinkedIn"
                headline_match = re.search(
                    rf"{re.escape(name)}\s*[-–|]\s*(.+?)(?:\s*[|]|\s*[-–]\s*LinkedIn|$)", 
                    result.get("title", ""),
                    re.IGNORECASE
                )
                if headline_match:
                    profile.headline = headline_match.group(1).strip()
            
            # Extract current position
            title_patterns = [
                r"(?:currently|now)\s+(?:working\s+as\s+)?(.+?)\s+at\s+(\w[\w\s&]+)",
                r"(\w[\w\s]+)\s+at\s+(\w[\w\s&]+)",
                r"(?:CEO|CTO|CFO|COO|Founder|Co-Founder|VP|Director|Manager|Engineer)\s+(?:of|at)\s+(\w[\w\s&]+)",
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2:
                        profile.current_title = match.group(1).strip()
                        profile.current_company = match.group(2).strip()
                    break
            
            # Extract location
            location_patterns = [
                r"(?:based\s+in|located\s+in|from)\s+([\w\s,]+?)(?:\s*[|.]|$)",
                r"([\w\s]+,\s*(?:Egypt|UAE|KSA|USA|UK|Germany|France|India|Canada))",
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    profile.location = match.group(1).strip()
                    break
            
            # Extract summary/about
            if not profile.summary and len(snippet) > 100:
                # Clean snippet for summary
                clean_snippet = re.sub(r'\s+', ' ', snippet).strip()
                if name.lower() in clean_snippet.lower():
                    profile.summary = clean_snippet[:500]
        
        # Parse headline for title/company if not found
        if profile.headline and not profile.current_title:
            parts = profile.headline.split(" at ")
            if len(parts) >= 2:
                profile.current_title = parts[0].strip()
                profile.current_company = parts[1].split("|")[0].strip()
        
        profile.confidence = ConfidenceLevel.MEDIUM if profile.profile_url else ConfidenceLevel.LOW
        return profile


class CompanySearchStrategy(SearchStrategy):
    """Strategy for researching companies."""
    
    def research_company(self, company_name: str, 
                         context: str = None) -> CompanyIntelligence:
        """
        Comprehensive company research.
        """
        company = CompanyIntelligence(name=company_name)
        
        # Build contextual search query
        context_suffix = ""
        if context:
            context_suffix = f" {context}"
        
        # Strategy 1: General company info
        general_results = self.search(
            f"{company_name} company{context_suffix}", 
            max_results=10
        )
        
        # Strategy 2: Funding/startup info
        funding_results = self.search(
            f"{company_name} funding raised investors startup", 
            max_results=5
        )
        
        # Strategy 3: LinkedIn company page
        linkedin_results = self.search(
            f"site:linkedin.com/company {company_name}", 
            max_results=3
        )
        
        # Strategy 4: News and press
        news_results = self.search(
            f"{company_name} news announcement", 
            max_results=5
        )
        
        # Strategy 5: Company website
        website_results = self.search(
            f"{company_name} official website about", 
            max_results=3
        )
        
        # Process general results
        for result in general_results:
            snippet = result.get("content", "")
            url = result.get("url", "")
            title = result.get("title", "")
            
            # Extract website
            if not company.website:
                # Look for official domain
                domain_match = re.search(
                    r'https?://(?:www\.)?([a-z0-9-]+\.[a-z]{2,})', 
                    url, re.IGNORECASE
                )
                if domain_match:
                    domain = domain_match.group(1).lower()
                    # Exclude social media and search engines
                    excluded = ['linkedin.com', 'twitter.com', 'facebook.com', 
                               'crunchbase.com', 'google.com', 'youtube.com']
                    if not any(ex in domain for ex in excluded):
                        company.website = domain_match.group(0)
            
            # Extract description
            if not company.description and len(snippet) > 50:
                if company_name.lower() in snippet.lower():
                    company.description = snippet[:500]
            
            # Extract industry
            industry_keywords = {
                "fintech": "Fintech",
                "financial technology": "Fintech",
                "healthtech": "Healthtech",
                "healthcare": "Healthcare",
                "e-commerce": "E-commerce",
                "ecommerce": "E-commerce",
                "artificial intelligence": "Artificial Intelligence",
                "ai company": "Artificial Intelligence",
                "machine learning": "AI/ML",
                "saas": "SaaS",
                "software": "Software",
                "proptech": "PropTech",
                "real estate": "Real Estate",
                "edtech": "EdTech",
                "education": "Education",
                "logistics": "Logistics",
                "mobility": "Mobility/Transportation",
                "transportation": "Transportation",
                "cybersecurity": "Cybersecurity",
                "security": "Cybersecurity",
                "biotech": "Biotech",
                "cleantech": "CleanTech",
                "agtech": "AgTech",
                "foodtech": "FoodTech",
                "gaming": "Gaming",
                "media": "Media",
                "entertainment": "Entertainment",
                "hr tech": "HR Tech",
                "recruitment": "HR Tech",
                "marketing": "MarTech",
                "legal tech": "LegalTech",
                "consulting": "Consulting",
                "venture capital": "Venture Capital",
                "investment": "Investment",
            }
            
            if not company.industry:
                snippet_lower = snippet.lower()
                for keyword, industry in industry_keywords.items():
                    if keyword in snippet_lower:
                        company.industry = industry
                        break
        
        # Process funding results
        for result in funding_results:
            snippet = result.get("content", "")
            
            # Extract funding amount
            if not company.total_funding:
                funding_match = re.search(
                    r'(?:raised|funding|secured)\s+\$?([\d.]+)\s*(million|billion|M|B|K)?',
                    snippet, re.IGNORECASE
                )
                if funding_match:
                    amount = funding_match.group(1)
                    unit = (funding_match.group(2) or "").lower()
                    if unit in ['million', 'm']:
                        company.total_funding = f"${amount}M"
                    elif unit in ['billion', 'b']:
                        company.total_funding = f"${amount}B"
                    else:
                        company.total_funding = f"${amount}"
            
            # Extract funding stage
            if not company.funding_stage:
                stage_patterns = [
                    r"(seed|pre-seed)\s*(?:round|funding)?",
                    r"series\s*([a-e])\s*(?:round|funding)?",
                    r"(ipo|public)",
                ]
                for pattern in stage_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        stage = match.group(0).strip().title()
                        company.funding_stage = stage
                        break
            
            # Extract investors
            investor_match = re.search(
                r"(?:led\s+by|from|investors?\s+include)\s+([\w\s,&]+?)(?:\.|,\s*and|$)",
                snippet, re.IGNORECASE
            )
            if investor_match:
                investors = investor_match.group(1).split(",")
                company.investors.extend([i.strip() for i in investors if i.strip()])
        
        # Process LinkedIn results
        for result in linkedin_results:
            url = result.get("url", "")
            snippet = result.get("content", "")
            
            if "/company/" in url and not company.linkedin_url:
                company.linkedin_url = url
            
            # Extract size from LinkedIn
            size_match = re.search(
                r"(\d+[-–]\d+|\d+\+?)\s*employees",
                snippet, re.IGNORECASE
            )
            if size_match and not company.company_size:
                company.company_size = size_match.group(1) + " employees"
        
        # Process news results
        for result in news_results[:3]:
            company.recent_news.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")[:200]
            })
        
        # Extract headquarters/location
        for result in general_results + linkedin_results:
            snippet = result.get("content", "")
            
            if not company.headquarters:
                location_match = re.search(
                    r"(?:headquartered|based|located)\s+in\s+([\w\s,]+?)(?:\.|,|$)",
                    snippet, re.IGNORECASE
                )
                if location_match:
                    company.headquarters = location_match.group(1).strip()
        
        # Determine confidence
        if company.linkedin_url and company.description:
            company.confidence = ConfidenceLevel.HIGH
        elif company.linkedin_url or company.description:
            company.confidence = ConfidenceLevel.MEDIUM
        else:
            company.confidence = ConfidenceLevel.LOW
        
        company.data_freshness = datetime.now().strftime("%Y-%m-%d")
        
        return company


class PersonSearchStrategy(SearchStrategy):
    """Strategy for researching individuals."""
    
    def research_person(self, name: str, company: str = None,
                       known_title: str = None,
                       known_location: str = None) -> PersonIntelligence:
        """
        Comprehensive person research.
        """
        person = PersonIntelligence(full_name=name)
        
        # Split name
        name_parts = name.split()
        if name_parts:
            person.first_name = name_parts[0]
            person.last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
        
        # Build search queries with context
        context_parts = []
        if company:
            context_parts.append(company)
        if known_title:
            context_parts.append(known_title)
        if known_location:
            context_parts.append(known_location)
        context = " ".join(context_parts)
        
        # Strategy 1: General person search
        general_results = self.search(
            f"{name} {context}" if context else name,
            max_results=10
        )
        
        # Strategy 2: Professional profile search
        professional_results = self.search(
            f"{name} {company if company else ''} CEO CTO founder executive",
            max_results=5
        )
        
        # Strategy 3: News mentions
        news_results = self.search(
            f'"{name}" {company if company else ""} news announcement',
            max_results=5
        )
        
        # Process all results
        all_results = general_results + professional_results
        
        for result in all_results:
            snippet = result.get("content", "")
            url = result.get("url", "")
            title = result.get("title", "")
            
            # Extract title/position
            if not person.current_title:
                title_patterns = [
                    rf"{re.escape(name)}.*?(?:is|as|,)\s+(?:the\s+)?(\w[\w\s]+?)\s+(?:at|of)\s+(\w[\w\s&]+)",
                    r"(CEO|CTO|CFO|COO|CMO|CPO|Founder|Co-Founder|President|VP|Vice President|Director|Manager)\s+(?:at|of)\s+(\w[\w\s&]+)",
                ]
                for pattern in title_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        person.current_title = match.group(1).strip()
                        if len(match.groups()) >= 2:
                            person.current_company = person.current_company or match.group(2).strip()
                        break
            
            # Extract location
            if not person.location:
                location_patterns = [
                    r"based\s+in\s+([\w\s,]+?)(?:\.|,|$)",
                    r"from\s+([\w\s,]+?)(?:\.|,|$)",
                    r"(Cairo|Dubai|Riyadh|San Francisco|New York|London|Berlin|Paris|Singapore|Sydney|Toronto|Tel Aviv)[\s,]*([\w\s]*)?",
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        person.location = match.group(0).strip().rstrip('.,')
                        break
            
            # Extract email
            if not person.email:
                email_match = re.search(
                    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                    snippet
                )
                if email_match:
                    person.email = email_match.group(0).lower()
            
            # Extract expertise areas
            expertise_keywords = [
                "artificial intelligence", "machine learning", "fintech",
                "venture capital", "entrepreneurship", "strategy",
                "product management", "engineering", "sales", "marketing",
                "operations", "growth", "fundraising", "leadership"
            ]
            snippet_lower = snippet.lower()
            for keyword in expertise_keywords:
                if keyword in snippet_lower and keyword not in person.expertise_areas:
                    person.expertise_areas.append(keyword.title())
        
        # Determine contact type
        person.contact_type = self._classify_contact_type(person, all_results)
        
        # Determine seniority
        person.seniority = self._determine_seniority(person.current_title)
        
        # Generate professional summary
        if not person.professional_summary and general_results:
            # Use first meaningful snippet as summary
            for result in general_results:
                snippet = result.get("content", "")
                if name.lower() in snippet.lower() and len(snippet) > 100:
                    person.professional_summary = snippet[:500]
                    break
        
        # Process news mentions
        for result in news_results[:3]:
            person.recent_mentions.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "date": datetime.now().strftime("%Y-%m-%d")
            })
        
        # Set company if known
        if company and not person.current_company:
            person.current_company = company
        
        # Confidence
        if person.current_title and person.current_company:
            person.confidence = ConfidenceLevel.MEDIUM
        elif person.current_title or person.current_company:
            person.confidence = ConfidenceLevel.LOW
        else:
            person.confidence = ConfidenceLevel.UNVERIFIED
        
        return person
    
    def _classify_contact_type(self, person: PersonIntelligence, 
                               results: List[Dict]) -> str:
        """Classify person as Founder, Investor, or Enabler."""
        title = (person.current_title or "").lower()
        company = (person.current_company or "").lower()
        
        all_text = title + " " + company
        for r in results:
            all_text += " " + r.get("content", "").lower()
        
        # Check for Investor
        investor_signals = [
            "investor", "venture capital", "vc ", "angel investor",
            "general partner", "managing partner", "partner at",
            "investment fund", "portfolio"
        ]
        investor_company_signals = [
            "capital", "ventures", "fund", "investment", "partners"
        ]
        
        for signal in investor_signals:
            if signal in all_text:
                return "Investor"
        for signal in investor_company_signals:
            if signal in company:
                return "Investor"
        
        # Check for Founder
        founder_signals = [
            "founder", "co-founder", "cofounder", "founding",
            "started", "built the company", "launched"
        ]
        founder_titles = ["ceo", "chief executive", "cto", "coo"]
        
        for signal in founder_signals:
            if signal in all_text:
                return "Founder"
        
        # CEOs at startups are often founders
        for t in founder_titles:
            if t in title:
                startup_signals = ["startup", "tech", "saas", "fintech"]
                if any(s in all_text for s in startup_signals):
                    return "Founder"
        
        # Default to Enabler
        return "Enabler"
    
    def _determine_seniority(self, title: str) -> str:
        """Determine seniority level from title."""
        if not title:
            return "Unknown"
        
        title_lower = title.lower()
        
        if any(t in title_lower for t in ["ceo", "cto", "cfo", "coo", "cmo", "cpo", "chief"]):
            return "C-Level"
        if any(t in title_lower for t in ["founder", "co-founder", "president", "owner"]):
            return "Founder/Executive"
        if any(t in title_lower for t in ["vp", "vice president", "svp", "evp"]):
            return "VP"
        if "director" in title_lower:
            return "Director"
        if any(t in title_lower for t in ["manager", "head of", "lead"]):
            return "Manager"
        if any(t in title_lower for t in ["senior", "sr.", "sr "]):
            return "Senior IC"
        
        return "IC"


class DeepResearchEngine:
    """
    Main research engine that orchestrates all search strategies.
    """
    
    def __init__(self):
        self._tavily_client = None
        self._ai_service = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of clients."""
        if self._initialized:
            return
        
        # Initialize Tavily
        try:
            from tavily import TavilyClient
            if APIConfig.TAVILY_API_KEY:
                self._tavily_client = TavilyClient(api_key=APIConfig.TAVILY_API_KEY)
                logger.info("Tavily client initialized for research engine")
        except Exception as e:
            logger.error(f"Failed to initialize Tavily: {e}")
        
        # Initialize AI service
        try:
            from services.ai_service import get_ai_service
            self._ai_service = get_ai_service()
        except Exception as e:
            logger.error(f"Failed to initialize AI service: {e}")
        
        self._initialized = True
    
    def research(self, request: ResearchRequest) -> ResearchResult:
        """
        Execute comprehensive research for a contact.
        
        This is the main entry point that:
        1. Runs multiple search strategies
        2. Cross-validates data
        3. Aggregates results
        4. Returns structured output
        """
        self._initialize()
        
        start_time = time.time()
        
        result = ResearchResult(
            search_query=f"{request.name} {request.company or ''}".strip()
        )
        
        if not self._tavily_client:
            result.warnings.append("Search service unavailable - no Tavily API key")
            return result
        
        logger.info(f"Starting deep research for: {request.name} (company: {request.company})")
        
        # Initialize strategies
        linkedin_strategy = LinkedInSearchStrategy(self._tavily_client, self._ai_service)
        company_strategy = CompanySearchStrategy(self._tavily_client, self._ai_service)
        person_strategy = PersonSearchStrategy(self._tavily_client, self._ai_service)
        
        sources_consulted = 0
        
        # 1. LinkedIn Profile Search
        logger.info("Phase 1: LinkedIn profile search...")
        linkedin_url = linkedin_strategy.search_person_profile(
            request.name,
            request.company,
            request.known_location
        )
        
        if linkedin_url:
            result.linkedin_profile = linkedin_strategy.extract_profile_data(
                linkedin_url, request.name
            )
            result.field_mappings["linkedin_url"] = SourcedValue(
                value=linkedin_url,
                confidence=ConfidenceLevel.HIGH,
                source=DataSource.LINKEDIN_PROFILE,
                source_url=linkedin_url
            )
            sources_consulted += 1
        else:
            result.warnings.append(f"Could not find LinkedIn profile for {request.name}")
        
        # 2. Person Research
        logger.info("Phase 2: Person intelligence research...")
        result.person = person_strategy.research_person(
            request.name,
            request.company,
            request.known_title,
            request.known_location
        )
        sources_consulted += 1
        
        # 3. Company Research (if company known or found)
        company_name = request.company or (result.person and result.person.current_company)
        
        if company_name and not request.skip_company_research:
            logger.info(f"Phase 3: Company intelligence research for {company_name}...")
            
            # Search for company LinkedIn
            company_linkedin = linkedin_strategy.search_company_page(company_name)
            
            # Research company
            result.company = company_strategy.research_company(
                company_name,
                context=request.known_location
            )
            
            if company_linkedin:
                result.company.linkedin_url = company_linkedin
                result.field_mappings["company_linkedin_url"] = SourcedValue(
                    value=company_linkedin,
                    confidence=ConfidenceLevel.HIGH,
                    source=DataSource.LINKEDIN_COMPANY,
                    source_url=company_linkedin
                )
            
            sources_consulted += 1
        
        # 4. Cross-validate and enrich
        logger.info("Phase 4: Cross-validation and enrichment...")
        self._cross_validate(result)
        
        # 5. Build field mappings
        self._build_field_mappings(result)
        
        # 6. Calculate metrics
        result.sources_consulted = sources_consulted
        result.research_duration_seconds = time.time() - start_time
        result.calculate_completeness()
        
        # Determine overall confidence
        if result.completeness_score >= 0.7:
            result.overall_confidence = ConfidenceLevel.HIGH
        elif result.completeness_score >= 0.4:
            result.overall_confidence = ConfidenceLevel.MEDIUM
        else:
            result.overall_confidence = ConfidenceLevel.LOW
        
        logger.info(
            f"Research complete for {request.name}: "
            f"completeness={result.completeness_score:.0%}, "
            f"confidence={result.overall_confidence.value}, "
            f"duration={result.research_duration_seconds:.1f}s"
        )
        
        return result
    
    def _cross_validate(self, result: ResearchResult):
        """Cross-validate data from multiple sources."""
        # Validate title consistency
        titles = []
        if result.person and result.person.current_title:
            titles.append(result.person.current_title)
        if result.linkedin_profile and result.linkedin_profile.current_title:
            titles.append(result.linkedin_profile.current_title)
        
        if len(titles) >= 2:
            # Check if titles match
            if titles[0].lower() != titles[1].lower():
                result.warnings.append(
                    f"Title mismatch: '{titles[0]}' vs '{titles[1]}'"
                )
                # Prefer LinkedIn title
                if result.linkedin_profile and result.linkedin_profile.current_title:
                    result.person.current_title = result.linkedin_profile.current_title
            else:
                result.accuracy_indicators.append("Title confirmed from multiple sources")
        
        # Validate company consistency
        companies = []
        if result.person and result.person.current_company:
            companies.append(result.person.current_company)
        if result.linkedin_profile and result.linkedin_profile.current_company:
            companies.append(result.linkedin_profile.current_company)
        if result.company and result.company.name:
            companies.append(result.company.name)
        
        if len(companies) >= 2:
            # Basic fuzzy match
            base_company = companies[0].lower()
            if all(base_company in c.lower() or c.lower() in base_company for c in companies):
                result.accuracy_indicators.append("Company confirmed from multiple sources")
            else:
                result.warnings.append(f"Company variations found: {', '.join(companies)}")
        
        # Enrich person with LinkedIn data
        if result.linkedin_profile:
            if not result.person:
                result.person = PersonIntelligence(full_name=result.search_query.split()[0])
            
            if result.linkedin_profile.current_title and not result.person.current_title:
                result.person.current_title = result.linkedin_profile.current_title
            if result.linkedin_profile.current_company and not result.person.current_company:
                result.person.current_company = result.linkedin_profile.current_company
            if result.linkedin_profile.location and not result.person.location:
                result.person.location = result.linkedin_profile.location
            if result.linkedin_profile.summary and not result.person.professional_summary:
                result.person.professional_summary = result.linkedin_profile.summary
    
    def _build_field_mappings(self, result: ResearchResult):
        """Build structured field mappings for agent consumption."""
        # Title
        if result.person and result.person.current_title:
            confidence = ConfidenceLevel.HIGH if "Title confirmed" in str(result.accuracy_indicators) else ConfidenceLevel.MEDIUM
            result.field_mappings["title"] = SourcedValue(
                value=result.person.current_title,
                confidence=confidence,
                source=DataSource.LINKEDIN_PROFILE if result.linkedin_profile else DataSource.GOOGLE_SEARCH
            )
        
        # Company
        if result.person and result.person.current_company:
            result.field_mappings["company"] = SourcedValue(
                value=result.person.current_company,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.GOOGLE_SEARCH
            )
        
        # Location
        location = None
        if result.person and result.person.location:
            location = result.person.location
        elif result.company and result.company.headquarters:
            location = result.company.headquarters
        
        if location:
            result.field_mappings["address"] = SourcedValue(
                value=location,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.GOOGLE_SEARCH
            )
        
        # Contact type
        if result.person and result.person.contact_type:
            result.field_mappings["contact_type"] = SourcedValue(
                value=result.person.contact_type,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.AI_INFERENCE
            )
        
        # Industry
        if result.company and result.company.industry:
            result.field_mappings["industry"] = SourcedValue(
                value=result.company.industry,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.GOOGLE_SEARCH
            )
        
        # Company description
        if result.company and result.company.description:
            result.field_mappings["company_description"] = SourcedValue(
                value=result.company.description[:500],
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.COMPANY_WEBSITE if result.company.website else DataSource.GOOGLE_SEARCH
            )
        
        # Funding info
        if result.company and result.company.funding_stage:
            result.field_mappings["company_stage"] = SourcedValue(
                value=result.company.funding_stage,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.NEWS_ARTICLE
            )
        
        if result.company and result.company.total_funding:
            result.field_mappings["funding_raised"] = SourcedValue(
                value=result.company.total_funding,
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.NEWS_ARTICLE
            )
        
        # Website
        if result.company and result.company.website:
            result.field_mappings["website"] = SourcedValue(
                value=result.company.website,
                confidence=ConfidenceLevel.HIGH,
                source=DataSource.GOOGLE_SEARCH
            )
        
        # Summary
        if result.person and result.person.professional_summary:
            result.field_mappings["linkedin_summary"] = SourcedValue(
                value=result.person.professional_summary[:500],
                confidence=ConfidenceLevel.MEDIUM,
                source=DataSource.LINKEDIN_PROFILE if result.linkedin_profile else DataSource.GOOGLE_SEARCH
            )
        
        # Key strengths
        if result.person and result.person.expertise_areas:
            result.field_mappings["key_strengths"] = SourcedValue(
                value=", ".join(result.person.expertise_areas[:5]),
                confidence=ConfidenceLevel.LOW,
                source=DataSource.AI_INFERENCE
            )
    
    def quick_linkedin_search(self, name: str, company: str = None) -> Optional[str]:
        """Quick LinkedIn-only search for fast results."""
        self._initialize()
        
        if not self._tavily_client:
            return None
        
        strategy = LinkedInSearchStrategy(self._tavily_client, self._ai_service)
        return strategy.search_person_profile(name, company)
    
    def quick_company_search(self, company_name: str) -> Optional[CompanyIntelligence]:
        """Quick company-only search."""
        self._initialize()
        
        if not self._tavily_client:
            return None
        
        strategy = CompanySearchStrategy(self._tavily_client, self._ai_service)
        return strategy.research_company(company_name)


# Global instance
_research_engine: Optional[DeepResearchEngine] = None


def get_research_engine() -> DeepResearchEngine:
    """Get or create the research engine instance."""
    global _research_engine
    if _research_engine is None:
        _research_engine = DeepResearchEngine()
    return _research_engine
