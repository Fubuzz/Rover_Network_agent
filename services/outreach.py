"""
Outreach Agent Service (V02 - Data-First Approach).
Generates personalized email drafts by cross-referencing Matches with Contacts.
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

from config import AIConfig
from data.schema import Draft, ApprovalStatus, SendStatus
from services.google_sheets import get_sheets_service


class OutreachService:
    """Service for drafting and sending outreach emails with data enrichment."""

    def __init__(self):
        self.sheets_service = get_sheets_service()
        self.llm = ChatOpenAI(
            model=AIConfig.OPENAI_MODEL,
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7  # Slightly creative for email writing
        )
        # Email config from environment
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        # Support both naming conventions
        self.sender_name = os.getenv("SENDER_NAME") or os.getenv("SMTP_FROM_NAME", "Ahmed")
        self.sender_email = os.getenv("SENDER_EMAIL") or os.getenv("SMTP_FROM_EMAIL", "")

    def get_high_quality_matches(self, min_score: int = 70) -> List[Dict[str, Any]]:
        """Get matches eligible for drafting."""
        return self.sheets_service.get_high_quality_matches_for_drafting(min_score)

    def enrich_match_with_contacts(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """
        LAZY MODE: Names should already be "baked in" by the Matchmaker.
        Just read them from the Match data. Only fallback to lookup if missing.
        """
        enriched = match.copy()

        # ========================================
        # READ BAKED-IN DATA FROM MATCH
        # (The Matchmaker saved person LinkedIn to Matches sheet)
        # Source columns from Sheet 1:
        #   - contact_linkedin_url -> founder_linkedin / investor_linkedin (in Matches)
        #   - company_linkedin_url -> startup_linkedin / investor_company_linkedin (extracted here for Drafts)
        # ========================================
        founder_name = match.get("founder_name", "")
        investor_name = match.get("investor_name", "")
        founder_linkedin = match.get("founder_linkedin", "")        # Person's LinkedIn (from Match)
        investor_linkedin = match.get("investor_linkedin", "")      # Person's LinkedIn (from Match)

        # Company LinkedIn fields need to be looked up from Contacts (not in Matches)
        startup_linkedin = ""
        investor_company_linkedin = ""

        print(f"[OUTREACH] Reading from Match: {founder_name} -> {investor_name}")

        # ========================================
        # LOOKUP: Get company LinkedIn from Contacts (Sheet 1)
        # Company LinkedIn is NOT in Matches - must be looked up for Drafts
        # Uses get_contact_dict_by_id to access all columns including company_linkedin_url
        # ========================================

        # Lookup Founder contact for company LinkedIn
        founder_contact_id = match.get("founder_contact_id", "")
        if founder_contact_id:
            founder_dict = self.sheets_service.get_contact_dict_by_id(founder_contact_id)
            if founder_dict:
                # Get company LinkedIn from company_linkedin_url column
                startup_linkedin = founder_dict.get("company_linkedin_url", "") or ""
                enriched["startup_description"] = founder_dict.get("company_description", "") or ""
                enriched["startup_milestone"] = founder_dict.get("funding_raised", "") or founder_dict.get("company_stage", "") or ""
                # Fallback for name if missing
                if not founder_name:
                    founder_name = founder_dict.get("full_name", "") or f"{founder_dict.get('first_name', '')} {founder_dict.get('last_name', '')}".strip()
                    founder_linkedin = founder_dict.get("contact_linkedin_url", "") or founder_dict.get("linkedin_url", "") or ""
                print(f"[OUTREACH] Founder lookup: {founder_name}, Company LinkedIn: {bool(startup_linkedin)}")

        # Lookup Investor contact for company LinkedIn
        investor_contact_id = match.get("investor_contact_id", "")
        if investor_contact_id:
            investor_dict = self.sheets_service.get_contact_dict_by_id(investor_contact_id)
            if investor_dict:
                # Get company LinkedIn from company_linkedin_url column
                investor_company_linkedin = investor_dict.get("company_linkedin_url", "") or ""
                # Fallback for name if missing
                if not investor_name:
                    investor_name = investor_dict.get("full_name", "") or f"{investor_dict.get('first_name', '')} {investor_dict.get('last_name', '')}".strip()
                    investor_linkedin = investor_dict.get("contact_linkedin_url", "") or investor_dict.get("linkedin_url", "") or ""
                print(f"[OUTREACH] Investor lookup: {investor_name}, Company LinkedIn: {bool(investor_company_linkedin)}")

        # ========================================
        # UPDATE ENRICHED DATA
        # ========================================
        enriched["founder_name"] = founder_name
        enriched["investor_name"] = investor_name
        enriched["founder_linkedin"] = founder_linkedin          # Person's LinkedIn
        enriched["investor_linkedin"] = investor_linkedin        # Person's LinkedIn
        enriched["startup_linkedin"] = startup_linkedin          # Company LinkedIn
        enriched["investor_company_linkedin"] = investor_company_linkedin  # Company LinkedIn
        enriched["investor_company_name"] = match.get("investor_firm", "")

        # ========================================
        # VALIDATION
        # ========================================
        if not founder_name:
            print(f"[ERROR] Missing founder_name for match {match.get('match_id')}")
            enriched["_skip_draft"] = True
            enriched["_skip_reason"] = "Missing founder name"

        if not investor_name:
            print(f"[ERROR] Missing investor_name for match {match.get('match_id')}")
            enriched["_skip_draft"] = True
            enriched["_skip_reason"] = "Missing investor name"

        return enriched

    def generate_email_draft(self, enriched_match: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate personalized email content using VERIFIED enriched data.
        Uses deterministic template with LLM enhancement.
        """
        # ========================================
        # EXTRACT VERIFIED VARIABLES
        # ========================================
        startup_name = enriched_match.get("startup_name", "the startup")
        investor_firm = enriched_match.get("investor_company_name") or enriched_match.get("investor_firm", "")

        # VERIFIED: These come from the Sheet 1 lookup
        investor_name = enriched_match.get("investor_name", "")
        founder_name = enriched_match.get("founder_name", "")

        # Extract first name for greeting
        recipient_first_name = investor_name.split()[0] if investor_name else "there"

        # LinkedIn and context
        founder_linkedin = enriched_match.get("founder_linkedin", "")
        startup_description = enriched_match.get("startup_description", "")
        startup_milestone = enriched_match.get("startup_milestone", "")
        match_rationale = enriched_match.get("match_rationale", "") or enriched_match.get("primary_match_reason", "")
        recent_news = enriched_match.get("recent_news_hook", "")

        print(f"[DEBUG] Generating email for: {founder_name} -> {investor_name}")
        print(f"[DEBUG] Match rationale: {match_rationale[:50]}..." if match_rationale else "[DEBUG] No match rationale")

        # ========================================
        # BUILD DETERMINISTIC EMAIL (FALLBACK)
        # ========================================
        # This ensures we ALWAYS have a good email even if LLM fails

        # Hook line
        if recent_news and recent_news.strip():
            hook = f"Saw the news about {recent_news} – love the direction."
        else:
            hook = "Hope you're having a great week."

        # Build the email body with VERIFIED variables
        body_lines = [f"Hi {recipient_first_name},", "", hook, ""]

        # Intro with verified names
        intro = f"I wanted to put {startup_name} on your radar. I met {founder_name} recently and immediately thought of you"
        if match_rationale:
            # Extract key reason
            intro += f" because {match_rationale.split('.')[0]}."
        else:
            intro += "."
        body_lines.append(intro)
        body_lines.append("")

        # Pitch (if we have description)
        if startup_description:
            desc_short = startup_description.split('.')[0] + '.' if '.' in startup_description else startup_description
            body_lines.append(desc_short)
            if startup_milestone:
                body_lines.append(f"They recently hit {startup_milestone}.")
            body_lines.append("")

        # Links (only if available - NEVER say NA)
        if founder_linkedin:
            body_lines.append(f"Founder Profile: {founder_linkedin}")
        body_lines.append("")

        # Ask and sign-off
        body_lines.append("Attached is their brief. Worth a double opt-in?")
        body_lines.append("")
        body_lines.append("Best,")
        body_lines.append("Ahmed")

        deterministic_email = "\n".join(body_lines)

        # ========================================
        # TRY LLM ENHANCEMENT (OPTIONAL)
        # ========================================
        try:
            copywriter = Agent(
                role="Elite Venture Scout & Networker",
                goal="Polish introduction emails to be punchy and personal",
                backstory=f"""You are Ahmed's Chief of Staff. You're polishing an email to {recipient_first_name}.
                The email MUST mention {founder_name} (the founder) and {startup_name} (the startup).
                Sign off as 'Ahmed' - NEVER as 'Network Nurturing Agent'.""",
                llm=self.llm,
                verbose=False
            )

            prompt = f"""
            Polish this email to be more punchy and natural. Keep the same structure but improve the flow.

            VERIFIED DATA (USE THESE EXACT NAMES):
            - Recipient: {recipient_first_name} (Investor at {investor_firm})
            - Founder: {founder_name}
            - Startup: {startup_name}
            - Why they match: {match_rationale}

            ORIGINAL EMAIL:
            {deterministic_email}

            RULES:
            - MUST use "{recipient_first_name}" in greeting
            - MUST mention "{founder_name}" by name
            - MUST sign as "Ahmed" (NEVER "Network Nurturing Agent")
            - Keep under 100 words
            - Keep all LinkedIn links exactly as they are

            Return ONLY the polished email text, no JSON.
            """

            task = Task(description=prompt, agent=copywriter, expected_output="Polished email text")
            crew = Crew(agents=[copywriter], tasks=[task], verbose=False)
            result = crew.kickoff()
            polished = str(result).strip()

            # ========================================
            # QUALITY CHECK: Reject bad LLM output
            # ========================================
            is_bad_output = (
                "Network Nurturing Agent" in polished or
                "Hi," in polished and recipient_first_name not in polished or
                founder_name not in polished or
                len(polished) < 50
            )

            if is_bad_output:
                print(f"[WARNING] LLM output rejected, using deterministic email")
                final_body = deterministic_email
            else:
                final_body = polished

        except Exception as e:
            print(f"[WARNING] LLM failed ({e}), using deterministic email")
            final_body = deterministic_email

        return {
            "subject": f"Intro: {startup_name} x {investor_firm}",
            "body": final_body
        }

    def create_drafts_from_matches(self, min_score: int = 70, progress_callback=None) -> Tuple[int, str]:
        """
        Create email drafts using STRICT ID LOOKUP PROTOCOL.
        1. Read Matches (Sheet 2)
        2. LOOKUP: Get names from Contacts (Sheet 1) using IDs
        3. VALIDATE: Skip if names are missing
        4. Generate personalized email with VERIFIED data
        5. Write to Drafts (Sheet 3)
        """
        # Step 0: Validate Drafts sheet schema (fixes column misalignment)
        from data.schema import DRAFT_SHEET_HEADERS
        try:
            drafts_ws = self.sheets_service.get_drafts_worksheet()
            if drafts_ws:
                current_headers = drafts_ws.row_values(1)
                if current_headers != DRAFT_SHEET_HEADERS:
                    print(f"[SCHEMA FIX] Drafts sheet headers mismatch!")
                    print(f"[SCHEMA FIX] Expected: {DRAFT_SHEET_HEADERS}")
                    print(f"[SCHEMA FIX] Found: {current_headers}")
                    print(f"[SCHEMA FIX] Recreating Drafts sheet with correct schema...")
                    if progress_callback:
                        progress_callback("Fixing Drafts sheet schema...")
                    self.sheets_service.clear_drafts(recreate_with_new_headers=True)
        except Exception as e:
            print(f"[WARNING] Could not validate Drafts schema: {e}")

        # Step 1: Get eligible matches from Sheet 2
        matches = self.get_high_quality_matches(min_score)

        if not matches:
            return 0, "No eligible matches found for drafting."

        if progress_callback:
            progress_callback(f"Found {len(matches)} matches to process.")

        drafts_created = 0
        skipped_count = 0
        drafts = []

        for i, match in enumerate(matches):
            match_id = match.get("match_id", "unknown")

            if progress_callback and (i + 1) % 2 == 0:
                progress_callback(f"Processing match {i + 1}/{len(matches)}...")

            try:
                # Step 2: LOOKUP - Enrich with contact details from Sheet 1
                enriched_match = self.enrich_match_with_contacts(match)

                # Step 3: VALIDATE - Skip if missing required data
                if enriched_match.get("_skip_draft"):
                    reason = enriched_match.get("_skip_reason", "Unknown")
                    print(f"[SKIP] Match {match_id}: {reason}")
                    skipped_count += 1
                    continue

                # Final validation
                founder_name = enriched_match.get("founder_name", "")
                investor_name = enriched_match.get("investor_name", "")

                if not founder_name or not investor_name:
                    print(f"[SKIP] Match {match_id}: Missing name after enrichment")
                    skipped_count += 1
                    continue

                # Step 4: Generate email content with VERIFIED enriched data
                email_content = self.generate_email_draft(enriched_match)

                # Step 5: Create Draft object with ALL verified columns
                draft = Draft(
                    match_id=match_id,
                    # VERIFIED Founder info (from Sheet 1 lookup)
                    founder_name=founder_name,
                    founder_email=enriched_match.get("founder_email", ""),
                    # VERIFIED Investor info (from Sheet 1 lookup)
                    investor_name=investor_name,
                    investor_email=enriched_match.get("investor_email", ""),
                    investor_company_name=enriched_match.get("investor_company_name") or enriched_match.get("investor_firm", ""),
                    # Startup info (from Match - baked in by Matchmaker)
                    startup_name=enriched_match.get("startup_name", ""),
                    startup_linkedin=enriched_match.get("startup_linkedin", ""),  # Company LinkedIn (from company_linkedin_url)
                    investor_company_linkedin=enriched_match.get("investor_company_linkedin", ""),  # Company LinkedIn
                    startup_description=enriched_match.get("startup_description", ""),
                    startup_milestone=enriched_match.get("startup_milestone", ""),
                    # Email content
                    email_subject=email_content.get("subject", ""),
                    email_body=email_content.get("body", ""),
                    approval_status=ApprovalStatus.PENDING.value,
                    send_status=SendStatus.DRAFTED.value
                )

                drafts.append(draft)

                # Update match email_status to "Drafted"
                self.sheets_service.update_match_email_status(match_id, "Drafted")

                drafts_created += 1
                print(f"[OK] Draft created for {founder_name} -> {investor_name}")

            except Exception as e:
                print(f"[ERROR] Match {match_id}: {e}")
                skipped_count += 1
                continue

        # Batch save drafts to Sheet 3
        if drafts:
            saved_count = self.sheets_service.add_drafts_batch(drafts)
            drafts_created = saved_count

        summary = f"""
DRAFTING COMPLETE (Strict Lookup V02)

Matches processed: {len(matches)}
Drafts created: {drafts_created}
Skipped (missing data): {skipped_count}

Data Verification:
- Founder names VERIFIED from Contacts (Sheet 1)
- Investor names VERIFIED from Contacts (Sheet 1)
- LinkedIn URLs pulled from Contacts
- Emails use REAL names, not placeholders

Next steps:
1. Open the 'Drafts' sheet in your Google Spreadsheet
2. Verify founder_name and investor_name columns are filled
3. Review email_body for personalization
4. Set 'approval_status' to "APPROVED" for emails ready to send
5. Run /send_approved to send approved emails
"""

        return drafts_created, summary.strip()

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send an email via SMTP."""
        if not self.smtp_user or not self.smtp_password:
            print("SMTP credentials not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email or self.smtp_user}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add body
            msg.attach(MIMEText(body, 'plain'))

            # Connect and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return True

        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_approved_emails(self, progress_callback=None) -> Tuple[int, int, str]:
        """
        Send all approved emails.
        Returns: (sent count, failed count, summary message)
        """
        # Get approved drafts
        approved_drafts = self.sheets_service.get_approved_drafts()

        if not approved_drafts:
            return 0, 0, "No approved emails to send."

        if progress_callback:
            progress_callback(f"Found {len(approved_drafts)} approved emails to send.")

        sent_count = 0
        failed_count = 0

        for i, draft in enumerate(approved_drafts):
            if progress_callback and (i + 1) % 2 == 0:
                progress_callback(f"Sending email {i + 1}/{len(approved_drafts)}...")

            try:
                to_email = draft.get("investor_email", "")
                subject = draft.get("email_subject", "")
                body = draft.get("email_body", "")
                row_number = draft.get("row_number")

                if not to_email or not subject or not body:
                    print(f"Missing email data for draft: {draft.get('draft_id')}")
                    failed_count += 1
                    continue

                # Send the email
                success = self.send_email(to_email, subject, body)

                if success:
                    # Update draft status
                    if row_number:
                        self.sheets_service.update_draft_status(
                            row_number,
                            SendStatus.SENT.value,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    sent_count += 1
                else:
                    if row_number:
                        self.sheets_service.update_draft_status(
                            row_number,
                            SendStatus.FAILED.value,
                            ""
                        )
                    failed_count += 1

            except Exception as e:
                print(f"Error sending email: {e}")
                failed_count += 1
                continue

        summary = f"""
