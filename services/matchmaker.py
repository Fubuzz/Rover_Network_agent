"""
Matchmaker Agent Service.
Matches Founders with Investors based on sector fit, stage alignment, geo alignment, and thesis alignment.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

from config import AIConfig
from data.schema import Match, StageAlignment, IntroAngle, ToneInstruction, EmailStatus
from services.airtable_service import get_sheets_service


class MatchmakerService:
    """Service for matching Founders with Investors."""

    # Negation prefixes that invalidate a keyword match
    _NEGATION_PREFIXES = ["no ", "not ", "non-", "lack of ", "without ", "unlikely "]

    def __init__(self):
        self.sheets_service = get_sheets_service()
        # Use gpt-4o-mini for faster matching with 128k context window
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.3
        )

    def get_contacts_for_matching(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get founders and investors from the contacts sheet."""
        return self.sheets_service.get_founders_and_investors()

    @staticmethod
    def _has_positive_keyword(text: str, keyword: str) -> bool:
        """Check if keyword appears in text without being negated."""
        idx = text.find(keyword)
        if idx == -1:
            return False
        # Check if preceded by a negation
        prefix = text[max(0, idx - 12):idx].lower()
        negations = ["no ", "not ", "non-", "lack of ", "without ", "unlikely "]
        return not any(prefix.endswith(neg) for neg in negations)

    def _any_positive_keyword(self, text: str, keywords: list) -> bool:
        """Check if any keyword matches positively (not negated) in text."""
        return any(self._has_positive_keyword(text, kw) for kw in keywords)

    def calculate_match_score(
        self,
        founder: Dict[str, Any],
        investor: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> int:
        """Calculate match score (0-100) based on analysis factors.

        Scoring is MORE LENIENT to catch good matches.
        Keywords checked in order of strength.
        Negated keywords (e.g. "not strong") are excluded.
        """
        score = 0

        # Sector Fit (0-30 points) - More lenient keywords
        sector_fit = analysis.get("sector_fit", "").lower()
        if self._any_positive_keyword(sector_fit, ["strong", "exact", "direct", "perfect", "excellent", "high"]):
            score += 30
        elif self._any_positive_keyword(sector_fit, ["partial", "adjacent", "related", "good", "moderate", "overlap"]):
            score += 20
        elif self._any_positive_keyword(sector_fit, ["possible", "potential", "some", "limited", "tangential"]):
            score += 10
        elif sector_fit and "weak" not in sector_fit and "none" not in sector_fit:
            score += 15  # Default non-negative response

        # Stage Alignment (0-25 points)
        stage_alignment = analysis.get("stage_alignment", "").lower()
        if self._any_positive_keyword(stage_alignment, ["exact", "perfect", "ideal", "match", "fits"]):
            score += 25
        elif self._any_positive_keyword(stage_alignment, ["typical", "within range", "close", "good", "appropriate"]):
            score += 20
        elif self._any_positive_keyword(stage_alignment, ["adjacent", "sometimes", "possible", "flexible"]):
            score += 10
        elif stage_alignment and "outside" not in stage_alignment and "mismatch" not in stage_alignment:
            score += 12  # Default non-negative response

        # Geo Alignment (0-20 points)
        geo_alignment = analysis.get("geo_alignment", "").lower()
        if self._any_positive_keyword(geo_alignment, ["local", "same", "both", "shared"]):
            score += 20
        elif self._any_positive_keyword(geo_alignment, ["regional", "nearby", "close", "mena", "middle east"]):
            score += 15
        elif self._any_positive_keyword(geo_alignment, ["remote", "global", "international", "flexible"]):
            score += 10
        elif geo_alignment and "no " not in geo_alignment:
            score += 8  # Default

        # Thesis Alignment (0-25 points)
        thesis_alignment = analysis.get("thesis_alignment", "").lower()
        if self._any_positive_keyword(thesis_alignment, ["strong", "direct", "perfect", "excellent", "high"]):
            score += 25
        elif self._any_positive_keyword(thesis_alignment, ["partial", "related", "good", "moderate", "aligned"]):
            score += 15
        elif self._any_positive_keyword(thesis_alignment, ["tangential", "indirect", "possible", "potential"]):
            score += 8
        elif thesis_alignment and "weak" not in thesis_alignment and "none" not in thesis_alignment:
            score += 10  # Default

        return min(score, 100)

    def determine_stage_alignment(self, founder: Dict, investor: Dict) -> str:
        """Determine stage alignment category."""
        founder_stage = founder.get("startup_stage", "").lower()
        investor_focus = investor.get("notes", "").lower() + investor.get("industry", "").lower()

        if any(s in founder_stage for s in ["seed", "pre-seed"]):
            if any(s in investor_focus for s in ["seed", "early", "angel"]):
                return StageAlignment.MATCH.value
        elif any(s in founder_stage for s in ["series a", "series b"]):
            if any(s in investor_focus for s in ["series", "growth", "venture"]):
                return StageAlignment.MATCH.value
            else:
                return StageAlignment.REACH.value

        return StageAlignment.SAFETY.value

    def create_match_from_analysis(
        self,
        founder: Dict[str, Any],
        investor: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Match:
        """Create a Match object from founder, investor, and analysis data."""
        score = self.calculate_match_score(founder, investor, analysis)

        # Map intro_angle from analysis to enum value
        intro_angle_map = {
            "sector": IntroAngle.THESIS.value,
            "stage": IntroAngle.MOMENTUM.value,
            "mutual_connection": IntroAngle.MUTUAL.value,
            "warm_referral": IntroAngle.MUTUAL.value,
            "flattery": IntroAngle.FLATTERY.value,
            "data": IntroAngle.HARD_DATA.value
        }
        raw_angle = analysis.get("intro_angle", "thesis").lower()
        intro_angle = intro_angle_map.get(raw_angle, IntroAngle.THESIS.value)

        # Check for anti-portfolio conflict
        anti_conflict = analysis.get("anti_portfolio_conflict", "None found")
        has_conflict = anti_conflict.lower() not in ["none found", "none", "no", ""]

        # ========================================
        # BAKE IN: Extract names and LinkedIn URLs from Contacts
        # This saves the Outreach agent from having to look them up
        # ========================================
        # Source columns in Sheet 1:
        #   - contact_linkedin_url: Person's LinkedIn profile -> founder_linkedin / investor_linkedin
        #   - company_linkedin_url: Company's LinkedIn page -> goes to Drafts sheet (not Matches)

        # Founder details (from Contacts row)
        founder_linkedin = (
            founder.get("contact_linkedin_url") or
            founder.get("linkedin_url") or
            founder.get("linkedin_link", "")
        )
        founder_name = founder.get("full_name") or f"{founder.get('first_name', '')} {founder.get('last_name', '')}".strip()

        # Investor details (from Contacts row)
        investor_linkedin = (
            investor.get("contact_linkedin_url") or
            investor.get("linkedin_url") or
            investor.get("linkedin_link", "")
        )
        investor_name = investor.get("full_name") or f"{investor.get('first_name', '')} {investor.get('last_name', '')}".strip()

        print(f"[MATCHMAKER] Baking in: {founder_name} -> {investor_name}")
        print(f"[MATCHMAKER] LinkedIn - Founder: {founder_linkedin[:30] if founder_linkedin else 'None'}...")

        # Use Airtable record ID (row_number) for linked records, not custom contact_id
        # The row_number contains the actual "recXXX" ID needed for linked record fields
        founder_record_id = founder.get("row_number") or founder.get("contact_id", "")
        investor_record_id = investor.get("row_number") or investor.get("contact_id", "")

        # FIX: Validate startup_name - ensure we get company name, not industry
        startup_name = founder.get("company", "")
        industry_keywords = ["fintech", "ai", "saas", "healthtech", "edtech", "biotech",
                            "cleantech", "proptech", "insurtech", "regtech", "agtech",
                            "medtech", "martech", "adtech", "legaltech", "govtech",
                            "technology", "software", "hardware", "services", "consulting"]
        if startup_name and startup_name.lower() in industry_keywords:
            # Wrong field grabbed - this is an industry, not a company name
            # Try to use the full_name + "Company" as fallback
            print(f"[MATCHMAKER WARNING] '{startup_name}' looks like an industry, not a company name")
            startup_name = f"{founder_name}'s Startup"  # Fallback

        match = Match(
            founder_contact_id=founder_record_id,
            investor_contact_id=investor_record_id,
            founder_email=founder.get("email", ""),
            founder_linkedin=founder_linkedin,           # Person's LinkedIn (from contact_linkedin_url)
            founder_name=founder_name,
            startup_name=startup_name,
            investor_email=investor.get("email", ""),
            investor_firm=investor.get("company", ""),
            investor_name=investor_name,
            investor_linkedin=investor_linkedin,         # Person's LinkedIn (from contact_linkedin_url)
            match_score=score,
            primary_match_reason=analysis.get("sector_fit", ""),
            match_rationale=analysis.get("intro_blurb", ""),
            thesis_alignment_notes=analysis.get("thesis_alignment", ""),
            portfolio_synergy=analysis.get("portfolio_synergy", ""),
            anti_portfolio_flag=has_conflict,
            sector_overlap=analysis.get("sector_fit", ""),
            stage_alignment=self.determine_stage_alignment(founder, investor),
            geo_alignment=analysis.get("geo_alignment", "Unknown"),
            intro_angle=intro_angle,
            suggested_subject_line=f"Intro: {founder.get('company', 'Startup')} x {investor.get('company', 'Investor')}",
            recent_news_hook=analysis.get("recent_news_hook", ""),
            tone_instruction=ToneInstruction.WARM.value,
            email_status=EmailStatus.DRAFTED.value
        )

        return match

    def run_matching(self, progress_callback=None) -> Tuple[List[Match], str]:
        """
        Run the full matching process.
        Returns: (list of matches, summary report)
        """
        # Get contacts
        contacts = self.get_contacts_for_matching()
        founders = contacts["founders"]
        investors = contacts["investors"]

        if not founders:
            return [], "No founders found in contacts."
        if not investors:
            return [], "No investors found in contacts."

        if progress_callback:
            progress_callback(f"Found {len(founders)} founders and {len(investors)} investors.")

        # Create the matching crew
        matches = []
        total_pairs = len(founders) * len(investors)
        processed = 0

        # Create the analyst agent
        analyst = Agent(
            role="Investment Match Analyst",
            goal="Analyze founder-investor pairs to determine compatibility and match quality",
            backstory="""You are an expert investment analyst who specializes in
            matching startups with the right investors. You understand venture capital
            thesis alignment, sector expertise, stage preferences, and geographic considerations.
            You provide concise, actionable insights.""",
            llm=self.llm,
            verbose=False
        )

        for founder in founders:
            for investor in investors:
                processed += 1

                if progress_callback and processed % 5 == 0:
                    progress_callback(f"Analyzing pair {processed}/{total_pairs}...")

                try:
                    # Create analysis task
                    analysis_prompt = f"""
                    Analyze this founder-investor match:

                    FOUNDER:
                    - Name: {founder.get('full_name', 'Unknown')}
                    - Company: {founder.get('company', 'Unknown')}
                    - Industry: {founder.get('industry', 'Unknown')}
                    - Stage: {founder.get('startup_stage', 'Unknown')}
                    - Location: {founder.get('address', 'Unknown')}
                    - Notes: {founder.get('notes', '')}

                    INVESTOR:
                    - Name: {investor.get('full_name', 'Unknown')}
                    - Firm: {investor.get('company', 'Unknown')}
                    - Focus Areas: {investor.get('industry', 'Unknown')}
                    - Location: {investor.get('address', 'Unknown')}
                    - Notes: {investor.get('notes', '')}

                    Provide your analysis in this exact JSON format:
                    {{
                        "sector_fit": "Description of sector alignment (Strong/Partial/Weak)",
                        "stage_alignment": "Description of stage match (Exact/Typical/Sometimes/Outside)",
                        "geo_alignment": "Description of geographic fit (Local/Regional/Remote)",
                        "thesis_alignment": "Description of thesis match (Strong/Partial/Tangential)",
                        "anti_portfolio_conflict": "Any known conflicts or 'None found'",
                        "intro_angle": "Best angle for introduction (sector/stage/mutual_connection/warm_referral)",
                        "intro_blurb": "2-3 sentence introduction pitch for this specific match"
                    }}

                    Return ONLY the JSON object, no other text.
                    """

                    task = Task(
                        description=analysis_prompt,
                        agent=analyst,
                        expected_output="JSON object with match analysis"
                    )

                    crew = Crew(
                        agents=[analyst],
                        tasks=[task],
                        verbose=False
                    )

                    result = crew.kickoff()

                    # Parse the analysis result
                    try:
                        result_str = str(result)
                        # Extract JSON from result
                        if "{" in result_str and "}" in result_str:
                            json_start = result_str.find("{")
                            json_end = result_str.rfind("}") + 1
                            json_str = result_str[json_start:json_end]
                            analysis = json.loads(json_str)
                        else:
                            analysis = {
                                "sector_fit": "Unable to analyze",
                                "stage_alignment": "Unable to analyze",
                                "geo_alignment": "Unable to analyze",
                                "thesis_alignment": "Unable to analyze",
                                "anti_portfolio_conflict": "None found",
                                "intro_angle": "thesis",
                                "intro_blurb": f"Introducing {founder.get('full_name', 'founder')} to {investor.get('full_name', 'investor')}."
                            }
                    except json.JSONDecodeError:
                        analysis = {
                            "sector_fit": "Unable to parse",
                            "stage_alignment": "Unable to parse",
                            "geo_alignment": "Unable to parse",
                            "thesis_alignment": "Unable to parse",
                            "anti_portfolio_conflict": "None found",
                            "intro_angle": "thesis",
                            "intro_blurb": f"Introducing {founder.get('full_name', 'founder')} to {investor.get('full_name', 'investor')}."
                        }

                    # Create match
                    match = self.create_match_from_analysis(founder, investor, analysis)

                    # Debug: Log score for every pair
                    print(f"[MATCHMAKER] Score: {match.match_score}/100 for {founder.get('full_name', 'Unknown')} -> {investor.get('full_name', 'Unknown')}")
                    print(f"[MATCHMAKER]   Analysis: sector={analysis.get('sector_fit', 'N/A')[:30]}, stage={analysis.get('stage_alignment', 'N/A')[:30]}")

                    # Only include matches with score >= 50
                    if match.match_score >= 50:
                        matches.append(match)
                    else:
                        print(f"[MATCHMAKER]   Skipped (below threshold)")

                except Exception as e:
                    print(f"Error analyzing pair: {e}")
                    continue

        # Sort matches by score (highest first)
        matches.sort(key=lambda m: m.match_score, reverse=True)

        # Generate summary
        summary = self._generate_summary(founders, investors, matches)

        return matches, summary

    def _generate_summary(
        self,
        founders: List[Dict],
        investors: List[Dict],
        matches: List[Match]
    ) -> str:
        """Generate a summary report of the matching results."""
        total_pairs = len(founders) * len(investors)
        high_quality = len([m for m in matches if m.match_score >= 80])
        medium_quality = len([m for m in matches if 50 <= m.match_score < 80])

        summary = f"""
MATCHMAKER REPORT

Contacts Analyzed:
- Founders: {len(founders)}
- Investors: {len(investors)}
- Total pairs evaluated: {total_pairs}

Results:
- High-quality matches (80+): {high_quality}
- Medium-quality matches (50-79): {medium_quality}
- Total matches saved: {len(matches)}

Top Matches:
"""
        for i, match in enumerate(matches[:5], 1):
            summary += f"""
{i}. {match.startup_name or 'Unknown Startup'} ↔ {match.investor_firm or 'Unknown Firm'}
   Score: {match.match_score}/100
   Sector: {match.sector_overlap or 'Unknown'}
"""

        return summary.strip()

    def save_matches_to_sheet(self, matches: List[Match]) -> int:
        """Save matches to the Matches sheet. Returns count saved."""
        if not matches:
            return 0

        # Clear existing matches
        self.sheets_service.clear_matches()

        # Add new matches
        count = self.sheets_service.add_matches_batch(matches)
        return count


# Global service instance
_matchmaker_service: Optional[MatchmakerService] = None


def get_matchmaker_service() -> MatchmakerService:
    """Get or create Matchmaker service instance."""
    global _matchmaker_service
    if _matchmaker_service is None:
        _matchmaker_service = MatchmakerService()
    return _matchmaker_service


async def run_matchmaker(progress_callback=None) -> Tuple[List[Match], str]:
    """
    Main entry point for running the matchmaker.
    Returns: (list of matches, summary report)
    """
    service = get_matchmaker_service()

    # Run matching
    matches, summary = service.run_matching(progress_callback)

    # Save to sheet
    if matches:
        saved_count = service.save_matches_to_sheet(matches)
        summary += f"\n\nSaved {saved_count} matches to 'Matches' sheet."

    return matches, summary
