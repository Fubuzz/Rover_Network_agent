"""
Telegram handlers for voice, image, and text input processing.
Uses the AI-powered conversation engine for all text interactions.
"""

import asyncio
import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters

from services.ai_service import get_ai_service
from services.contact_memory import get_memory_service
from services.message_response import MessageResponse
from analytics.tracker import get_tracker
from data.schema import OperationType
from config import FeatureFlags
from handlers.conversation_engine import process_message

logger = logging.getLogger('network_agent')


# ============================================================
# DEBOUNCE STATE — per-user message batching
# ============================================================

_pending_messages: dict[str, list[str]] = {}   # user_id -> [messages]
_pending_tasks: dict[str, asyncio.Task] = {}    # user_id -> delayed task
_pending_updates: dict[str, Update] = {}        # user_id -> last Update (for reply)
_pending_contexts: dict[str, ContextTypes.DEFAULT_TYPE] = {}  # user_id -> last context
DEBOUNCE_SECONDS = 1.5


# ============================================================
# SAFE MESSAGE SENDING
# ============================================================

def _build_keyboard(buttons):
    """Build InlineKeyboardMarkup from button list."""
    if not buttons:
        return None
    keyboard = []
    for row in buttons:
        keyboard.append([InlineKeyboardButton(label, callback_data=data) for label, data in row])
    return InlineKeyboardMarkup(keyboard)


async def safe_reply(message, text: str, reply_markup=None):
    """Send reply, falling back to plain text if Markdown fails."""
    try:
        # First try with Markdown
        await message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except BadRequest as e:
        if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            # Markdown parsing failed - try HTML mode
            try:
                # Convert simple Markdown to HTML
                html_text = text
                # Bold: **text** or *text* -> <b>text</b>
                html_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_text)
                html_text = re.sub(r'\*([^*]+?)\*', r'<b>\1</b>', html_text)
                # Italic: _text_ -> <i>text</i> (but not underscores in emails)
                # Only convert if surrounded by spaces or start/end
                html_text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+?)_(?![a-zA-Z0-9])', r'<i>\1</i>', html_text)
                await message.reply_text(html_text, parse_mode="HTML", reply_markup=reply_markup)
            except BadRequest:
                # HTML also failed - send plain text
                # Strip markdown characters
                plain_text = re.sub(r'[*_`\[\]]', '', text)
                await message.reply_text(plain_text, reply_markup=reply_markup)
        else:
            raise