SENDING COMPLETE

Emails sent: {sent_count}
Emails failed: {failed_count}

Check the 'Drafts' sheet for updated status.
"""

        return sent_count, failed_count, summary.strip()

    def get_draft_stats(self) -> Dict[str, int]:
        """Get statistics about drafts."""
        all_drafts = self.sheets_service.get_all_drafts()

        stats = {
            "total": len(all_drafts),
            "pending": 0,
            "approved": 0,
            "sent": 0,
            "failed": 0
        }

        for draft in all_drafts:
            approval = draft.approval_status.upper() if draft.approval_status else ""
            send_status = draft.send_status if draft.send_status else ""

            if approval == "PENDING":
                stats["pending"] += 1
            elif approval in ["APPROVED", "TRUE"]:
                stats["approved"] += 1

            if send_status == "Sent":
                stats["sent"] += 1
            elif send_status == "Failed":
                stats["failed"] += 1

        return stats


# Global service instance
_outreach_service: Optional[OutreachService] = None


def get_outreach_service() -> OutreachService:
    """Get or create Outreach service instance."""
    global _outreach_service
    if _outreach_service is None:
        _outreach_service = OutreachService()
    return _outreach_service


async def run_drafter(min_score: int = 70, progress_callback=None) -> Tuple[int, str]:
    """
    Main entry point for drafting emails.
    Returns: (count of drafts, summary message)
    """
    service = get_outreach_service()
    return service.create_drafts_from_matches(min_score, progress_callback)


async def run_sender(progress_callback=None) -> Tuple[int, int, str]:
    """
    Main entry point for sending approved emails.
    Returns: (sent count, failed count, summary message)
    """
    service = get_outreach_service()
    return service.send_approved_emails(progress_callback)
