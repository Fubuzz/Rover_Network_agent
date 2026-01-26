"""
Main entry point for the Telegram Network Nurturing Agent.
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes

from config import (
    TelegramConfig, 
    validate_all_configs, 
    get_config_summary,
    LoggingConfig
)
from app_logging.logger import configure_all_loggers, get_main_logger
from app_logging.change_logger import get_change_logger
from data.storage import get_analytics_db
from services.airtable_service import get_sheets_service

# Import handlers
from handlers.contact_handlers import get_contact_handlers
from handlers.enrichment_handlers import get_enrichment_handlers
from handlers.report_handlers import get_report_handlers
from handlers.matchmaker_handlers import get_matchmaker_handlers
from handlers.outreach_handlers import get_outreach_handlers
from handlers.input_handlers import get_input_handlers
from handlers.analytics_handlers import get_analytics_handlers
from handlers.evaluation_handlers import get_evaluation_handlers
from handlers.conversation_handlers import get_conversation_handlers


def setup_logging():
    """Set up logging for the application."""
    # Configure Python's root logger
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, LoggingConfig.LOG_LEVEL)
    )
    
    # Set up our custom loggers
    configure_all_loggers()
    
    return get_main_logger()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot."""
    logger = get_main_logger()
    
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Log to error logger
    from app_logging.error_logger import get_error_logger
    error_logger = get_error_logger()
    error_logger.log_exception(
        context.error,
        agent_name="telegram_bot",
        context={"update": str(update) if update else None}
    )
    
    # Notify user if possible
    if update and hasattr(update, 'message') and update.message:
        try:
            await update.message.reply_text(
                "An error occurred while processing your request. "
                "Please try again or contact support if the issue persists."
            )
        except:
            pass


async def post_init(application: Application):
    """Post-initialization callback."""
    logger = get_main_logger()
    logger.info("Bot initialized successfully")
    
    # Initialize services
    try:
        # Initialize Google Sheets
        sheets = get_sheets_service()
        if sheets.initialize():
            logger.info("Google Sheets service initialized")
        else:
            logger.warning("Google Sheets service failed to initialize - check credentials")
    except Exception as e:
        logger.warning(f"Could not initialize Google Sheets: {e}")
    
    # Initialize analytics database
    try:
        db = get_analytics_db()
        logger.info("Analytics database initialized")
    except Exception as e:
        logger.warning(f"Could not initialize analytics database: {e}")
    
    # Log initial feature set
    change_logger = get_change_logger()
    change_logger.log_feature_add(
        feature_name="Telegram Network Agent",
        description="Initial release with contact management, enrichment, classification, and analytics",
        version="1.0.0",
        author="System",
        files_changed=["main.py", "config.py", "handlers/*", "services/*", "agents/*", "crews/*"]
    )


def main():
    """Main function to run the bot."""
    # Set up logging
    logger = setup_logging()
    logger.info("Starting Telegram Network Nurturing Agent...")
    
    # Validate configuration
    try:
        validate_all_configs()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nConfiguration Error: {e}")
        print("Please check your .env file and ensure all required values are set.")
        return
    
    # Print config summary in debug mode
    if LoggingConfig.DEBUG_MODE:
        summary = get_config_summary()
        logger.debug(f"Configuration: {summary}")
    
    # Create the Application
    application = Application.builder().token(TelegramConfig.BOT_TOKEN).post_init(post_init).build()
    
    # Register all handlers
    logger.info("Registering handlers...")
    
    # Contact management handlers
    for handler in get_contact_handlers():
        application.add_handler(handler)
    
    # Enrichment handlers
    for handler in get_enrichment_handlers():
        application.add_handler(handler)
    
    # Report handlers
    for handler in get_report_handlers():
        application.add_handler(handler)

    # Matchmaker handlers
    for handler in get_matchmaker_handlers():
        application.add_handler(handler)

    # Outreach handlers
    for handler in get_outreach_handlers():
        application.add_handler(handler)

    # Analytics handlers
    for handler in get_analytics_handlers():
        application.add_handler(handler)
    
    # Evaluation handlers
    for handler in get_evaluation_handlers():
        application.add_handler(handler)
    
    # Conversation/help handlers
    for handler in get_conversation_handlers():
        application.add_handler(handler)
    
    # Input handlers (voice, image, text) - should be last
    for handler in get_input_handlers():
        application.add_handler(handler)
    
    # Error handler
    application.add_error_handler(error_handler)
    
    logger.info("All handlers registered")
    logger.info(f"Bot is starting... (@{TelegramConfig.BOT_NAME})")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
