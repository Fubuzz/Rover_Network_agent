"""
Telegram handlers for natural language conversation and help.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from services.ai_service import get_ai_service
from services.google_sheets import get_sheets_service
from utils.constants import MESSAGES, COMMANDS
from analytics.tracker import get_tracker


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="start_bot",
        user_id=user_id,
        command="/start"
    )
    
    try:
        await update.message.reply_text(MESSAGES["welcome"], parse_mode="Markdown")
        tracker.end_operation(success=True)
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="help",
        user_id=user_id,
        command="/help"
    )
    
    try:
        await update.message.reply_text(MESSAGES["help"], parse_mode="Markdown")
        tracker.end_operation(success=True)
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remind command to set a follow-up reminder."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="set_reminder",
        user_id=user_id,
        command="/remind"
    )
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Remind you about *who* and *when*? 📅\n\n"
                "Try: `/remind John Doe next week`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # For now, store reminder in notes
        name = context.args[0]
        reminder_date = " ".join(context.args[1:])
        
        sheets = get_sheets_service()
        contact = sheets.get_contact_by_name(name)
        
        if not contact:
            await update.message.reply_text(
                f"I don't have anyone named **{name}** in my records. 🤔\n\n"
                "_Check the spelling?_",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # Add reminder to notes
        current_notes = contact.notes or ""
        new_notes = f"{current_notes}\n[REMINDER: {reminder_date}]".strip()
        
        sheets.update_contact(name, {"notes": new_notes})
        
        await update.message.reply_text(
            f"⏰ Done! I'll make sure you don't forget about **{name}** ({reminder_date}).\n\n"
            "_Unlike that time you forgot to... never mind._ 😏",
            parse_mode="Markdown"
        )
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Reminder failed. The irony. ⏰❌\n\n_{str(e)}_", parse_mode="Markdown")


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note command to add a note to a contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="add_note",
        user_id=user_id,
        command="/note"
    )
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Spill the tea! ☕\n\n"
                "Try: `/note John Doe Met at conference, interested in AI`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # Parse: first word(s) are name until we hit a likely note
        args = " ".join(context.args)
        
        # Try to find the name (assume first 1-3 words)
        sheets = get_sheets_service()
        name = None
        note_text = None
        
        # Try different name lengths
        words = args.split()
        for i in range(min(3, len(words)), 0, -1):
            potential_name = " ".join(words[:i])
            contact = sheets.get_contact_by_name(potential_name)
            if contact:
                name = potential_name
                note_text = " ".join(words[i:])
                break
        
        if not name:
            await update.message.reply_text(
                "Can't find that person. 🤔\n\n_Double-check the name?_",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        if not note_text:
            await update.message.reply_text(
                "You want to add a note but... you didn't give me a note. 📝\n\n_I'm good, but I'm not a mind reader._",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # Add note
        contact = sheets.get_contact_by_name(name)
        current_notes = contact.notes or ""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d")
        new_notes = f"{current_notes}\n[{timestamp}] {note_text}".strip()
        
        sheets.update_contact(name, {"notes": new_notes})
        
        await update.message.reply_text(
            f"📝 Note added to **{name}**.\n\n_Your secrets are safe with me._ 🤫",
            parse_mode="Markdown"
        )
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Note-taking failed. 📝❌\n\n_{str(e)}_", parse_mode="Markdown")


async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tag command to add tags to a contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="add_tags",
        user_id=user_id,
        command="/tag"
    )
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: `/tag <name> <tag1,tag2,...>`\n"
                "Example: `/tag John Doe ai,startup,potential-partner`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # Last arg is tags, everything before is name
        tags_str = context.args[-1]
        name = " ".join(context.args[:-1])
        
        sheets = get_sheets_service()
        contact = sheets.get_contact_by_name(name)
        
        if not contact:
            await update.message.reply_text(f"Contact '{name}' not found.")
            tracker.end_operation(success=True)
            return
        
        # Parse and merge tags
        new_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        existing_tags = contact.tags or []
        all_tags = list(set(existing_tags + new_tags))
        
        sheets.update_contact(name, {"tags": ",".join(all_tags)})
        
        await update.message.reply_text(f"✅ Tags added to {name}: {', '.join(new_tags)}")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error adding tags: {str(e)}")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ask command for natural language queries about contacts."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="ask_question",
        user_id=user_id,
        command="/ask"
    )
    
    try:
        if not context.args:
            await update.message.reply_text(
                "Go ahead, ask me anything about your network. 💭\n\n"
                "Try:\n"
                "• `/ask Who works at TechCorp?`\n"
                "• `/ask How many founders do I know?`\n"
                "• `/ask Who should I follow up with?`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        question = " ".join(context.args)
        await update.message.reply_text("Let me think about that... 🤔")
        
        # Get context from contacts
        sheets = get_sheets_service()
        contacts = sheets.get_all_contacts()
        stats = sheets.get_contact_stats()
        
        context_info = f"""
Contact Database Summary:
- Total contacts: {stats['total']}
- By classification: {stats['by_classification']}
- Top companies: {list(stats['by_company'].keys())[:5]}

Recent contacts (sample):
"""
        for contact in contacts[:10]:
            context_info += f"- {contact.name}: {contact.job_title or 'N/A'} at {contact.company or 'N/A'}\n"
        
        # Use AI to answer
        ai_service = get_ai_service()
        response = ai_service.generate_response(question, context_info)
        
        await update.message.reply_text(f"Here's what I found: 💡\n\n{response}", parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"My brain short-circuited. 🧠💥\n\n_{str(e)}_", parse_mode="Markdown")


def get_conversation_handlers():
    """Get all conversation-related handlers."""
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CommandHandler("remind", remind_command),
        CommandHandler("note", note_command),
        CommandHandler("tag", tag_command),
        CommandHandler("ask", ask_command),
    ]
