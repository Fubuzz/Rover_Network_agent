"""
Direct outreach pipeline — parse NL request, filter contacts, generate emails, save drafts.

This is separate from the match-based outreach in services/outreach.py.
Drafts are saved to the same Airtable Drafts table and flow through the
existing PENDING → APPROVED → /send_approved pipeline.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import openai

from config import AIConfig
from data.schema import Draft, ApprovalStatus, SendStatus
from services.airtable_service import get_sheets_service

logger = logging.getLogger("network_agent")

# ---------------------------------------------------------------------------
# 1. Parse natural-language outreach request into structured criteria
# ---------------------------------------------------------------------------

def parse_outreach_request(natural_language: str) -> dict:
    """
    Use GPT to parse a natural-language outreach request into structured criteria.

    Returns:
        {
            "filter_criteria": {"contact_type": "investor", "industry": "fintech", "address": "egypt"},
            "purpose": "set up a meeting to discuss partnership",
            "date_range": "March 5-12",
            "tone": "warm"
        }
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=AIConfig.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured outreach parameters from a natural-language request.\n"
                    "Return ONLY valid JSON with these keys:\n"
                    "- filter_criteria: object with any of {contact_type, industry, address, company} (lowercase values)\n"
                    "- purpose: string describing why the user wants to reach out\n"
                    "- date_range: string with meeting dates if mentioned, else null\n"
                    "- tone: one of warm, formal, urgent (default warm)\n\n"
                    "Valid contact_type values: investor, founder, enabler, professional.\n"
                    "Put location/country/city into address.\n"
                    "Return ONLY the JSON object, no markdown."
                ),
            },
            {"role": "user", "content": natural_language},
        ],
        temperature=0,
        max_tokens=300,
    )

    raw = (response.choices[0].message.content or "").strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"[OUTREACH] Could not parse GPT response: {raw}")
        return {
            "filter_criteria": {},
            "purpose": natural_language,
            "date_range": None,
            "tone": "warm",
        }


# ---------------------------------------------------------------------------
# 2. Generate a single personalized outreach email
# ---------------------------------------------------------------------------

