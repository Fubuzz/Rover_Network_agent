"""
Telegram handlers for evaluation commands.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from interfaces.evaluation_interface import get_evaluation_interface
from interfaces.dashboard import get_dashboard
from analytics.tracker import get_tracker


async def eval_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /eval command to show evaluation statistics."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="view_evaluation",
        user_id=user_id,
        command="/eval"
    )
    
    try:
        evaluation = get_evaluation_interface()
        
        # Check for subcommand
        if context.args:
            subcommand = context.args[0].lower()
            days = int(context.args[1]) if len(context.args) > 1 else 7
            
            if subcommand == "operations":
                summary = evaluation.get_operation_summary(days)
                
                lines = [
                    "**Operations Evaluation**",
                    f"_Period: Last {days} days_",
                    "",
                    f"**Total Operations:** {summary.get('total', 0)}",
                    f"**Successful:** {summary['by_status'].get('success', 0)}",
                    f"**Failed:** {summary['by_status'].get('failure', 0)}",
                    ""
                ]
                
                by_type = summary.get("by_type", {})
                if by_type:
                    lines.append("**By Type:**")
                    for op_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"  {op_type}: {count}")
                
                result = "\n".join(lines)
                
            elif subcommand == "errors":
                errors = evaluation.get_error_summary(days)
                
                lines = [
                    "**Error Analysis**",
                    f"_Period: Last {days} days_",
                    "",
                    f"**Total Errors:** {errors.get('total', 0)}",
                    f"**Unresolved:** {errors.get('unresolved', 0)}",
                    ""
                ]
                
                by_type = errors.get("by_type", {})
                if by_type:
                    lines.append("**By Error Type:**")
                    for error_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"  {error_type}: {count}")
                
                result = "\n".join(lines)
                
            elif subcommand == "quality":
                quality = evaluation.get_data_quality_metrics()
                
                if "error" in quality:
                    result = f"Error getting quality metrics: {quality['error']}"
                else:
                    result = "\n".join([
                        "**Data Quality Metrics**",
                        "",
                        f"**Total Contacts:** {quality.get('total_contacts', 0)}",
                        f"**Completeness:** {quality.get('completeness', 0):.1%}",
                        "",
                        "**Field Coverage:**",
                        f"  With Email: {quality.get('with_email', 0)}",
                        f"  With Phone: {quality.get('with_phone', 0)}",
                        f"  With LinkedIn: {quality.get('with_linkedin', 0)}"
                    ])
                
            elif subcommand == "agents":
                agents = evaluation.get_agent_evaluation()
                
                lines = ["**Agent Performance Evaluation**", ""]
                
                for agent_name, metrics in agents.items():
                    lines.append(f"**{agent_name}:**")
                    lines.append(f"  Actions: {metrics.get('total_actions', 0)}")
                    lines.append(f"  Success Rate: {metrics.get('success_rate', 0):.1%}")
                    lines.append(f"  Avg Duration: {metrics.get('avg_duration_ms', 0):.0f}ms")
                    lines.append(f"  Status: {metrics.get('performance', 'unknown')}")
                    lines.append("")
                
                result = "\n".join(lines) if agents else "No agent activity recorded yet."
            else:
                result = evaluation.format_evaluation_summary(days)
        else:
            result = evaluation.format_evaluation_summary()
        
        await update.message.reply_text(result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Error getting evaluation: {str(e)}")


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dashboard command to show real-time dashboard."""
    tracker = get_tracker()
    user_id = str(update.effective_user.id)
    
    tracker.start_operation(
        operation_type="view_dashboard",
        user_id=user_id,
        command="/dashboard"
    )
    
    try:
        dashboard = get_dashboard()
        result = dashboard.format_dashboard()
        
        intro = "Here's how things are running. _Spoiler: I'm doing great._ 💅\n\n"
        await update.message.reply_text(intro + result, parse_mode="Markdown")
        tracker.end_operation(success=True)
        
    except Exception as e:
        tracker.end_operation(success=False, error_message=str(e))
        await update.message.reply_text(f"Dashboard crashed. Even I'm not perfect. 📊💥\n\n_{str(e)}_", parse_mode="Markdown")


def get_evaluation_handlers():
    """Get all evaluation-related handlers."""
    return [
        CommandHandler("eval", eval_command),
        CommandHandler("dashboard", dashboard_command),
    ]
