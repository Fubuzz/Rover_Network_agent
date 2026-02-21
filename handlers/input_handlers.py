"""
Telegram handlers for voice, image, and text input processing.
Uses the AI-powered conversation engine for all text interactions.
"""

import re
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters

from services.ai_service import get_ai_service
from services.contact_memory import get_memory_service
from analytics.tracker import get_tracker
from data.schema import OperationType
from config import FeatureFlags
from handlers.conversation_engine import process_message


# ============================================================
# SAFE MESSAGE SENDING
# ============================================================

def escape_markdown(text: str) -> str:
    """Escape special Markdown characters for Telegram."""
    # Characters that need escaping in Telegram Markdown
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_response_safe(text: str) -> str:
    """Format response with safe Markdown - escape problematic characters in data values."""
    # Don't escape the formatting markers we intentionally use, but escape data
    # Simple approach: use HTML mode instead which is more forgiving
    return text


async def safe_reply(message, text: str):
    """Send reply, falling back to plain text if Markdown fails."""
    try:
        # First try with Markdown
        await message.reply_text(text, parse_mode="Markdown")
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
                await message.reply_text(html_text, parse_mode="HTML")
            except BadRequest:
                # HTML also failed - send plain text
                # Strip markdown characters
                plain_text = re.sub(r'[*_`\[\]]', '', text)
                await message.reply_text(plain_text)
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
        
        await update.message.reply_text(
            f"**I heard:** _{transcript}_\n\nProcessing... 💭",
            parse_mode="Markdown"
        )
        
        # Process the transcript through the conversation engine
        response = await process_message(user_id, transcript)
        
        await update.message.reply_text(response, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"Voice processing hit a snag. 🎤💥\n\n_{str(e)}_",
            parse_mode="Markdown"
        )


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

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        # Check if user is already collecting a contact
        memory = get_memory_service()
        if memory.is_collecting(user_id):
            pending = memory.get_pending_contact(user_id)
            if pending:
                extracted_name = extracted.get('name', '').lower()
                pending_name = pending.name.lower() if pending.name else ''

                # If the card has a different name, ask the user
                if extracted_name and extracted_name != pending_name and extracted_name not in pending_name:
                    await update.message.reply_text(
                        f"I see you're adding **{pending.name}**, but this card is for **{extracted.get('name')}**.\n\n"
                        f"What should I do?\n"
                        f"• Say _'add to current'_ to add this info to {pending.name}\n"
                        f"• Say _'new contact'_ to start a new contact for {extracted.get('name')}\n"
                        f"• Say _'done'_ to save {pending.name} first",
                        parse_mode="Markdown"
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
                    await update.message.reply_text(response, parse_mode="Markdown")
                else:
                    await update.message.reply_text(
                        f"Hmm, couldn't extract much from that card for **{pending.name}**. 🤔\n"
                        f"Try adding details manually!",
                        parse_mode="Markdown"
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
        await update.message.reply_text(response, parse_mode="Markdown")
        
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(
            f"Image processing went sideways. 📸💥\n\n_{str(e)}_",
            parse_mode="Markdown"
        )


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
# TEXT MESSAGE HANDLER - Main entry point
# ============================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages using the AI-powered conversation engine.
    This is the main handler for all text interactions.
    """
    # Skip if it's a command
    if update.message.text.startswith('/'):
        return
    
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    
    # Track the operation
    tracker.start_operation(
        operation_type=OperationType.ADD_CONTACT.value,
        user_id=user_id,
        command="text_message"
    )
    
    try:
        # Use the AI-powered conversation engine
        response = await process_message(user_id, text)
        await safe_reply(update.message, response)
        tracker.end_operation(success=True)

    except Exception as e:
        print(f"Conversation engine error: {e}")
        import traceback
        traceback.print_exc()
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Something went wrong: {str(e)}")


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
