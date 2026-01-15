"""
Analytics interface for viewing usage and performance metrics.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from analytics.metrics import get_metrics
from analytics.usage_analytics import get_usage_analytics
from analytics.performance_monitor import get_performance_monitor
from data.storage import get_analytics_db


class AnalyticsInterface:
    """Interface for analytics and usage data."""
    
    def __init__(self):
        self._metrics = None
        self._usage = None
        self._monitor = None
        self._db = None
    
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
    
    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = get_performance_monitor()
        return self._monitor
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def get_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics."""
        return self.usage.generate_usage_report(days)
    
    def get_feature_usage(self) -> Dict[str, int]:
        """Get feature usage statistics."""
        return self.usage.get_feature_stats()
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics."""
        return self.metrics.get_performance_metrics(days)
    
    def get_operations_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get operations analytics."""
        op_stats = self.db.get_operation_stats(days)
        by_type = self.metrics.get_operations_by_type(days)
        
        return {
            "summary": op_stats,
            "by_type": by_type,
            "period_days": days
        }
    
    def export_analytics_data(self, days: int = 30) -> Dict[str, Any]:
        """Export comprehensive analytics data."""
        return {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "usage": self.get_usage_stats(days),
            "performance": self.get_performance_metrics(days),
            "operations": self.get_operations_analytics(days),
            "features": self.get_feature_usage()
        }
    
    def format_analytics_summary(self, days: int = 7) -> str:
        """Format analytics summary for Telegram display."""
        usage = self.get_usage_stats(days)
        perf = self.get_performance_metrics(days)
        
        lines = [
            "**Analytics Dashboard**",
            f"_Period: Last {days} days_",
            "",
            "**Usage:**",
            f"  Total Operations: {usage['operations']['total_operations']}",
            f"  Operations/Day: {usage['operations']['operations_per_day']:.1f}",
            ""
        ]
        
        # Top features
        features = usage.get("features", {}).get("top_features", [])
        if features:
            lines.append("**Top Features:**")
            for f in features[:5]:
                lines.append(f"  {f['feature']}: {f['usage_count']} uses")
            lines.append("")
        
        # Performance
        lines.extend([
            "**Performance:**",
            f"  Success Rate: {perf.get('success_rate', 0):.1%}",
            f"  Avg Response: {perf.get('avg_duration_ms', 0):.0f}ms"
        ])
        
        return "\n".join(lines)
    
    def format_operations_analytics(self, days: int = 7) -> str:
        """Format operations analytics for Telegram display."""
        ops = self.get_operations_analytics(days)
        summary = ops.get("summary", {})
        by_type = ops.get("by_type", {})
        
        lines = [
            "**Operations Analytics**",
            f"_Period: Last {days} days_",
            "",
            f"**Total:** {summary.get('total', 0)}",
            f"**Success:** {summary.get('success', 0)}",
            f"**Failed:** {summary.get('failure', 0)}",
            f"**Success Rate:** {summary.get('success_rate', 0):.1%}",
            ""
        ]
        
        if by_type:
            lines.append("**By Type:**")
            for op_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  {op_type}: {count}")
        
        return "\n".join(lines)
    
    def format_feature_usage(self) -> str:
        """Format feature usage for Telegram display."""
        features = self.get_feature_usage()
        
        lines = ["**Feature Usage**", ""]
        
        if features:
            sorted_features = sorted(features.items(), key=lambda x: x[1], reverse=True)
            for feature, count in sorted_features[:10]:
                lines.append(f"  {feature}: {count} uses")
        else:
            lines.append("No feature usage recorded yet.")
        
        return "\n".join(lines)
    
    def format_performance_report(self, days: int = 7) -> str:
        """Format performance report for Telegram display."""
        perf = self.get_performance_metrics(days)
        health = self.monitor.get_system_health()
        
        status_emoji = "✅" if health["status"] == "healthy" else "⚠️" if health["status"] == "degraded" else "❌"
        
        lines = [
            "**Performance Report**",
            f"_Period: Last {days} days_",
            "",
            f"**System Status:** {status_emoji} {health['status'].upper()}",
            "",
            f"**Metrics:**",
            f"  Total Operations: {perf.get('total_operations', 0)}",
            f"  Success Rate: {perf.get('success_rate', 0):.1%}",
            f"  Avg Duration: {perf.get('avg_duration_ms', 0):.0f}ms",
            f"  Max Duration: {perf.get('max_duration_ms', 0):.0f}ms"
        ]
        
        if health.get("issues"):
            lines.append("")
            lines.append("**Issues:**")
            for issue in health["issues"]:
                lines.append(f"  ⚠️ {issue}")
        
        return "\n".join(lines)


# Global instance
_analytics_interface: Optional[AnalyticsInterface] = None


def get_analytics_interface() -> AnalyticsInterface:
    """Get or create analytics interface instance."""
    global _analytics_interface
    if _analytics_interface is None:
        _analytics_interface = AnalyticsInterface()
    return _analytics_interface
