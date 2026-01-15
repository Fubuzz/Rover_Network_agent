"""
Telegram handlers for matchmaker commands.
Matches Founders with Investors based on compatibility analysis.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from services.matchmaker import run_matchmaker, get_matchmaker_service
from analytics.tracker import get_tracker
from data.schema import OperationType


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    if not text:
        return ""
    # Escape markdown special characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # But keep intentional formatting like **bold** and _italic_
    # For safety, escape underscores in the middle of words and angle brackets
    text = text.replace('<', '‹').replace('>', '›')  # Replace angle brackets with similar looking chars
    return text


async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /match command to run the matchmaker.
    Analyzes all Founders and Investors in the contacts database,
    creates matches based on compatibility, and saves to the Matches sheet.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/match"
    )

    try:
        # Send initial message
        status_message = await update.message.reply_text(
            "Starting the Matchmaker... \n\n"
            "_Analyzing Founders and Investors in your network._\n"
            "_This may take a few minutes._"
        )

        # Progress callback to update user
        progress_count = [0]

        async def send_progress(msg: str):
            progress_count[0] += 1
            if progress_count[0] % 3 == 0:  # Update every 3rd progress message
                try:
                    await status_message.edit_text(
                        f"Matchmaker running...\n\n_{msg}_"
                    )
                except Exception:
                    pass  # Ignore edit errors

        # Run the matchmaker
        matches, summary = await run_matchmaker(progress_callback=lambda msg: None)

        # Send final report - use plain text to avoid markdown parsing issues
        if matches:
            report = f"""✅ MATCHMAKER COMPLETE

{summary}

All matches have been saved to the 'Matches' sheet in your Google Spreadsheet.

Use /matches to see all saved matches."""
        else:
            report = """✅ MATCHMAKER COMPLETE

No high-quality matches found.

This could mean:
• No Founders or Investors in your contacts
• Low compatibility between existing contacts
• Missing contact_type classification

Make sure contacts have:
• contact_type set to "Founder" or "Investor"
• Industry/sector information
• Company/startup details"""

        # Send without markdown parsing to avoid entity errors
        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"❌ Matchmaker failed.\n\n{str(e)}"
        )


async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /matches command to show saved matches.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/matches"
    )

    try:
        service = get_matchmaker_service()
        sheets = service.sheets_service
        matches = sheets.get_all_matches()

        if not matches:
            await update.message.reply_text(
                "📭 No matches found.\n\n"
                "Run /match to analyze your network and generate matches."
            )
            tracker.end_operation(success=True)
            return

        # Format matches summary - plain text to avoid markdown issues
        report = f"📊 Saved Matches ({len(matches)} total)\n\n"

        # Show top 10 matches
        for i, match in enumerate(matches[:10], 1):
            score_emoji = "🟢" if match.match_score >= 80 else "🟡" if match.match_score >= 60 else "🟠"
            startup = match.startup_name or 'Unknown'
            investor = match.investor_firm or 'Unknown'
            stage = match.stage_alignment or ''
            report += (
                f"{i}. {score_emoji} {startup} ↔ {investor}\n"
                f"   Score: {match.match_score}/100 | {stage}\n\n"
            )

        if len(matches) > 10:
            report += f"\n...and {len(matches) - 10} more matches in your Sheets."

        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"❌ Failed to retrieve matches.\n\n{str(e)}"
        )


async def clear_matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /clear_matches command to clear all saved matches.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/clear_matches"
    )

    try:
        service = get_matchmaker_service()
        success = service.sheets_service.clear_matches()

        if success:
            await update.message.reply_text(
                "🗑️ Matches cleared.\n\n"
                "All matches have been removed from the Matches sheet.\n"
                "Run /match to generate new matches."
            )
        else:
            await update.message.reply_text(
                "❌ Failed to clear matches. The Matches sheet may not exist."
            )

        tracker.end_operation(success=success)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"❌ Failed to clear matches.\n\n{str(e)}"
        )


def get_matchmaker_handlers():
    """Get all matchmaker-related handlers."""
    return [
        CommandHandler("match", match_command),
        CommandHandler("matches", matches_command),
        CommandHandler("clear_matches", clear_matches_command),
    ]
