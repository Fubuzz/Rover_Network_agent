"""
Performance monitoring service.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import time

from data.storage import get_analytics_db
from utils.constants import METRICS


class PerformanceMonitor:
    """Monitors system performance and health."""
    
    def __init__(self):
        self._db = None
        self._api_usage = {
            "openai": {"count": 0, "last_reset": datetime.now()},
            "gemini": {"count": 0, "last_reset": datetime.now()},
            "serpapi": {"count": 0, "last_reset": datetime.now()}
        }
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def track_api_call(self, api_name: str, duration_ms: int = 0,
                      success: bool = True):
        """Track an API call."""
        if api_name in self._api_usage:
            self._api_usage[api_name]["count"] += 1
    
    def get_api_usage(self) -> Dict[str, Dict]:
        """Get current API usage statistics."""
        return {
            name: {
                "calls": data["count"],
                "since": data["last_reset"].isoformat()
            }
            for name, data in self._api_usage.items()
        }
    
    def reset_api_usage(self, api_name: str = None):
        """Reset API usage counters."""
        if api_name and api_name in self._api_usage:
            self._api_usage[api_name] = {
                "count": 0,
                "last_reset": datetime.now()
            }
        else:
            for name in self._api_usage:
                self._api_usage[name] = {
                    "count": 0,
                    "last_reset": datetime.now()
                }
    
    def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics for the specified period."""
        stats = self.db.get_operation_stats(days=1)
        
        return {
            "success_rate": stats.get("success_rate", 0),
            "avg_response_time_ms": stats.get("avg_duration_ms", 0),
            "max_response_time_ms": stats.get("max_duration_ms", 0),
            "total_operations": stats.get("total", 0),
            "error_count": stats.get("failure", 0)
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        stats = self.get_performance_stats()
        
        # Determine health status
        success_rate = stats.get("success_rate", 0)
        avg_response = stats.get("avg_response_time_ms", 0)
        
        health_status = "healthy"
        issues = []
        
        if success_rate < METRICS["success_rate_threshold"]:
            health_status = "degraded" if success_rate > 0.7 else "critical"
            issues.append(f"Low success rate: {success_rate:.1%}")
        
        if avg_response > METRICS["avg_response_time_threshold"]:
            if health_status == "healthy":
                health_status = "degraded"
            issues.append(f"High response time: {avg_response:.0f}ms")
        
        return {
            "status": health_status,
            "issues": issues,
            "metrics": stats,
            "api_usage": self.get_api_usage(),
            "checked_at": datetime.now().isoformat()
        }
    
    def get_alerts(self) -> List[Dict]:
        """Get active performance alerts."""
        alerts = []
        health = self.get_system_health()
        
        if health["status"] != "healthy":
            for issue in health["issues"]:
                alerts.append({
                    "type": "performance",
                    "severity": health["status"],
                    "message": issue,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Check for recent errors
        recent_errors = self.db.get_recent_errors(limit=10)
        unresolved_errors = [e for e in recent_errors if not e.get("resolved")]
        
        if len(unresolved_errors) >= 5:
            alerts.append({
                "type": "errors",
                "severity": "warning",
                "message": f"{len(unresolved_errors)} unresolved errors",
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def monitor_performance(self) -> Dict[str, Any]:
        """Run a full performance monitoring check."""
        return {
            "health": self.get_system_health(),
            "alerts": self.get_alerts(),
            "api_status": self.get_api_usage(),
            "monitored_at": datetime.now().isoformat()
        }


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str = None):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.duration_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        return False


# Global instance
_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor
