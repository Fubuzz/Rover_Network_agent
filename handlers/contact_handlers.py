"""
Telegram handlers for contact management commands.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
import time

from crews.contact_crew import get_contact_crew
from crews.input_processing_crew import get_input_processing_crew
from services.airtable_service import get_sheets_service
from services.local_storage import get_local_storage
from analytics.tracker import get_tracker
from data.schema import OperationType
from utils.formatters import format_contact_card, format_contact_list
from utils.constants import MESSAGES


def get_storage():
    """Get the best available storage (Google Sheets or local fallback)."""
    try:
        sheets = get_sheets_service()
        sheets._ensure_initialized()
        return sheets, "airtable"
    except Exception:
        return get_local_storage(), "local"


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command to add a new contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.ADD_CONTACT.value,
        user_id=user_id,
        command="/add"
    )
    
    try:
        # Check if there's data after the command
        if context.args:
            text = " ".join(context.args)
            await update.message.reply_text("On it. Let me file this one away... 📁")
            
            # Use input processing crew
            crew = get_input_processing_crew()
            result = crew.process_text(text)
            
            await update.message.reply_text(result, parse_mode="Markdown")
            tracker.end_operation(success=True)
        else:
            await update.message.reply_text(
                "I need *something* to work with here. 🙄\n\n"
                "Try: `/add John Doe, CEO at TechCorp, john@techcorp.com`\n\n"
                "Or just tell me about them naturally. I'm fluent in human.",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Well, that didn't work. 😬\n\n_{str(e)}_", parse_mode="Markdown")


async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /view command to view a contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.VIEW_CONTACT.value,
        user_id=user_id,
        command="/view"
    )
    
    try:
        if not context.args:
            await update.message.reply_text("View *who* exactly? 🤨\n\nTry: `/view John Doe`", parse_mode="Markdown")
            tracker.end_operation(success=True)
            return
        
        name = " ".join(context.args)
        storage, storage_type = get_storage()
        contact = storage.get_contact_by_name(name)
        
        if contact:
            intro = f"Here's everything I have on **{name}**: 📋\n\n"
            card = format_contact_card(contact.to_dict())
            if storage_type == "local":
                card += "\n\n_📦 From local storage_"
            await update.message.reply_text(intro + card, parse_mode="Markdown")
            tracker.end_operation(success=True)
        else:
            await update.message.reply_text(MESSAGES["contact_not_found"].format(name=name), parse_mode="Markdown")
            tracker.end_operation(success=True)
            
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Oops. Something broke. 🔧\n\n_{str(e)}_", parse_mode="Markdown")


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /update command to update a contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.UPDATE_CONTACT.value,
        user_id=user_id,
        command="/update"
    )
    
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: `/update <name> <field> <value>`\n"
                "Example: `/update John Doe email john.new@email.com`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        # Parse command - first word(s) are name, then field, then value
        args = " ".join(context.args)
        
        # Simple parsing - find the field keyword
        fields = ["email", "phone", "company", "title", "linkedin", "location", "notes", "classification"]
        
        name = None
        field = None
        value = None
        
        for f in fields:
            if f" {f} " in args.lower():
                parts = args.lower().split(f" {f} ")
                if len(parts) == 2:
                    name = parts[0].strip()
                    field = f
                    value = parts[1].strip()
                    break
        
        if not all([name, field, value]):
            await update.message.reply_text("Could not parse update command. Try: `/update John Doe email new@email.com`", parse_mode="Markdown")
            tracker.end_operation(success=True)
            return
        
        crew = get_contact_crew()
        result = crew.update_contact(name, field, value)
        
        await update.message.reply_text(result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error updating contact: {str(e)}")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delete command to delete a contact."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.DELETE_CONTACT.value,
        user_id=user_id,
        command="/delete"
    )
    
    try:
        if not context.args:
            await update.message.reply_text("Please specify a contact name: `/delete John Doe`", parse_mode="Markdown")
            tracker.end_operation(success=True)
            return
        
        name = " ".join(context.args)
        storage, _ = get_storage()
        
        success = storage.delete_contact(name)
        
        if success:
            await update.message.reply_text(MESSAGES["contact_deleted"].format(name=name), parse_mode="Markdown")
        else:
            await update.message.reply_text(MESSAGES["contact_not_found"].format(name=name), parse_mode="Markdown")
        
        tracker.end_operation(success=success)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error deleting contact: {str(e)}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command to list all contacts."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.VIEW_CONTACT.value,
        user_id=user_id,
        command="/list"
    )
    
    try:
        page = 1
        if context.args:
            try:
                page = int(context.args[0])
            except ValueError:
                pass
        
        storage, storage_type = get_storage()
        contacts = storage.get_all_contacts()
        
        if not contacts:
            await update.message.reply_text(
                "Your network is looking a little... empty. 😬\n\n"
                "Let's fix that. Use /add to start building your empire.",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        storage_note = " _(local)_" if storage_type == "local" else ""
        intro = f"Here's your network — all **{len(contacts)}** of them:{storage_note} 👥\n\n"
        contact_list = [c.to_dict() for c in contacts]
        formatted = format_contact_list(contact_list, page=page)
        
        await update.message.reply_text(intro + formatted, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Something went wrong. Even I'm surprised. 😅\n\n_{str(e)}_", parse_mode="Markdown")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command to search contacts."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.SEARCH_CONTACT.value,
        user_id=user_id,
        command="/search"
    )
    
    try:
        if not context.args:
            await update.message.reply_text(
                "Search for *what* exactly? 🔍\n\n"
                "Try: `/search TechCorp` or `/search founder`",
                parse_mode="Markdown"
            )
            tracker.end_operation(success=True)
            return
        
        query = " ".join(context.args)
        await update.message.reply_text(f"Searching for '{query}'... 🔎")
        
        storage, storage_type = get_storage()
        contacts = storage.search_contacts(query)
        
        if contacts:
            intro = f"Found **{len(contacts)}** match{'es' if len(contacts) > 1 else ''}. I'm just that good. 💅\n\n"
            contact_list = [c.to_dict() for c in contacts]
            formatted = format_contact_list(contact_list)
            await update.message.reply_text(intro + formatted, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"Nothing found for '*{query}*'. 🤷‍♀️\n\n"
                "Either they don't exist, or you spelled it wrong. _No judgment._",
                parse_mode="Markdown"
            )
        
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Search failed. The irony isn't lost on me. 🙃\n\n_{str(e)}_", parse_mode="Markdown")


def get_contact_handlers():
    """Get all contact-related handlers."""
    return [
        CommandHandler("add", add_command),
        CommandHandler("view", view_command),
        CommandHandler("update", update_command),
        CommandHandler("delete", delete_command),
        CommandHandler("list", list_command),
        CommandHandler("search", search_command),
    ]
