"""
Message formatting utilities for Telegram output.
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from data.schema import Contact


def format_contact_card(contact: Dict) -> str:
    """Format contact data as a readable card for Telegram - Donna style."""
    lines = []
    
    # Classification emoji
    classification = contact.get("classification", "").lower()
    class_emoji = {
        "founder": "🚀",
        "investor": "💰",
        "enabler": "🌟",
        "professional": "💼"
    }.get(classification, "👤")
    
    # Header
    name = contact.get("name", "Unknown")
    if classification:
        lines.append(f"{class_emoji} **{name}** _[{classification.upper()}]_")
    else:
        lines.append(f"👤 **{name}**")
    
    lines.append("─" * 20)
    
    # Job info
    job_title = contact.get("job_title")
    company = contact.get("company")
    if job_title and company:
        lines.append(f"💼 **{job_title}** @ {company}")
    elif job_title:
        lines.append(f"💼 {job_title}")
    elif company:
        lines.append(f"🏢 {company}")
    
    # Contact info with emojis
    if contact.get("email"):
        lines.append(f"📧 {contact['email']}")
    
    if contact.get("phone"):
        lines.append(f"📱 {contact['phone']}")
    
    if contact.get("linkedin_url"):
        lines.append(f"🔗 {contact['linkedin_url']}")
    
    if contact.get("location"):
        lines.append(f"📍 {contact['location']}")
    
    # Tags
    tags = contact.get("tags")
    if tags:
        if isinstance(tags, list):
            tags = ", ".join(tags)
        lines.append(f"🏷️ {tags}")
    
    # Notes
    if contact.get("notes"):
        lines.append("")
        lines.append(f"📝 _{contact['notes']}_")
    
    # Metadata with style
    lines.append("")
    meta = []
    if contact.get("last_contacted"):
        meta.append(f"Last seen: {contact['last_contacted']}")
    if contact.get("source"):
        meta.append(f"Via: {contact['source']}")
    if meta:
        lines.append(f"_({' • '.join(meta)})_")
    
    return "\n".join(lines)


def format_contact_list(contacts: List[Dict], page: int = 1, page_size: int = 10) -> str:
    """Format a list of contacts for Telegram."""
    if not contacts:
        return "No contacts found."
    
    total = len(contacts)
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    page_contacts = contacts[start:end]
    
    lines = [f"**Contacts** (showing {start + 1}-{end} of {total})"]
    lines.append("")
    
    for i, contact in enumerate(page_contacts, start=start + 1):
        name = contact.get("name", "Unknown")
        company = contact.get("company", "")
        classification = contact.get("classification", "")
        
        entry = f"{i}. **{name}**"
        if company:
            entry += f" @ {company}"
        if classification:
            entry += f" [{classification}]"
        
        lines.append(entry)
    
    if total > page_size:
        total_pages = (total + page_size - 1) // page_size
        lines.append("")
        lines.append(f"Page {page}/{total_pages}")
    
    return "\n".join(lines)


def format_statistics(stats: Dict) -> str:
    """Format statistics for Telegram - Donna style."""
    total = stats.get('total', 0)
    
    # Witty opener based on network size
    if total == 0:
        opener = "_Your network is... nonexistent. We should fix that._"
    elif total < 10:
        opener = "_A cozy little network. Quality over quantity, right?_"
    elif total < 50:
        opener = "_Nice network you've got there._"
    elif total < 100:
        opener = "_Impressive. You actually know people._"
    else:
        opener = "_Look at you, Mr./Ms. Popular._"
    
    lines = [
        "**📊 Network Stats**",
        "",
        opener,
        "",
        f"👥 **Total Contacts:** {total}",
        ""
    ]
    
    # By classification with emojis
    by_classification = stats.get("by_classification", {})
    if by_classification:
        lines.append("**By Type:**")
        class_emoji = {"founder": "🚀", "investor": "💰", "enabler": "🌟", "professional": "💼"}
        for classification, count in sorted(by_classification.items()):
            emoji = class_emoji.get(classification.lower(), "👤")
            lines.append(f"  {emoji} {classification.title()}: **{count}**")
        lines.append("")
    
    # By company
    by_company = stats.get("by_company", {})
    if by_company:
        lines.append("**Top Companies:** 🏢")
        for company, count in sorted(by_company.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  • {company}: {count}")
        lines.append("")
    
    # By location
    by_location = stats.get("by_location", {})
    if by_location:
        lines.append("**Top Locations:** 🌍")
        for location, count in sorted(by_location.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  • {location}: {count}")
    
    return "\n".join(lines)


def format_analytics_report(analytics: Dict) -> str:
    """Format analytics data for Telegram."""
    lines = ["**Analytics Dashboard**", ""]
    
    # Operations
    ops = analytics.get("operations", {})
    if ops:
        lines.append("**Operations:**")
        lines.append(f"  - Total: {ops.get('total', 0)}")
        lines.append(f"  - Successful: {ops.get('success', 0)}")
        lines.append(f"  - Failed: {ops.get('failure', 0)}")
        success_rate = ops.get('success_rate', 0)
        lines.append(f"  - Success Rate: {success_rate:.1%}")
        lines.append("")
    
    # Performance
    perf = analytics.get("performance", {})
    if perf:
        lines.append("**Performance:**")
        lines.append(f"  - Avg Response Time: {perf.get('avg_duration_ms', 0):.0f}ms")
        lines.append(f"  - Max Response Time: {perf.get('max_duration_ms', 0):.0f}ms")
        lines.append("")
    
    # Feature usage
    features = analytics.get("features", {})
    if features:
        lines.append("**Top Features:**")
        for feature, count in sorted(features.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  - {feature}: {count} uses")
        lines.append("")
    
    # Recent errors
    errors = analytics.get("recent_errors", [])
    if errors:
        lines.append("**Recent Errors:**")
        for error in errors[:3]:
            lines.append(f"  - {error.get('error_type', 'Unknown')}: {error.get('error_message', '')[:50]}")
    
    return "\n".join(lines)


def format_evaluation_report(evaluation: Dict) -> str:
    """Format evaluation data for Telegram."""
    lines = ["**Evaluation Report**", ""]
    
    # Data quality
    quality = evaluation.get("data_quality", {})
    if quality:
        lines.append("**Data Quality:**")
        lines.append(f"  - Completeness: {quality.get('completeness', 0):.1%}")
        lines.append(f"  - Accuracy: {quality.get('accuracy', 0):.1%}")
        lines.append(f"  - Valid Emails: {quality.get('valid_emails', 0)}/{quality.get('total_emails', 0)}")
        lines.append(f"  - Valid Phones: {quality.get('valid_phones', 0)}/{quality.get('total_phones', 0)}")
        lines.append("")
    
    # Operations evaluation
    ops_eval = evaluation.get("operations", {})
    if ops_eval:
        lines.append("**Operations Evaluation:**")
        lines.append(f"  - Success Rate: {ops_eval.get('success_rate', 0):.1%}")
        lines.append(f"  - Avg Duration: {ops_eval.get('avg_duration_ms', 0):.0f}ms")
        lines.append(f"  - Error Rate: {ops_eval.get('error_rate', 0):.1%}")
        lines.append("")
    
    # Agent performance
    agents = evaluation.get("agents", {})
    if agents:
        lines.append("**Agent Performance:**")
        for agent, metrics in agents.items():
            lines.append(f"  - {agent}: {metrics.get('success_rate', 0):.1%} success")
    
    return "\n".join(lines)


def format_dashboard(data: Dict) -> str:
    """Format real-time dashboard for Telegram."""
    lines = ["**Real-Time Dashboard**", ""]
    
    # Status
    status = data.get("status", "unknown")
    status_emoji = "" if status == "healthy" else "" if status == "warning" else ""
    lines.append(f"**System Status:** {status_emoji} {status.upper()}")
    lines.append("")
    
    # Quick stats
    lines.append("**Quick Stats:**")
    lines.append(f"  - Total Contacts: {data.get('total_contacts', 0)}")
    lines.append(f"  - Operations Today: {data.get('operations_today', 0)}")
    lines.append(f"  - Success Rate: {data.get('success_rate', 0):.1%}")
    lines.append("")
    
    # Recent activity
    recent = data.get("recent_activity", [])
    if recent:
        lines.append("**Recent Activity:**")
        for activity in recent[:5]:
            lines.append(f"  - {activity}")
    
    # Last updated
    lines.append("")
    lines.append(f"_Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    
    return "\n".join(lines)


def format_error_message(error: str, details: Optional[str] = None) -> str:
    """Format error message for Telegram - Donna style."""
    witty_responses = [
        "Well, that didn't go as planned. 🙃",
        "Oops. Even I have off moments. 😅",
        "That's not supposed to happen. Let me fix this. 🔧",
        "Something went sideways. Working on it. 🛠️",
    ]
    import random
    opener = random.choice(witty_responses)
    
    lines = [opener, "", f"**What went wrong:** {error}"]
    
    if details:
        lines.append(f"_Details: {details}_")
    
    lines.append("")
    lines.append("_Try again? I promise I'll do better._ 💪")
    
    return "\n".join(lines)


def format_success_message(message: str, details: Optional[Dict] = None) -> str:
    """Format success message for Telegram - Donna style."""
    witty_closers = [
        "_You're welcome._ 💅",
        "_Another job well done._ ✨",
        "_I'm just that good._ 😏",
        "_Was there ever any doubt?_ 💁‍♀️",
    ]
    import random
    closer = random.choice(witty_closers)
    
    lines = [f"✅ **{message}**"]
    
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"  • {key}: {value}")
    
    lines.append("")
    lines.append(closer)
    
    return "\n".join(lines)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def contact_draft_card(contact: "Contact") -> str:
    """Format a Contact being edited as a draft display card."""
    from data.schema import Contact  # noqa: F811 — runtime import to avoid circular

    lines = []

    name = contact.name
    if name:
        lines.append(f"**{name}**")

    title = contact.title
    company = contact.company
    if title and company:
        lines.append(f"_{title} at {company}_")
    elif title:
        lines.append(f"_{title}_")
    elif company:
        lines.append(f"_at {company}_")

    lines.append("")

    if contact.email:
        lines.append(f"📧 {contact.email}")
    if contact.phone:
        lines.append(f"📱 {contact.phone}")
    if contact.linkedin_url:
        lines.append(f"🔗 {contact.linkedin_url}")
    if contact.address:
        lines.append(f"📍 {contact.address}")
    if contact.industry:
        lines.append(f"🏢 {contact.industry}")
    if contact.contact_type:
        lines.append(f"👤 {contact.contact_type}")
    if contact.company_description:
        desc = contact.company_description
        if len(desc) > 100:
            desc = desc[:100] + "..."
        lines.append(f"📄 {desc}")

    research_summary = getattr(contact, 'research_summary', None)
    if research_summary:
        lines.append("")
        summary = research_summary
        if len(summary) > 200:
            summary = summary[:200] + "..."
        lines.append(f"**Summary:** {summary}")

    return "\n".join(lines)


def contact_missing_fields(contact: "Contact") -> list:
    """Get list of empty important fields on a Contact."""
    missing = []
    if not contact.email:
        missing.append("email")
    if not contact.phone:
        missing.append("phone")
    if not contact.linkedin_url:
        missing.append("LinkedIn")
    if not contact.company:
        missing.append("company")
    return missing
