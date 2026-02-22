"""
Telegram callback handler for inline keyboard button presses.
"""

import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CallbackQueryHandler

from handlers.conversation_engine import process_message
from services.message_response import MessageResponse

logger = logging.getLogger('network_agent')


def _build_keyboard(buttons):
    """Build InlineKeyboardMarkup from button list."""
    if not buttons:
        return None
    keyboard = []
    for row in buttons:
        keyboard.append([InlineKeyboardButton(label, callback_data=data) for label, data in row])
    return InlineKeyboardMarkup(keyboard)


async def _safe_reply(message, text: str, reply_markup=None):
    """Send reply, falling back to plain text if Markdown fails."""
    try:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except BadRequest as e:
        if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            try:
                html_text = text
                html_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_text)
                html_text = re.sub(r'\*([^*]+?)\*', r'<b>\1</b>', html_text)
                html_text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+?)_(?![a-zA-Z0-9])', r'<i>\1</i>', html_text)
                await message.reply_text(html_text, parse_mode="HTML", reply_markup=reply_markup)
            except BadRequest:
                plain_text = re.sub(r'[*_`\[\]]', '', text)
                await message.reply_text(plain_text, reply_markup=reply_markup)
        else:
            raise


async def _send_response(query, response):
    """Send a MessageResponse or string as a reply to a callback query."""
    if isinstance(response, MessageResponse):
        markup = _build_keyboard(response.buttons)
        await _safe_reply(query.message, response.text, reply_markup=markup)
    else:
        await _safe_reply(query.message, response)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    data = query.data

    logger.info(f"[CALLBACK] user={user_id} data={data}")

    # Route based on callback_data
    if data == "save":
        response = await process_message(user_id, "done")
        await _send_response(query, response)

    elif data == "cancel":
        response = await process_message(user_id, "cancel")
        await _send_response(query, response)

    elif data.startswith("enrich:"):
        name = data[7:]
        response = await process_message(user_id, f"enrich {name}")
        await _send_response(query, response)

    elif data == "enrich_current":
        response = await process_message(user_id, "enrich")
        await _send_response(query, response)

    elif data == "add_new":
        await _safe_reply(query.message, "Ready for your next contact! Just say _'Add [Name]'_.")

    elif data.startswith("view:"):
        name = data[5:]
        response = await process_message(user_id, f"show {name}")
        await _send_response(query, response)

    elif data == "dismiss":
        # Just acknowledge, remove buttons by not sending new ones
        await query.edit_message_reply_markup(reply_markup=None)

    elif data.startswith("readd:"):
        name = data[6:]
        response = await process_message(user_id, f"add {name}")
        await _send_response(query, response)

    elif data == "undo":
        response = await process_message(user_id, "/undo")
        await _send_response(query, response)

    else:
        logger.warning(f"[CALLBACK] Unknown callback data: {data}")
        await _safe_reply(query.message, "Unknown action.")


def get_callback_handlers():
    """Get callback query handlers."""
    return [
        CallbackQueryHandler(handle_callback),
    ]
