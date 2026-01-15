"""
Telegram handlers for analytics commands.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import json
import io

from interfaces.analytics_interface import get_analytics_interface
from analytics.tracker import get_tracker


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analytics command to show usage analytics."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="view_analytics",
        user_id=user_id,
        command="/analytics"
    )
    
    try:
        analytics = get_analytics_interface()
        
        # Check for subcommand
        if context.args:
            subcommand = context.args[0].lower()
            
            if subcommand == "operations":
                days = int(context.args[1]) if len(context.args) > 1 else 7
                result = analytics.format_operations_analytics(days)
            elif subcommand == "features":
                result = analytics.format_feature_usage()
            elif subcommand == "performance":
                days = int(context.args[1]) if len(context.args) > 1 else 7
                result = analytics.format_performance_report(days)
            elif subcommand == "export":
                days = int(context.args[1]) if len(context.args) > 1 else 30
                data = analytics.export_analytics_data(days)
                
                # Send as JSON file
                json_content = json.dumps(data, indent=2, default=str)
                file_bytes = io.BytesIO(json_content.encode('utf-8'))
                file_bytes.name = "analytics_export.json"
                
                await update.message.reply_document(
                    document=file_bytes,
                    filename="analytics_export.json",
                    caption=f"Analytics export for the last {days} days"
                )
                tracker.end_operation(success=True)
                return
            else:
                result = analytics.format_analytics_summary()
        else:
            result = analytics.format_analytics_summary()
        
        await update.message.reply_text(result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error getting analytics: {str(e)}")


def get_analytics_handlers():
    """Get all analytics-related handlers."""
    return [
        CommandHandler("analytics", analytics_command),
    ]
