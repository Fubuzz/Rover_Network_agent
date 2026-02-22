"""
Telegram handlers for reporting and statistics commands.
"""

import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler
import io
import re

from crews.reporting_crew import get_reporting_crew
from services.airtable_service import get_sheets_service
from analytics.tracker import get_tracker
from data.schema import OperationType
from utils.formatters import format_statistics

logger = logging.getLogger('network_agent')

TELEGRAM_MSG_LIMIT = 4096


async def safe_reply(message, text: str):
    """Send reply, falling back to plain text if Markdown fails. Chunks long messages."""
    chunks = _chunk_message(text)
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode="Markdown")
        except BadRequest:
            try:
                # Convert simple Markdown to HTML
                html_text = chunk
                html_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_text)
                html_text = re.sub(r'\*([^*]+?)\*', r'<b>\1</b>', html_text)
                html_text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+?)_(?![a-zA-Z0-9])', r'<i>\1</i>', html_text)
                await message.reply_text(html_text, parse_mode="HTML")
            except BadRequest:
                plain_text = re.sub(r'[*_`\[\]]', '', chunk)
                await message.reply_text(plain_text)


def _chunk_message(text: str, limit: int = TELEGRAM_MSG_LIMIT) -> list:
    """Split text into chunks that fit Telegram's message limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Find a good split point (newline or space)
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = text.rfind(' ', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command to show contact statistics."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/stats"
    )

    try:
        # Check for "by" parameter
        if context.args and len(context.args) >= 2 and context.args[0].lower() == "by":
            attribute = context.args[1]
            await update.message.reply_text(f"Crunching numbers by {attribute}... 📊")
            crew = get_reporting_crew()
            result = crew.generate_stats_by_attribute(attribute)
            intro = "Here's the breakdown: 📈\n\n"
            await safe_reply(update.message, intro + result)
        else:
            # General stats
            sheets = get_sheets_service()
            stats = sheets.get_contact_stats()

            intro = "Time for the numbers. _I love a good stat._ 📊\n\n"
            formatted = format_statistics(stats)
            await safe_reply(update.message, intro + formatted)

        tracker.end_operation(success=True)

    except Exception as e:
        logger.error(f"Stats command failed: {e}")
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text("Stats calculation hit a snag. Try again in a moment.")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command to generate a detailed contact report."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/report"
    )

    try:
        if not context.args:
            await update.message.reply_text(
                "Report on *who*? 📋\n\n"
                "Try: `/report John Doe`\n"
                "Or: `/report all` for the full network analysis",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return

        name = " ".join(context.args)

        if name.lower() == "all":
            await update.message.reply_text("Analyzing your entire network. This might take a sec... 🔍")
            crew = get_reporting_crew()
            result = crew.generate_network_insights()
            intro = "**Your Network Analysis** 🌐\n_Here's the big picture:_\n\n"
        else:
            await update.message.reply_text(f"Compiling everything on **{name}**... 📋")
            crew = get_reporting_crew()
            result = crew.generate_contact_report(name)
            intro = f"**Full Dossier: {name}** 📋\n_Everything I know (which is everything):_\n\n"

        await safe_reply(update.message, intro + result)
        tracker.end_operation(success=True)

    except Exception as e:
        logger.error(f"Report command failed: {e}")
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text("Report generation hit a snag. Try again in a moment.")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /export command to export contacts to CSV."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.EXPORT_CONTACTS.value,
        user_id=user_id,
        command="/export"
    )

    try:
        await update.message.reply_text("Packaging up your network... 📦\n\n_This is basically your little black book._")

        sheets = get_sheets_service()
        csv_content = sheets.export_to_csv()

        # Send as file
        file_bytes = io.BytesIO(csv_content.encode('utf-8'))
        file_bytes.name = "contacts_export.csv"

        await update.message.reply_document(
            document=file_bytes,
            filename="contacts_export.csv",
            caption="Here you go — your entire network in one tidy file. 📋✨\n\n_Handle with care. This is gold._"
        )

        tracker.end_operation(success=True)

    except Exception as e:
        logger.error(f"Export command failed: {e}")
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text("Export failed. Try again in a moment.")


def get_report_handlers():
    """Get all report-related handlers."""
    return [
        CommandHandler("stats", stats_command),
        CommandHandler("report", report_command),
        CommandHandler("export", export_command),
    ]