# ============================================================
# VOICE MESSAGE HANDLER
# ============================================================

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - transcribe and process as text."""
    if not FeatureFlags.VOICE_TRANSCRIPTION:
        await update.message.reply_text("Voice transcription is off. 🎤❌")
        return
    
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.VOICE_TRANSCRIPTION.value,
        user_id=user_id,
        command="voice_message"
    )
    
    try:
        await update.message.reply_text("Got your voice memo. Let me decode this... 🎧")
        
        # Get voice file
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        # Download voice file
        voice_bytes = await file.download_as_bytearray()
        
        # Transcribe using AI service
        ai_service = get_ai_service()
        transcript = ai_service.transcribe_audio(bytes(voice_bytes), "voice.ogg")
        
        if not transcript:
            await update.message.reply_text(
                "I couldn't make out what you said. 🤔\n\n"
                "_Try speaking a bit clearer?_"
            )
            tracker.end_operation(success=False, error_message="Transcription failed")
            return
        
        await safe_reply(
            update.message,
            f"**I heard:** _{transcript}_\n\nProcessing... 💭"
        )

        # Process the transcript through the conversation engine
        response = await process_message(user_id, transcript)

        if isinstance(response, MessageResponse):
            markup = _build_keyboard(response.buttons)
            await safe_reply(update.message, response.text, reply_markup=markup)
        else:
            await safe_reply(update.message, response)
        tracker.end_operation(success=True)
        
    except Exception as e:
        logger.error(f"Voice processing failed: {e}")
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text("Voice processing hit a snag. 🎤 Try again?")


# ============================================================
# PHOTO MESSAGE HANDLER
# ============================================================

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages (business cards) to extract contact information."""
    if not FeatureFlags.IMAGE_OCR:
        await update.message.reply_text("Image reading is disabled. 👀❌")
        return
    
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type=OperationType.IMAGE_OCR.value,
        user_id=user_id,
        command="photo_message"
    )
    
    try:
        await update.message.reply_text(
            "Business card detected! Reading it now... 👓\n\n_Nice design, by the way._"
        )
        
        # Get the largest photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Download image to temp file
        import tempfile, os
        image_bytes = await file.download_as_bytearray()
        
        # Save to temp file for GPT-4o Vision
        temp_path = os.path.join(tempfile.gettempdir(), f"card_{user_id}_{photo.file_id}.jpg")
        with open(temp_path, "wb") as f:
            f.write(bytes(image_bytes))
        
        # Extract using GPT-4o Vision (upgraded from old ai_service)
        from services.auto_enrichment import extract_business_card
        import asyncio
        extracted = await extract_business_card(temp_path)
        
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass
        
        if not extracted:
            await update.message.reply_text(
                "I couldn't read that. 😅\n\n"
                "Try a clearer photo — good lighting, flat surface?"
            )
            tracker.end_operation(success=False, error_message="OCR extraction failed")
            return
        
        # Format and show extracted data
        lines = ["**Here's what I extracted:** 📋", ""]
        for field, value in extracted.items():
            if value:
                lines.append(f"**{field.replace('_', ' ').title()}:** {value}")

        await safe_reply(update.message, "\n".join(lines))

        # Check if user is already collecting a contact
        memory = get_memory_service()
        if memory.is_collecting(user_id):
            pending = memory.get_pending_contact(user_id)
            if pending:
                extracted_name = extracted.get('name', '').lower()
                pending_name = pending.name.lower() if pending.name else ''

                # If the card has a different name, ask the user
                if extracted_name and extracted_name != pending_name and extracted_name not in pending_name:
                    await safe_reply(
                        update.message,
                        f"I see you're adding **{pending.name}**, but this card is for **{extracted.get('name')}**.\n\n"
                        f"What should I do?\n"
                        f"• Say _'add to current'_ to add this info to {pending.name}\n"
                        f"• Say _'new contact'_ to start a new contact for {extracted.get('name')}\n"
                        f"• Say _'done'_ to save {pending.name} first"
                    )
                    tracker.end_operation(success=True)
                    return

                # Same person or no name conflict - add info to current contact
                text_repr = ""
                if extracted.get('title'):
                    text_repr += f"{extracted['title']} "
                if extracted.get('company'):
                    text_repr += f"at {extracted['company']} "
                if extracted.get('email'):
                    text_repr += f"email: {extracted['email']} "
                if extracted.get('phone'):
                    text_repr += f"phone: {extracted['phone']}"

                if text_repr.strip():
                    response = await process_message(user_id, text_repr.strip())
                    if isinstance(response, MessageResponse):
                        markup = _build_keyboard(response.buttons)
                        await safe_reply(update.message, response.text, reply_markup=markup)
                    else:
                        await safe_reply(update.message, response)
                else:
                    await safe_reply(
                        update.message,
                        f"Hmm, couldn't extract much from that card for **{pending.name}**. 🤔\n"
                        f"Try adding details manually!"
                    )

                tracker.end_operation(success=True)
                return

        # Not collecting - start a new contact with the extracted info
        text_repr = f"Add {extracted.get('name', 'contact')}"
        if extracted.get('title'):
            text_repr += f", {extracted['title']}"
        if extracted.get('company'):
            text_repr += f" at {extracted['company']}"
        if extracted.get('email'):
            text_repr += f", email: {extracted['email']}"
        if extracted.get('phone'):
            text_repr += f", phone: {extracted['phone']}"

        response = await process_message(user_id, text_repr)
        if isinstance(response, MessageResponse):
            markup = _build_keyboard(response.buttons)
            await safe_reply(update.message, response.text, reply_markup=markup)
        else:
            await safe_reply(update.message, response)

        tracker.end_operation(success=True)

    except Exception as e:
        logger.error(f"Photo processing failed: {e}")
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text("Image processing went sideways. 📸 Try again?")


# ============================================================
# DOCUMENT MESSAGE HANDLER
# ============================================================

