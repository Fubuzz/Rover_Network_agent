"""
Daily Digest Service — Morning briefing for Ahmed.

Generates a daily summary of:
- Pending follow-ups (overdue + today + upcoming)
- Decaying relationships (score dropping)
- Suggested introductions
- Network stats
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from services.interaction_tracker import get_interaction_tracker
from services.airtable_service import get_sheets_service

logger = logging.getLogger('network_agent')


def generate_daily_digest(user_id: str) -> str:
    """
    Generate the daily morning digest.
    
    Returns:
        Formatted digest string ready to send via Telegram.
    """
    tracker = get_interaction_tracker()
    sheets = get_sheets_service()
    sheets._ensure_initialized()
    
    today = datetime.now().date()
    sections = []
    
    # Header
    day_name = today.strftime("%A")
    date_str = today.strftime("%B %d, %Y")
    sections.append(f"☀️ **Good morning! Here's your network briefing for {day_name}, {date_str}:**\n")
    
    # --- Follow-ups ---
    follow_ups = tracker.get_pending_follow_ups(user_id)
    # Also check Airtable follow-ups
    airtable_follow_ups = tracker.get_contacts_needing_follow_up(user_id)
    
    overdue = []
    due_today = []
    upcoming = []
    
    for fu in follow_ups:
        try:
            fu_date = datetime.strptime(fu['follow_up_date'], "%Y-%m-%d").date()
            days_diff = (fu_date - today).days
            entry = f"**{fu['contact_name']}**"
            if fu.get('reason'):
                entry += f" — {fu['reason']}"
            
            if days_diff < 0:
                overdue.append((abs(days_diff), entry))
            elif days_diff == 0:
                due_today.append(entry)
            elif days_diff <= 7:
                upcoming.append((days_diff, entry))
        except (ValueError, TypeError):
            continue
    
    # Add Airtable follow-ups not already in SQLite
    sqlite_names = {fu['contact_name'].lower() for fu in follow_ups}
    for contact in airtable_follow_ups:
        if contact.name and contact.name.lower() not in sqlite_names:
            entry = f"**{contact.name}**"
            if contact.follow_up_reason:
                entry += f" — {contact.follow_up_reason}"
            try:
                if len(contact.follow_up_date) <= 10:
                    fu_date = datetime.strptime(contact.follow_up_date, "%Y-%m-%d").date()
                else:
                    fu_date = datetime.strptime(contact.follow_up_date, "%Y-%m-%d %H:%M:%S").date()
                days_diff = (fu_date - today).days
                if days_diff < 0:
                    overdue.append((abs(days_diff), entry))
                elif days_diff == 0:
                    due_today.append(entry)
                elif days_diff <= 7:
                    upcoming.append((days_diff, entry))
            except (ValueError, TypeError):
                continue
    
    if overdue or due_today or upcoming:
        sections.append("📅 **Follow-ups:**")
        if overdue:
            overdue.sort(key=lambda x: -x[0])
            for days, entry in overdue:
                sections.append(f"  🔴 {entry} — {days} days overdue!")
        if due_today:
            for entry in due_today:
                sections.append(f"  🔥 {entry} — TODAY")
        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            for days, entry in upcoming:
                sections.append(f"  📌 {entry} — in {days} day{'s' if days > 1 else ''}")
        sections.append("")
    
    # --- Decaying Relationships ---
    decaying = tracker.get_decaying_relationships(user_id, threshold=40)
    if decaying:
        sections.append("⚠️ **Relationships needing attention:**")
        for contact, score in decaying[:5]:
            last = ""
            if contact.last_interaction_date:
                try:
                    last_dt = datetime.strptime(contact.last_interaction_date, "%Y-%m-%d %H:%M:%S")
                    weeks = (datetime.now() - last_dt).days // 7
                    last = f" — {weeks} weeks since last contact"
                except (ValueError, TypeError):
                    pass
            company = f" ({contact.company})" if contact.company else ""
            sections.append(f"  📉 **{contact.name}**{company} — score: {score}/100{last}")
        sections.append("")
    
    # --- Network Stats ---
    all_contacts = sheets.get_all_contacts()
    total_contacts = len(all_contacts)
    
    # Count by classification
    classifications = {}
    for c in all_contacts:
        ct = c.contact_type or "unclassified"
        classifications[ct] = classifications.get(ct, 0) + 1
    
    # Recent interactions (last 7 days)
    recent_interactions = []
    try:
        import sqlite3
        from config import DATA_DIR
        conn = sqlite3.connect(str(DATA_DIR / "interactions.db"))
        cursor = conn.cursor()
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM interactions WHERE user_id = ? AND timestamp > ?",
            (user_id, week_ago)
        )
        weekly_count = cursor.fetchone()[0]
        conn.close()
    except Exception:
        weekly_count = 0
    
    sections.append(f"📊 **Network Stats:**")
    sections.append(f"  👥 {total_contacts} contacts")
    if classifications:
        cls_str = ", ".join(f"{v} {k}s" for k, v in sorted(classifications.items(), key=lambda x: -x[1])[:4])
        sections.append(f"  📋 {cls_str}")
    sections.append(f"  💬 {weekly_count} interactions this week")
    
    # --- Suggested Actions ---
    actions = []
    if overdue:
        actions.append(f"Follow up with {overdue[0][1].split('**')[1]} (most overdue)")
    if decaying:
        contact, score = decaying[0]
        actions.append(f"Reconnect with {contact.name} (score: {score})")
    
    if actions:
        sections.append("")
        sections.append("💡 **Suggested actions:**")
        for action in actions[:3]:
            sections.append(f"  → {action}")
    
    return "\n".join(sections)


def generate_weekly_report(user_id: str) -> str:
    """Generate a weekly network report."""
    tracker = get_interaction_tracker()
    sheets = get_sheets_service()
    sheets._ensure_initialized()
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    # Get interactions this week
    import sqlite3
    from config import DATA_DIR
    
    conn = sqlite3.connect(str(DATA_DIR / "interactions.db"))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT contact_name, interaction_type, context, timestamp
        FROM interactions
        WHERE user_id = ? AND timestamp > ?
        ORDER BY timestamp DESC
    """, (user_id, week_ago.isoformat()))
    
    interactions = cursor.fetchall()
    
    # Unique contacts interacted with
    cursor.execute("""
        SELECT COUNT(DISTINCT contact_name)
        FROM interactions
        WHERE user_id = ? AND timestamp > ?
    """, (user_id, week_ago.isoformat()))
    
    unique_contacts = cursor.fetchone()[0]
    conn.close()
    
    # Get all contacts for stats
    all_contacts = sheets.get_all_contacts()
    
    # Build report
    sections = [
        f"📊 **Weekly Network Report ({week_ago.strftime('%b %d')} — {today.strftime('%b %d')})**\n",
        f"**Activity:**",
        f"  💬 {len(interactions)} interactions with {unique_contacts} contacts",
    ]
    
    # Interaction breakdown by type
    type_counts = {}
    for _, itype, _, _ in interactions:
        type_counts[itype] = type_counts.get(itype, 0) + 1
    if type_counts:
        types_str = ", ".join(f"{v}x {k}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
        sections.append(f"  📋 {types_str}")
    
    # Top relationships
    sections.append(f"\n**Top Relationships:**")
    scored = []
    for c in all_contacts[:20]:  # Limit to prevent too many API calls
        score = tracker.calculate_relationship_score(c.name)
        scored.append((c, score))
    scored.sort(key=lambda x: -x[1])
    
    for c, score in scored[:5]:
        company = f" ({c.company})" if c.company else ""
        sections.append(f"  🏆 **{c.name}**{company} — {score}/100")
    
    return "\n".join(sections)
