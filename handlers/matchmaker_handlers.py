"""
Telegram handlers for matchmaker commands.
Matches Founders with Investors based on compatibility analysis.
"""

import re
from typing import Dict, List, Any
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from services.matchmaker import run_matchmaker, get_matchmaker_service
from analytics.tracker import get_tracker
from data.schema import OperationType, Match

# Store pending matches per user (not auto-saved)
_pending_matches: Dict[str, List[Match]] = {}


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
        # FIX: Send "Keep Alive" message immediately to prevent timeout
        # This lets Telegram know we're processing and prevents the 60s timeout
        await update.message.reply_text(
            "🤝 **Starting the Matchmaker...**\n\n"
            "This analyzes ALL your Founders and Investors to find the best matches.\n"
            "⏳ This may take **60+ seconds** depending on your network size.\n\n"
            "_Please wait - I'll send results when ready._",
            parse_mode="Markdown"
        )

        # Progress callback to send periodic updates
        progress_count = [0]

        async def send_progress(msg: str):
            progress_count[0] += 1
            # Send keep-alive every 5 progress updates to prevent timeout
            if progress_count[0] % 5 == 0:
                try:
                    await update.message.reply_text(f"⏳ Still working... {msg}")
                except Exception:
                    pass  # Ignore errors

        # Run the matchmaker (generates matches but we control saving)
        service = get_matchmaker_service()
        matches, summary = service.run_matching(progress_callback=lambda msg: None)

        # Store matches for /save_matches command (FIX: Router Ambiguity)
        if matches:
            _pending_matches[user_id] = matches

        # Send final report - use plain text to avoid markdown parsing issues
        if matches:
            report = f"""✅ MATCHMAKER COMPLETE

{summary}

📝 Matches are ready but NOT yet saved.

Type /save_matches to write these matches to Airtable.
Type /matches to preview matches before saving."""
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


async def save_matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /save_matches command to save pending matches to Airtable.

    FIX: Router Ambiguity - This dedicated command ensures "Save" doesn't
    get confused between saving contacts vs saving matches.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/save_matches"
    )

    try:
        # Check for pending matches
        if user_id not in _pending_matches or not _pending_matches[user_id]:
            await update.message.reply_text(
                "📭 No pending matches to save.\n\n"
                "Run /match first to generate matches, then use /save_matches."
            )
            tracker.end_operation(success=True)
            return

        matches = _pending_matches[user_id]

        # Send confirmation before saving
        await update.message.reply_text(
            f"💾 Saving {len(matches)} matches to Airtable...\n"
            "_Please wait._"
        )

        # Save to Airtable
        service = get_matchmaker_service()
        saved_count = service.save_matches_to_sheet(matches)

        # Clear pending matches after saving
        del _pending_matches[user_id]

        if saved_count > 0:
            await update.message.reply_text(
                f"✅ Successfully saved {saved_count} matches to Airtable!\n\n"
                "Use /matches to view them.\n"
                "Use /draft to generate outreach emails."
            )
        else:
            await update.message.reply_text(
                "⚠️ No matches were saved. There may have been an error.\n"
                "Check that your Airtable Matches table is properly configured."
            )

        tracker.end_operation(success=saved_count > 0)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"❌ Failed to save matches.\n\n{str(e)}"
        )


def get_matchmaker_handlers():
    """Get all matchmaker-related handlers."""
    return [
        CommandHandler("match", match_command),
        CommandHandler("matches", matches_command),
        CommandHandler("save_matches", save_matches_command),  # FIX: Dedicated save command
        CommandHandler("clear_matches", clear_matches_command),
    ]
