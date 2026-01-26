"""
Evaluation and testing interface for viewing stats and metrics.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from data.storage import get_analytics_db
from analytics.metrics import get_metrics
from analytics.usage_analytics import get_usage_analytics
from utils.formatters import format_evaluation_report


class EvaluationInterface:
    """Interface for evaluation and testing metrics."""
    
    def __init__(self):
        self._db = None
        self._metrics = None
        self._usage = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    @property
    def metrics(self):
        if self._metrics is None:
            self._metrics = get_metrics()
        return self._metrics
    
    @property
    def usage(self):
        if self._usage is None:
            self._usage = get_usage_analytics()
        return self._usage
    
    def get_evaluation_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get overall evaluation statistics."""
        op_stats = self.db.get_operation_stats(days)
        agent_stats = self.db.get_agent_stats()
        errors = self.db.get_recent_errors(limit=10)
        
        return {
            "period_days": days,
            "operations": {
                "total": op_stats.get("total", 0),
                "success": op_stats.get("success", 0),
                "failure": op_stats.get("failure", 0),
                "success_rate": op_stats.get("success_rate", 0),
                "avg_duration_ms": op_stats.get("avg_duration_ms", 0)
            },
            "agents": agent_stats,
            "recent_errors": errors[:5],
            "error_count": len([e for e in errors if not e.get("resolved")])
        }
    
    def get_operation_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get operation summary with breakdown by type."""
        operations = self.db.get_operations(limit=1000)
        
        by_type = {}
        by_status = {"success": 0, "failure": 0}
        
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        for op in operations:
            op_time = datetime.fromisoformat(op['timestamp'])
            if op_time > cutoff:
                op_type = op.get('operation_type', 'unknown')
                by_type[op_type] = by_type.get(op_type, 0) + 1
                
                status = op.get('status', 'unknown')
                if status in by_status:
                    by_status[status] += 1
        
        return {
            "period_days": days,
            "by_type": by_type,
            "by_status": by_status,
            "total": sum(by_type.values())
        }
    
    def get_error_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get error summary with patterns."""
        errors = self.db.get_recent_errors(limit=500)
        
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        recent_errors = []
        by_type = {}
        by_agent = {}
        unresolved = 0
        
        for error in errors:
            error_time = datetime.fromisoformat(error['timestamp'])
            if error_time > cutoff:
                recent_errors.append(error)
                
                error_type = error.get('error_type', 'unknown')
                by_type[error_type] = by_type.get(error_type, 0) + 1
                
                agent = error.get('agent_name')
                if agent:
                    by_agent[agent] = by_agent.get(agent, 0) + 1
                
                if not error.get('resolved'):
                    unresolved += 1
        
        return {
            "period_days": days,
            "total": len(recent_errors),
            "unresolved": unresolved,
            "by_type": by_type,
            "by_agent": by_agent,
            "recent": recent_errors[:10]
        }
    
    def get_data_quality_metrics(self) -> Dict[str, Any]:
        """Get data quality metrics from recent operations."""
        from services.airtable_service import get_sheets_service
        
        try:
            sheets = get_sheets_service()
            stats = sheets.get_contact_stats()
            
            total = stats.get("total", 0)
            if total == 0:
                return {"total_contacts": 0, "completeness": 0}
            
            # Calculate completeness
            with_email = stats.get("with_email", 0)
            with_phone = stats.get("with_phone", 0)
            with_linkedin = stats.get("with_linkedin", 0)
            
            completeness = (with_email + with_phone + with_linkedin) / (total * 3)
            
            return {
                "total_contacts": total,
                "completeness": completeness,
                "with_email": with_email,
                "with_phone": with_phone,
                "with_linkedin": with_linkedin,
                "by_classification": stats.get("by_classification", {})
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_agent_evaluation(self) -> Dict[str, Any]:
        """Get agent performance evaluation."""
        agent_stats = self.db.get_agent_stats()
        
        evaluation = {}
        for agent_name, stats in agent_stats.items():
            evaluation[agent_name] = {
                "total_actions": stats.get("total", 0),
                "success_rate": stats.get("success_rate", 0),
                "avg_duration_ms": stats.get("avg_duration_ms", 0),
                "performance": "good" if stats.get("success_rate", 0) > 0.9 else "needs_improvement"
            }
        
        return evaluation
    
    def format_evaluation_summary(self, days: int = 7) -> str:
        """Format evaluation summary for Telegram display - Donna style."""
        stats = self.get_evaluation_stats(days)
        
        success_rate = stats['operations']['success_rate']
        
        # Witty commentary based on performance
        if success_rate >= 0.95:
            commentary = "_Basically perfect. As expected._ 💅"
        elif success_rate >= 0.85:
            commentary = "_Pretty solid. Room for improvement, but I won't complain._"
        elif success_rate >= 0.70:
            commentary = "_We've had better days. Let's fix this._"
        else:
            commentary = "_Okay, we need to talk about what's going wrong here._ 😬"
        
        lines = [
            "**📋 Performance Review**",
            f"_Last {days} days_",
            "",
            commentary,
            "",
            "**The Numbers:**",
            f"  📊 Total Operations: **{stats['operations']['total']}**",
            f"  ✅ Success Rate: **{stats['operations']['success_rate']:.1%}**",
            f"  ⚡ Avg Speed: **{stats['operations']['avg_duration_ms']:.0f}ms**",
            ""
        ]
        
        if stats.get("agents"):
            lines.append("**Agent Report Card:**")
            for agent, agent_stats in stats["agents"].items():
                rate = agent_stats.get('success_rate', 0)
                grade = "🌟" if rate >= 0.9 else "👍" if rate >= 0.7 else "🔧"
                lines.append(f"  {grade} {agent}: {rate:.1%}")
            lines.append("")
        
        error_count = stats.get("error_count", 0)
        if error_count > 0:
            lines.append(f"**🚨 Outstanding Issues:** {error_count}")
            lines.append("_Use `/eval errors` for details_")
        else:
            lines.append("**✨ No outstanding issues!**")
        
        return "\n".join(lines)


# Global instance
_evaluation_interface: Optional[EvaluationInterface] = None


def get_evaluation_interface() -> EvaluationInterface:
    """Get or create evaluation interface instance."""
    global _evaluation_interface
    if _evaluation_interface is None:
        _evaluation_interface = EvaluationInterface()
    return _evaluation_interface
