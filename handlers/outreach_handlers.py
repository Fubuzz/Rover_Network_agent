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


async def outreach_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /outreach command for direct, natural-language outreach.

    Usage:
        /outreach Email all investors in Egypt about a meeting March 5-12
        /outreach Reach out to fintech founders to introduce Synapse
    """
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.GENERATE_REPORT.value,
        user_id=user_id,
        command="/outreach"
    )

    try:
        # Get the full text after /outreach
        raw_text = " ".join(context.args) if context.args else ""

        if not raw_text.strip():
            await update.message.reply_text(
                "Usage: /outreach <your request in plain English>\n\n"
                "Examples:\n"
                "  /outreach Email all investors in Egypt about a meeting March 5-12\n"
                "  /outreach Reach out to fintech founders to introduce myself\n"
                "  /outreach Send a warm email to my professional contacts about catching up"
            )
            tracker.end_operation(success=True)
            return

        await update.message.reply_text(
            f"Processing outreach request...\n\n\"{raw_text}\"\n\n"
            "Filtering contacts, generating emails, and saving drafts."
        )

        from services.outreach_direct import create_outreach_drafts

        count, summary, previews = create_outreach_drafts(
            contacts_query=raw_text,
            purpose=raw_text,
        )

        if count == 0:
            await update.message.reply_text(f"No drafts created.\n\n{summary}")
            tracker.end_operation(success=True)
            return

        # Build response with previews
        report = f"OUTREACH COMPLETE\n\n{summary}\n\n"
        for i, p in enumerate(previews[:5], 1):
            report += (
                f"{i}. To: {p['to']} ({p['email']})\n"
                f"   Subject: {p['subject']}\n"
                f"   {p['body_preview']}\n\n"
            )
        if len(previews) > 5:
            report += f"...and {len(previews) - 5} more.\n\n"

        report += "Review drafts in Airtable, set approval_status to APPROVED, then /send_approved."

        await update.message.reply_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Outreach failed.\n\n{str(e)}")


def get_outreach_handlers():
    """Get all outreach-related handlers."""
    return [
        CommandHandler("draft", draft_command),
        CommandHandler("send_approved", send_approved_command),
        CommandHandler("drafts", drafts_command),
        CommandHandler("clear_drafts", clear_drafts_command),
        CommandHandler("outreach", outreach_command),
    ]
