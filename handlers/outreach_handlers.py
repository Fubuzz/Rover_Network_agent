"""
Telegram handlers for outreach commands.
Drafts emails from matches and sends approved emails.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from services.outreach import run_drafter, run_sender, get_outreach_service
from analytics.tracker import get_tracker
from data.schema import OperationType


async def draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /draft command to generate email drafts from matches.
    Reads high-quality matches (score > 70) and creates personalized email drafts.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/draft"
    )

    try:
        # Parse optional min_score argument
        min_score = 70
        if context.args and len(context.args) > 0:
            try:
                min_score = int(context.args[0])
            except ValueError:
                pass

        # Send initial message
        await update.message.reply_text(
            f"Starting the Drafter...\n\n"
            f"Looking for matches with score >= {min_score}\n"
            f"This may take a few minutes."
        )

        # Run the drafter
        count, summary = await run_drafter(min_score=min_score, progress_callback=None)

        # Send final report
        if count > 0:
            report = f"DRAFTER COMPLETE\n\n{summary}\n\nReview drafts in your Drafts sheet and set approval_status to APPROVED to send."
        else:
            report = "DRAFTER COMPLETE\n\nNo drafts created.\n\nThis could mean:\n- No matches with score >= 70\n- All eligible matches already have drafts\n\nRun /match first to generate matches, then try /draft again."

        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Drafter failed.\n\n{str(e)}")


async def send_approved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /send_approved command to send approved email drafts.
    Scans the Drafts sheet for approved rows and sends via SMTP.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/send_approved"
    )

    try:
        # Send initial message
        await update.message.reply_text(
            "Checking for approved emails...\n\n"
            "Looking for drafts with approval_status = APPROVED"
        )

        # Run the sender
        sent_count, failed_count, summary = await run_sender(progress_callback=None)

        # Send final report
        if sent_count > 0 or failed_count > 0:
            report = f"SENDER COMPLETE\n\n{summary}\n\nCheck the Drafts sheet for send_status updates."
        else:
            report = "SENDER COMPLETE\n\nNo approved emails to send.\n\nTo send emails:\n1. Open the Drafts sheet\n2. Review emails in email_body column\n3. Set approval_status to APPROVED\n4. Run /send_approved again"

        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Sender failed.\n\n{str(e)}")


async def drafts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /drafts command to show draft statistics.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/drafts"
    )

    try:
        service = get_outreach_service()
        stats = service.get_draft_stats()

        report = f"""Draft Statistics

Total drafts: {stats['total']}
Pending review: {stats['pending']}
Approved: {stats['approved']}
Sent: {stats['sent']}
Failed: {stats['failed']}

Commands:
/draft - Create new drafts from matches
/send_approved - Send approved drafts
/clear_drafts - Clear all drafts"""

        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Failed to get draft stats.\n\n{str(e)}")


async def clear_drafts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /clear_drafts command to clear all drafts.
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/clear_drafts"
    )

    try:
        service = get_outreach_service()
        success = service.sheets_service.clear_drafts()

        if success:
            await update.message.reply_text(
                "Drafts cleared.\n\n"
                "All drafts have been removed from the Drafts sheet.\n"
                "Run /draft to generate new drafts from matches."
            )
        else:
            await update.message.reply_text(
                "Failed to clear drafts. The Drafts sheet may not exist."
            )

        tracker.end_operation(success=success)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Failed to clear drafts.\n\n{str(e)}")


def get_outreach_handlers():
    """Get all outreach-related handlers."""
    return [
        CommandHandler("draft", draft_command),
        CommandHandler("send_approved", send_approved_command),
        CommandHandler("drafts", drafts_command),
        CommandHandler("clear_drafts", clear_drafts_command),
    ]
