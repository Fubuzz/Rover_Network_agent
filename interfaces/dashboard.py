"""
Real-time dashboard interface.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from data.storage import get_analytics_db
from analytics.performance_monitor import get_performance_monitor
from services.airtable_service import get_sheets_service


class Dashboard:
    """Real-time monitoring dashboard."""
    
    def __init__(self):
        self._db = None
        self._monitor = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = get_performance_monitor()
        return self._monitor
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for the real-time dashboard."""
        # Get system health
        health = self.monitor.get_system_health()
        
        # Get recent activity
        recent_ops = self.db.get_operations(limit=5)
        recent_activity = [
            f"{op['operation_type']}: {op['status']}"
            for op in recent_ops
        ]
        
        # Get contact count
        total_contacts = 0
        try:
            sheets = get_sheets_service()
            stats = sheets.get_contact_stats()
            total_contacts = stats.get("total", 0)
        except:
            pass
        
        # Get today's operations
        from datetime import timedelta
        today_stats = self.db.get_operation_stats(days=1)
        
        return {
            "status": health["status"],
            "total_contacts": total_contacts,
            "operations_today": today_stats.get("total", 0),
            "success_rate": today_stats.get("success_rate", 0),
            "avg_response_time": today_stats.get("avg_duration_ms", 0),
            "recent_activity": recent_activity,
            "alerts": self.monitor.get_alerts(),
            "updated_at": datetime.now().isoformat()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return self.monitor.get_system_health()
    
    def get_recent_activity(self, limit: int = 10) -> list:
        """Get recent activity log."""
        ops = self.db.get_operations(limit=limit)
        
        activity = []
        for op in ops:
            timestamp = datetime.fromisoformat(op['timestamp'])
            activity.append({
                "time": timestamp.strftime("%H:%M:%S"),
                "operation": op['operation_type'],
                "status": op['status'],
                "duration_ms": op.get('duration_ms', 0)
            })
        
        return activity
    
    def format_dashboard(self) -> str:
        """Format dashboard for Telegram display."""
        data = self.get_dashboard_data()
        
        # Status emoji and witty comment
        status = data.get("status", "unknown")
        if status == "healthy":
            status_display = "✅ RUNNING SMOOTHLY"
            status_comment = "_As expected._"
        elif status == "degraded":
            status_display = "⚠️ A LITTLE TIRED"
            status_comment = "_Even I need a coffee break sometimes._"
        else:
            status_display = "❌ HAVING A MOMENT"
            status_comment = "_Don't panic. I've got this._"
        
        lines = [
            "**📊 Command Center**",
            "",
            f"**System Status:** {status_display}",
            status_comment,
            "",
            "**The Numbers:**",
            f"  👥 Network Size: **{data.get('total_contacts', 0)}** contacts",
            f"  📈 Today's Hustle: **{data.get('operations_today', 0)}** operations",
            f"  ✅ Success Rate: **{data.get('success_rate', 0):.1%}**",
            f"  ⚡ Speed: **{data.get('avg_response_time', 0):.0f}ms** avg",
            ""
        ]
        
        # Recent activity
        recent = data.get("recent_activity", [])
        if recent:
            lines.append("**What I've Been Up To:**")
            for activity in recent[:5]:
                lines.append(f"  • {activity}")
            lines.append("")
        
        # Alerts
        alerts = data.get("alerts", [])
        if alerts:
            lines.append("**🚨 Heads Up:**")
            for alert in alerts[:3]:
                lines.append(f"  • {alert.get('message', 'Something needs attention')}")
            lines.append("")
        
        # Last updated with personality
        lines.append(f"_Last checked: {datetime.now().strftime('%H:%M:%S')} • I never sleep._")
        
        return "\n".join(lines)
    
    def get_quick_summary(self) -> str:
        """Get a quick one-line summary."""
        data = self.get_dashboard_data()
        
        status = data.get("status", "unknown")
        contacts = data.get("total_contacts", 0)
        ops_today = data.get("operations_today", 0)
        success_rate = data.get("success_rate", 0)
        
        emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
        
        return f"{emoji} {contacts} contacts | {ops_today} ops today | {success_rate:.0%} success"


# Global instance
_dashboard: Optional[Dashboard] = None


def get_dashboard() -> Dashboard:
    """Get or create dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = Dashboard()
    return _dashboard