def generate_outreach_email(
    contact,
    purpose: str,
    date_range: Optional[str] = None,
    sender_name: str = "Ahmed",
    tone: str = "warm",
) -> Dict[str, str]:
    """
    Generate a personalized email for one contact.

    Returns:
        {"subject": "...", "body": "..."}
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build context about the contact
    details = []
    if contact.name:
        details.append(f"Name: {contact.name}")
    if contact.title:
        details.append(f"Title: {contact.title}")
    if contact.company:
        details.append(f"Company: {contact.company}")
    if contact.industry:
        details.append(f"Industry: {contact.industry}")
    if contact.address:
        details.append(f"Location: {contact.address}")
    contact_block = "\n".join(details)

    date_str = f" Available dates: {date_range}." if date_range else ""
    tone_instruction = {
        "warm": "Use a warm, friendly tone. Be natural, not corporate.",
        "formal": "Use a professional, formal tone.",
        "urgent": "Convey a sense of urgency while staying polite.",
    }.get(tone, "Use a warm, friendly tone.")

    response = client.chat.completions.create(
        model=AIConfig.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are {sender_name}, founder of Synapse Analytics "
                    f"(AI credit decisioning for risk teams). "
                    f"Draft a short, personalized email. Keep under 80 words. "
                    f"{tone_instruction} Sign off as {sender_name}.\n"
                    f"Return ONLY valid JSON with keys 'subject' and 'body'. No markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write an email to this person.\n"
                    f"Purpose: {purpose}.{date_str}\n\n"
                    f"Contact:\n{contact_block}"
                ),
            },
        ],
        temperature=0.7,
        max_tokens=400,
    )

    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat the whole response as the body
        return {"subject": f"Meeting request — {sender_name}", "body": raw}


# ---------------------------------------------------------------------------
# 2b. GPT-based fallback filter (when Airtable formula misses)
# ---------------------------------------------------------------------------

def _llm_filter_contacts(sheets, contacts_query: str) -> list:
    """
    Use GPT to pick matching contacts from the full list.
    This handles fuzzy cases where the Airtable formula filter misses
    (e.g. address='Cairo' doesn't match query 'Egypt').
    """
    all_contacts = sheets.get_all_contacts()
    if not all_contacts:
        return []

    # Build compact summaries for the LLM
    summaries = []
    for c in all_contacts:
        parts = [c.name or "Unknown"]
        if c.title:
            parts.append(c.title)
        if c.company:
            parts.append(f"at {c.company}")
        if c.contact_type:
            parts.append(f"[{c.contact_type}]")
        if c.industry:
            parts.append(f"({c.industry})")
        if c.address:
            parts.append(f"in {c.address}")
        if c.email:
            parts.append(f"<{c.email}>")
        summaries.append(" | ".join(parts))

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        resp = client.chat.completions.create(
            model=AIConfig.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return matching contact names as a JSON array. "
                        "Only include contacts that genuinely match the query. "
                        "Return ONLY valid JSON, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Contacts:\n{chr(10).join(summaries)}\n\n"
                        f"Query: {contacts_query}\n\n"
                        "Return matching names as JSON array:"
                    ),
                },
            ],
            temperature=0,
            max_tokens=500,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        names = json.loads(raw)

        matched = []
        for name in names:
            contact = sheets.get_contact_by_name(name)
            if contact:
                matched.append(contact)
        return matched

    except Exception as e:
        logger.warning(f"[OUTREACH] LLM filter fallback failed: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. Main orchestrator: parse → filter → generate → save drafts
# ---------------------------------------------------------------------------

def create_outreach_drafts(
    contacts_query: str,
    purpose: str,
    date_range: Optional[str] = None,
    filter_criteria: Optional[dict] = None,
) -> Tuple[int, str, List[dict]]:
    """
    End-to-end direct outreach pipeline.

    Args:
        contacts_query: Natural-language description of recipients
        purpose: Why the user wants to reach out
        date_range: Optional meeting date window
        filter_criteria: Pre-parsed filter dict (skips NL parsing if provided)

    Returns:
        (count_created, summary_text, previews_list)
    """
    sheets = get_sheets_service()
    sheets._ensure_initialized()

    sender_name = os.getenv("SENDER_NAME") or os.getenv("SMTP_FROM_NAME", "Ahmed")

    # --- Step 1: Parse criteria (if not already provided) ---
    if filter_criteria:
        parsed = {
            "filter_criteria": filter_criteria,
            "purpose": purpose,
            "date_range": date_range,
            "tone": "warm",
        }
    else:
        # Build a combined NL string for the parser
        nl_text = contacts_query
        if purpose:
            nl_text += f". Purpose: {purpose}"
        if date_range:
            nl_text += f". Dates: {date_range}"
        parsed = parse_outreach_request(nl_text)

    criteria = parsed.get("filter_criteria", {})
    effective_purpose = parsed.get("purpose", purpose) or purpose
    effective_dates = parsed.get("date_range", date_range) or date_range
    tone = parsed.get("tone", "warm")

    # --- Step 2: Filter contacts ---
    contacts = []
    if criteria:
        contacts = sheets.filter_contacts(criteria)

    # Fallback: if formula filter found nothing, use GPT to match from full list
    if not contacts:
        contacts = _llm_filter_contacts(sheets, contacts_query)

    if not contacts:
        return 0, f"No contacts found matching: {contacts_query}", []

    # --- Step 3: Generate emails & build Draft objects ---
    drafts: List[Draft] = []
    previews: List[dict] = []
    skipped_no_email: List[str] = []

    for contact in contacts:
        if not contact.email:
            skipped_no_email.append(contact.name)
            continue

        email = generate_outreach_email(
            contact,
            purpose=effective_purpose,
            date_range=effective_dates,
            sender_name=sender_name,
            tone=tone,
        )

        draft = Draft(
            match_id="DIRECT_OUTREACH",
            founder_name=sender_name,
            founder_email=os.getenv("SENDER_EMAIL") or os.getenv("SMTP_FROM_EMAIL", ""),
            investor_name=contact.name,
            investor_email=contact.email,
            investor_company_name=contact.company or "",
            startup_name="Synapse Analytics",
            startup_description=effective_purpose,
            startup_milestone=effective_dates or "",
            email_subject=email.get("subject", ""),
            email_body=email.get("body", ""),
            approval_status=ApprovalStatus.PENDING.value,
            send_status=SendStatus.DRAFTED.value,
        )
        drafts.append(draft)
        previews.append({
            "to": contact.name,
            "email": contact.email,
            "subject": email.get("subject", ""),
            "body_preview": (email.get("body", ""))[:120] + "..."
            if len(email.get("body", "")) > 120
            else email.get("body", ""),
        })

    # --- Step 4: Save to Airtable ---
    saved = 0
    if drafts:
        saved = sheets.add_drafts_batch(drafts)

    # --- Step 5: Build summary ---
    summary_parts = [f"Created {saved} draft(s) for direct outreach."]
    if criteria:
        summary_parts.append(f"Filter: {criteria}")
    summary_parts.append(f"Purpose: {effective_purpose}")
    if effective_dates:
        summary_parts.append(f"Dates: {effective_dates}")
    if skipped_no_email:
        summary_parts.append(
            f"Skipped {len(skipped_no_email)} contact(s) without email: "
            + ", ".join(skipped_no_email)
        )
    summary_parts.append(
        "Drafts saved as PENDING. Review in Airtable, set to APPROVED, "
        "then run /send_approved."
    )

    return saved, "\n".join(summary_parts), previews