async def handle_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (CSV, Excel files) for bulk import."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)

    tracker.start_operation(
        operation_type=OperationType.IMPORT_CONTACTS.value,
        user_id=user_id,
        command="document_message"
    )

    try:
        document = update.message.document
        file_name = document.file_name
        file_name_lower = file_name.lower()

        # Check supported formats
        supported_formats = ('.csv', '.xlsx', '.xls')
        if not file_name_lower.endswith(supported_formats):
            await update.message.reply_text(
                "📄 Supported formats: CSV, XLSX\n\n"
                "Please upload a spreadsheet with contact data.\n"
                "Make sure it has headers like: Name, Email, Company, Title, Phone"
            )
            tracker.end_operation(success=True)
            return

        # Download file first to get size info
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        # Estimate row count for large file warning
        file_size_kb = len(file_bytes) / 1024
        estimated_rows = int(file_size_kb / 0.1)  # Rough estimate: ~100 bytes per row

        # Send processing message
        if estimated_rows > 500:
            status_msg = await update.message.reply_text(
                f"📥 Processing {file_name}...\n\n"
                f"📊 Large file detected (~{estimated_rows:,} rows estimated)\n"
                f"⏱️ This may take several minutes due to API rate limits.\n\n"
                f"I'll update you when it's done!"
            )
        else:
            status_msg = await update.message.reply_text(
                f"📥 Processing {file_name}...\n\n"
                "This may take a moment."
            )

        # Run bulk import
        from services.bulk_import import get_bulk_import_service
        service = get_bulk_import_service()
        result = await service.import_file(bytes(file_bytes), file_name)

        # Build result report
        report = f"""✅ Import Complete!

📊 Results:
• Total rows: {result.total_rows}
• Added: {result.successful}
• Updated: {result.updated}
• Skipped: {result.skipped}
• Failed: {result.failed}"""

        if result.errors:
            report += f"\n\n⚠️ Issues ({len(result.errors)}):\n"
            for error in result.errors[:5]:  # Show first 5 errors
                report += f"• {error}\n"
            if len(result.errors) > 5:
                report += f"...and {len(result.errors) - 5} more"

        await status_msg.edit_text(report)
        tracker.end_operation(success=True)

    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"❌ Error processing document: {str(e)}")


# ============================================================
# ENRICHMENT KEYWORD DETECTION
# ============================================================

_ENRICH_PREFIXES = ("enrich", "research", "look up")


def _is_enrichment_request(text: str) -> bool:
    """Check if the message is an enrichment/research request."""
    text_lower = text.lower().strip()
    return any(text_lower.startswith(p) for p in _ENRICH_PREFIXES)


# ============================================================
# TEXT MESSAGE HANDLER - Main entry point (with debounce + progress)
# ============================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages using the AI-powered conversation engine.
    Includes debounce (batches rapid messages) and progress indicator for enrichment.
    """
    # Skip if it's a command
    if update.message.text.startswith('/'):
        return

    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # --- Debounce: accumulate rapid messages ---
    _pending_messages.setdefault(user_id, []).append(text)
    _pending_updates[user_id] = update
    _pending_contexts[user_id] = context

    # Cancel any existing timer for this user
    existing_task = _pending_tasks.get(user_id)
    if existing_task and not existing_task.done():
        existing_task.cancel()

    # Schedule flush after DEBOUNCE_SECONDS
    _pending_tasks[user_id] = asyncio.create_task(_flush_after_delay(user_id))


async def _flush_after_delay(user_id: str):
    """Wait for debounce period, then flush accumulated messages."""
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return  # A newer message arrived, so this timer was superseded

    await _flush_messages(user_id)


async def _flush_messages(user_id: str):
    """Combine pending messages and process them."""
    messages = _pending_messages.pop(user_id, [])
    update = _pending_updates.pop(user_id, None)
    _pending_contexts.pop(user_id, None)
    _pending_tasks.pop(user_id, None)

    if not messages or not update:
        return

    # Combine multiple rapid messages into one
    combined = "\n".join(messages)

    tracker = get_tracker()
    tracker.start_operation(
        operation_type=OperationType.ADD_CONTACT.value,
        user_id=user_id,
        command="text_message"
    )

    try:
        # --- Progress indicator for enrichment ---
        status_msg = None
        if _is_enrichment_request(combined):
            try:
                status_msg = await update.message.reply_text(
                    "Researching... this may take a moment."
                )
            except Exception:
                pass

        # Process through conversation engine
        response = await process_message(user_id, combined)

        # Build reply
        if isinstance(response, MessageResponse):
            resp_text = response.text
            markup = _build_keyboard(response.buttons)
        else:
            resp_text = response
            markup = None

        # If we sent a progress placeholder, edit it; otherwise send new message
        if status_msg:
            try:
                await status_msg.edit_text(
                    resp_text, parse_mode="Markdown", reply_markup=markup
                )
            except BadRequest:
                # Edit failed (e.g. text unchanged) — fall back to new message
                await safe_reply(update.message, resp_text, reply_markup=markup)
        else:
            await safe_reply(update.message, resp_text, reply_markup=markup)

        tracker.end_operation(success=True)

    except Exception as e:
        logger.error(f"Conversation engine error: {e}")
        import traceback
        traceback.print_exc()
        tracker.end_operation(success=False, error_message=str(e))
        try:
            await update.message.reply_text(f"Something went wrong: {str(e)}")
        except Exception:
            pass


# ============================================================
# HANDLER REGISTRATION
# ============================================================

def get_input_handlers():
    """Get all input processing handlers."""
    return [
        MessageHandler(filters.VOICE, handle_voice_message),
        MessageHandler(filters.PHOTO, handle_photo_message),
        MessageHandler(filters.Document.ALL, handle_document_message),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message),
    ]
