"""
Telegram handlers for enrichment commands.
Enhanced with comprehensive data enrichment capabilities.
"""

import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from crews.enrichment_crew import get_enrichment_crew
from analytics.tracker import get_tracker
from data.schema import OperationType


async def enrich_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /enrich command to enrich a contact with online search.
    Supports:
    - /enrich <name> - Enrich a specific contact
    - /enrich <name> from <company> - Enrich with company context
    - /enrich all - Bulk enrich all contacts needing data
    - /enrich - Show contacts needing enrichment
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.ENRICH_CONTACT.value,
        user_id=user_id,
        command="/enrich"
    )

    try:
        crew = get_enrichment_crew()

        # No arguments - show what needs enrichment
        if not context.args:
            await _show_enrichment_options(update, crew)
            tracker.end_operation(success=True)
            return

        input_text = " ".join(context.args)

        # Check for bulk enrichment commands
        if input_text.lower() in ["all", "bulk", "my contacts", "contacts"]:
            await _handle_bulk_enrichment(update, crew, tracker)
            return

        # Single contact enrichment
        await _handle_single_enrichment(update, crew, tracker, input_text)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"The intel gathering hit a snag.\n\n_{str(e)}_",
            parse_mode="Markdown"
        )


async def _show_enrichment_options(update: Update, crew):
    """Show contacts that need enrichment."""
    try:
        contacts_needing = crew.get_contacts_needing_enrichment()

        if not contacts_needing:
            await update.message.reply_text(
                "All your contacts are fully enriched! Nothing to do here.\n\n"
                "To enrich a specific contact, use:\n"
                "`/enrich John Doe`\n"
                "`/enrich John from TechCorp`",
                parse_mode="Markdown"
            )
            return

        message = f"Found **{len(contacts_needing)}** contacts that could use some enrichment:\n\n"

        # Show first 10
        for i, contact in enumerate(contacts_needing[:10]):
            name = contact.get("name", "Unknown")
            missing = ", ".join(contact.get("missing_fields", [])[:3])
            message += f"{i+1}. **{name}** - _missing: {missing}_\n"

        if len(contacts_needing) > 10:
            message += f"\n_...and {len(contacts_needing) - 10} more_\n"

        message += "\n**Options:**\n"
        message += "`/enrich all` - Enrich all contacts\n"
        message += "`/enrich <name>` - Enrich a specific contact"

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(
            "Enrich *who* exactly? I need a name.\n\n"
            "Try:\n"
            "`/enrich John Doe`\n"
            "`/enrich all` - for bulk enrichment",
            parse_mode="Markdown"
        )


async def _handle_bulk_enrichment(update: Update, crew, tracker):
    """Handle bulk enrichment of all contacts."""
    await update.message.reply_text(
        "Starting bulk enrichment for all contacts with missing data...\n\n"
        "_This may take a few moments. Grab a coffee._",
        parse_mode="Markdown"
    )

    try:
        result = crew.enrich_bulk()

        total = result.get("total", 0)
        enriched = result.get("enriched", 0)
        partial = result.get("partial", 0)
        failed = result.get("failed", 0)

        summary = (
            f"**Bulk enrichment complete!**\n\n"
            f"Total contacts processed: {total}\n"
            f"Successfully enriched: {enriched}\n"
            f"Partially enriched: {partial}\n"
            f"Failed: {failed}\n\n"
            "_Would you like me to show the enriched data for any specific contact?_"
        )

        await update.message.reply_text(summary, parse_mode="Markdown")
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"Bulk enrichment hit a snag.\n\n_{str(e)}_",
            parse_mode="Markdown"
        )


async def _handle_single_enrichment(update: Update, crew, tracker, input_text: str):
    """Handle single contact enrichment."""
    await update.message.reply_text(
        f"Running enrichment for **{input_text}**...\n\n"
        "_This is the part where I work my magic._",
        parse_mode="Markdown"
    )

    # Use the comprehensive enrichment
    result = crew.enrich_contact_comprehensive(input_text)

    # Format output
    status = result.get("status", "Unknown")
    name = result.get("full_name", input_text)
    company = result.get("company")

    # Build response
    response = f"Running enrichment for {name}...\n\n"
    response += "```json\n"
    response += json.dumps(result, indent=2, ensure_ascii=False)
    response += "\n```"

    # Auto-save enrichment data to Google Sheets
    saved = False
    if status in ["Enriched", "Partial"]:
        try:
            save_result = crew.enrich_and_update_contact(name, company if company != "NA" else None)
            saved = save_result.get("updated_in_db", False)
        except Exception as e:
            print(f"Failed to save enrichment: {e}")

    # Add status-specific outro
    if status == "Enriched":
        if saved:
            response += "\n\n_Contact enriched and saved to your network!_"
        else:
            response += "\n\n_Contact enriched successfully!_"
    elif status == "Partial":
        if saved:
            response += "\n\n_Partial data found and saved. Some fields could not be verified._"
        else:
            response += "\n\n_Partial data found. Some fields could not be verified._"
    else:
        response += "\n\n_Could not find sufficient data for enrichment._"

    await update.message.reply_text(response, parse_mode="Markdown")
    tracker.end_operation(success=True)


async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /research command to research a company."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="research_company",
        user_id=user_id,
        command="/research"
    )
    
    try:
        if not context.args:
            await update.message.reply_text(
                "Research *which* company? 🏢\n\n"
                "Try: `/research TechCorp`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        company_name = " ".join(context.args)
        await update.message.reply_text(
            f"Pulling up everything on **{company_name}**... 🏢🔍\n\n"
            "_Let's see what skeletons are in this closet._",
            parse_mode="Markdown"
        )
        
        crew = get_enrichment_crew()
        result = crew.research_company(company_name)
        
        await update.message.reply_text(result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Research mission failed. 📚❌\n\n_{str(e)}_", parse_mode="Markdown")


async def linkedin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /linkedin command to find a person's LinkedIn profile."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="find_linkedin",
        user_id=user_id,
        command="/linkedin"
    )
    
    try:
        if not context.args:
            await update.message.reply_text(
                "LinkedIn stalking requires a name. 👀\n\n"
                "Try: `/linkedin John Doe`\n"
                "Or with company: `/linkedin John Doe TechCorp`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        args = " ".join(context.args)
        await update.message.reply_text(
            "Hunting down their LinkedIn... 🔗\n\n"
            "_Everyone's on LinkedIn. It's 2026._",
            parse_mode="Markdown"
        )
        
        crew = get_enrichment_crew()
        result = crew.find_linkedin(args)
        
        await update.message.reply_text(result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Couldn't find their LinkedIn. Maybe they're off the grid? 🕵️\n\n_{str(e)}_", parse_mode="Markdown")


def get_enrichment_handlers():
    """Get all enrichment-related handlers."""
    return [
        CommandHandler("enrich", enrich_command),
        CommandHandler("research", research_command),
        CommandHandler("linkedin", linkedin_command),
    ]
