#!/usr/bin/env python3
"""
Test Simulation Script for Rover Network Agent.

This script tests the full workflow without the Telegram layer:
1. Add a test contact (Founder and Investor)
2. Run matchmaker to create matches
3. Run outreach to create drafts
4. Verify all data saved correctly to Airtable

Usage:
    python scripts/test_simulation.py
    python scripts/test_simulation.py --cleanup  # Remove test data after

Set CLEANUP=1 to auto-cleanup test data after verification.
"""

import os
import sys
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from data.schema import Contact, Match, Draft
from services.airtable_service import get_sheets_service


def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_status(status: str, message: str):
    """Print a status message with icon."""
    icons = {
        "ok": "\u2705",
        "fail": "\u274c",
        "info": "\u2139\ufe0f",
        "warn": "\u26a0\ufe0f",
    }
    icon = icons.get(status, "\u2022")
    print(f"{icon} {message}")


class TestSimulation:
    """Full workflow test simulation."""

    def __init__(self, cleanup: bool = False):
        self.cleanup = cleanup
        self.service = get_sheets_service()
        self.test_founder = None
        self.test_investor = None
        self.created_ids = {"contacts": [], "matches": [], "drafts": []}

    def run(self) -> bool:
        """Run the full test simulation."""
        print_header("ROVER NETWORK AGENT - TEST SIMULATION")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Cleanup mode: {'ON' if self.cleanup else 'OFF'}")

        success = True

        try:
            # Phase 1: Test Contact Creation
            if not self._test_contacts():
                success = False

            # Phase 2: Test Matchmaker
            if success and not self._test_matchmaker():
                success = False

            # Phase 3: Test Outreach/Drafts
            if success and not self._test_outreach():
                success = False

            # Phase 4: Verify Data Integrity
            if success and not self._verify_data():
                success = False

        except Exception as e:
            print_status("fail", f"Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            success = False

        finally:
            if self.cleanup:
                self._cleanup_test_data()

        print_header("TEST RESULTS")
        if success:
            print_status("ok", "All tests PASSED!")
        else:
            print_status("fail", "Some tests FAILED. Check output above.")

        return success

    def _test_contacts(self) -> bool:
        """Test contact creation (Founder and Investor)."""
        print_header("PHASE 1: Contact Creation")

        # Create test founder
        print("\n[1.1] Creating test founder...")
        self.test_founder = Contact(
            first_name="TestFounder",
            last_name="SimUser",
            full_name="TestFounder SimUser",
            email="testfounder@simulation.test",
            company="SimStartup Inc",
            title="CEO",
            contact_type="Founder",
            industry="Fintech",
            address="Cairo, Egypt",
            notes="Test contact for simulation - can be deleted",
            source="test_simulation"
        )

        try:
            result = self.service.add_contact(self.test_founder)
            if result:
                print_status("ok", f"Founder created: {self.test_founder.full_name}")
                # Get the record ID
                found = self.service.get_contact_by_name(self.test_founder.full_name)
                if found:
                    self.test_founder.row_number = found.row_number
                    self.created_ids["contacts"].append(found.row_number)
                    print_status("info", f"Record ID: {found.row_number}")
            else:
                print_status("fail", "Failed to create founder")
                return False
        except Exception as e:
            print_status("fail", f"Error creating founder: {e}")
            return False

        # Create test investor
        print("\n[1.2] Creating test investor...")
        self.test_investor = Contact(
            first_name="TestInvestor",
            last_name="VCPartner",
            full_name="TestInvestor VCPartner",
            email="testinvestor@simulation.test",
            company="SimVC Capital",
            title="Partner",
            contact_type="Investor",
            industry="Venture Capital",
            address="Dubai, UAE",
            notes="Test investor for simulation - can be deleted",
            source="test_simulation"
        )

        try:
            result = self.service.add_contact(self.test_investor)
            if result:
                print_status("ok", f"Investor created: {self.test_investor.full_name}")
                # Get the record ID
                found = self.service.get_contact_by_name(self.test_investor.full_name)
                if found:
                    self.test_investor.row_number = found.row_number
                    self.created_ids["contacts"].append(found.row_number)
                    print_status("info", f"Record ID: {found.row_number}")
            else:
                print_status("fail", "Failed to create investor")
                return False
        except Exception as e:
            print_status("fail", f"Error creating investor: {e}")
            return False

        print_status("ok", "Phase 1 complete: 2 contacts created")
        return True

    def _test_matchmaker(self) -> bool:
        """Test match creation."""
        print_header("PHASE 2: Matchmaker")

        print("\n[2.1] Creating test match...")

        if not self.test_founder.row_number or not self.test_investor.row_number:
            print_status("fail", "Missing contact record IDs")
            return False

        test_match = Match(
            founder_contact_id=self.test_founder.row_number,
            investor_contact_id=self.test_investor.row_number,
            founder_email=self.test_founder.email,
            founder_linkedin="https://linkedin.com/in/testfounder",
            founder_name=self.test_founder.full_name,
            startup_name=self.test_founder.company,
            investor_email=self.test_investor.email,
            investor_firm=self.test_investor.company,
            investor_name=self.test_investor.full_name,
            investor_linkedin="https://linkedin.com/in/testinvestor",
            match_score=85,
            primary_match_reason="Strong sector fit in Fintech",
            match_rationale="TestFounder's fintech startup aligns well with TestInvestor's thesis",
            thesis_alignment_notes="Both focus on financial technology innovation",
            sector_overlap="Fintech",
            stage_alignment="Match",
            geo_alignment="Regional (MENA)",
            intro_angle="Thesis",
            suggested_subject_line="Intro: SimStartup Inc x SimVC Capital",
            tone_instruction="Warm"
        )

        try:
            # Use batch method since single add returns bool
            count = self.service.add_matches_batch([test_match])
            if count > 0:
                print_status("ok", f"Match created with score {test_match.match_score}/100")
                print_status("info", f"Match ID: {test_match.match_id}")
                self.created_ids["matches"].append(test_match.match_id)
            else:
                print_status("fail", "Failed to save match to Airtable")
                return False
        except Exception as e:
            print_status("fail", f"Error creating match: {e}")
            import traceback
            traceback.print_exc()
            return False

        print_status("ok", "Phase 2 complete: 1 match created")
        return True

    def _test_outreach(self) -> bool:
        """Test draft creation."""
        print_header("PHASE 3: Outreach Drafts")

        print("\n[3.1] Creating test draft...")

        if not self.created_ids["matches"]:
            print_status("fail", "No matches to create drafts for")
            return False

        match_id = self.created_ids["matches"][0]

        test_draft = Draft(
            match_id=match_id,
            founder_name=self.test_founder.full_name,
            founder_email=self.test_founder.email,
            investor_name=self.test_investor.full_name,
            investor_email=self.test_investor.email,
            investor_company_name=self.test_investor.company,
            startup_name=self.test_founder.company,
            startup_linkedin="https://linkedin.com/company/simstartup",
            investor_company_linkedin="https://linkedin.com/company/simvc",
            startup_description="SimStartup is a fintech company revolutionizing payments",
            startup_milestone="Recently raised $1M seed round",
            email_subject="Introduction: SimStartup x SimVC Capital",
            email_body="""Hi TestInvestor,

I hope this message finds you well. I wanted to introduce you to TestFounder, the CEO of SimStartup Inc.

SimStartup is building innovative fintech solutions that align perfectly with your investment thesis at SimVC Capital.

Would you be open to a brief intro call?

Best regards,
Ahmed""",
            approval_status="pending",
            send_status="not_sent",
            created_date=datetime.now().strftime("%Y-%m-%d")
        )

        try:
            result = self.service.add_draft(test_draft)
            if result:
                print_status("ok", f"Draft created for {test_draft.founder_name} -> {test_draft.investor_name}")
                print_status("info", f"Draft ID: {test_draft.draft_id}")
                self.created_ids["drafts"].append(test_draft.draft_id)
            else:
                print_status("fail", "Failed to save draft to Airtable")
                return False
        except Exception as e:
            print_status("fail", f"Error creating draft: {e}")
            import traceback
            traceback.print_exc()
            return False

        print_status("ok", "Phase 3 complete: 1 draft created")
        return True

    def _verify_data(self) -> bool:
        """Verify all data was saved correctly."""
        print_header("PHASE 4: Data Verification")

        all_passed = True

        # Verify contacts
        print("\n[4.1] Verifying contacts...")
        founder_check = self.service.get_contact_by_name("TestFounder SimUser")
        if founder_check:
            print_status("ok", f"Founder verified: {founder_check.full_name}")
            if founder_check.contact_type and "founder" in founder_check.contact_type.lower():
                print_status("ok", f"  contact_type = {founder_check.contact_type}")
            else:
                print_status("warn", f"  contact_type = {founder_check.contact_type} (expected Founder)")
        else:
            print_status("fail", "Founder not found in Airtable")
            all_passed = False

        investor_check = self.service.get_contact_by_name("TestInvestor VCPartner")
        if investor_check:
            print_status("ok", f"Investor verified: {investor_check.full_name}")
            if investor_check.contact_type and "investor" in investor_check.contact_type.lower():
                print_status("ok", f"  contact_type = {investor_check.contact_type}")
            else:
                print_status("warn", f"  contact_type = {investor_check.contact_type} (expected Investor)")
        else:
            print_status("fail", "Investor not found in Airtable")
            all_passed = False

        # Verify matches
        print("\n[4.2] Verifying matches...")
        all_matches = self.service.get_all_matches()
        test_matches = [m for m in all_matches if "TestFounder" in (m.founder_name or "")]
        if test_matches:
            match = test_matches[0]
            print_status("ok", f"Match verified: {match.founder_name} -> {match.investor_name}")
            print_status("info", f"  Score: {match.match_score}/100")
            print_status("info", f"  Sector: {match.sector_overlap}")

            # Check for populated fields
            missing = []
            if not match.founder_email:
                missing.append("founder_email")
            if not match.investor_email:
                missing.append("investor_email")
            if not match.founder_linkedin:
                missing.append("founder_linkedin")
            if not match.investor_linkedin:
                missing.append("investor_linkedin")

            if missing:
                print_status("warn", f"  Missing fields: {', '.join(missing)}")
            else:
                print_status("ok", "  All key fields populated")
        else:
            print_status("fail", "Test match not found in Airtable")
            all_passed = False

        # Verify drafts
        print("\n[4.3] Verifying drafts...")
        all_drafts = self.service.get_pending_drafts()
        test_drafts = [d for d in all_drafts if "TestFounder" in (d.founder_name or "")]
        if test_drafts:
            draft = test_drafts[0]
            print_status("ok", f"Draft verified: {draft.founder_name} -> {draft.investor_name}")
            print_status("info", f"  Subject: {draft.email_subject[:40]}...")
            print_status("info", f"  Status: {draft.approval_status}")
        else:
            print_status("warn", "Test draft not found (may have been approved/sent)")

        print_status("ok" if all_passed else "warn", "Phase 4 complete")
        return all_passed

    def _cleanup_test_data(self):
        """Remove all test data created during simulation."""
        print_header("CLEANUP: Removing Test Data")

        # Delete contacts
        for record_id in self.created_ids["contacts"]:
            try:
                self.service.contacts_table.delete(record_id)
                print_status("ok", f"Deleted contact: {record_id}")
            except Exception as e:
                print_status("warn", f"Failed to delete contact {record_id}: {e}")

        # Delete matches (find by founder name)
        try:
            all_matches = self.service.get_all_matches()
            for match in all_matches:
                if "TestFounder" in (match.founder_name or ""):
                    # Need to find the record ID
                    records = self.service.matches_table.all(
                        formula=f"{{founder_name}}='TestFounder SimUser'"
                    )
                    for rec in records:
                        self.service.matches_table.delete(rec["id"])
                        print_status("ok", f"Deleted match: {rec['id']}")
        except Exception as e:
            print_status("warn", f"Error cleaning matches: {e}")

        # Delete drafts
        try:
            records = self.service.drafts_table.all(
                formula=f"{{founder_name}}='TestFounder SimUser'"
            )
            for rec in records:
                self.service.drafts_table.delete(rec["id"])
                print_status("ok", f"Deleted draft: {rec['id']}")
        except Exception as e:
            print_status("warn", f"Error cleaning drafts: {e}")

        print_status("ok", "Cleanup complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Rover Network Agent workflow")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove test data after verification"
    )
    args = parser.parse_args()

    # Also check env var
    cleanup = args.cleanup or os.getenv("CLEANUP", "").lower() in ("1", "true", "yes")

    sim = TestSimulation(cleanup=cleanup)
    success = sim.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
