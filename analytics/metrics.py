"""
Metrics collection and calculation for analytics.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from data.storage import get_analytics_db


class MetricsCalculator:
    """Calculates various metrics from analytics data."""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def calculate_success_rate(self, days: int = 7, 
                               operation_type: str = None) -> float:
        """Calculate success rate for operations."""
        operations = self.db.get_operations(
            limit=10000,
            operation_type=operation_type
        )
        
        if not operations:
            return 0.0
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=days)
        recent_ops = [
            op for op in operations
            if datetime.fromisoformat(op['timestamp']) > cutoff
        ]
        
        if not recent_ops:
            return 0.0
        
        success_count = sum(1 for op in recent_ops if op['status'] == 'success')
        return success_count / len(recent_ops)
    
    def calculate_avg_duration(self, days: int = 7,
                               operation_type: str = None) -> float:
        """Calculate average operation duration in milliseconds."""
        operations = self.db.get_operations(
            limit=10000,
            operation_type=operation_type
        )
        
        if not operations:
            return 0.0
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=days)
        recent_ops = [
            op for op in operations
            if datetime.fromisoformat(op['timestamp']) > cutoff
        ]
        
        if not recent_ops:
            return 0.0
        
        total_duration = sum(op.get('duration_ms', 0) for op in recent_ops)
        return total_duration / len(recent_ops)
    
    def calculate_error_rate(self, days: int = 7) -> float:
        """Calculate error rate for operations."""
        success_rate = self.calculate_success_rate(days)
        return 1.0 - success_rate
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        stats = self.db.get_operation_stats(days)
        
        return {
            "total_operations": stats.get("total", 0),
            "success_rate": stats.get("success_rate", 0),
            "error_rate": 1 - stats.get("success_rate", 0),
            "avg_duration_ms": stats.get("avg_duration_ms", 0),
            "max_duration_ms": stats.get("max_duration_ms", 0),
            "operations_per_day": stats.get("total", 0) / max(1, days),
            "period_days": days
        }
    
    def get_operations_by_type(self, days: int = 7) -> Dict[str, int]:
        """Get operation counts by type."""
        operations = self.db.get_operations(limit=10000)
        
        cutoff = datetime.now() - timedelta(days=days)
        type_counts = {}
        
        for op in operations:
            if datetime.fromisoformat(op['timestamp']) > cutoff:
                op_type = op.get('operation_type', 'unknown')
                type_counts[op_type] = type_counts.get(op_type, 0) + 1
        
        return type_counts
    
    def get_hourly_distribution(self, days: int = 7) -> Dict[int, int]:
        """Get operation distribution by hour of day."""
        operations = self.db.get_operations(limit=10000)
        
        cutoff = datetime.now() - timedelta(days=days)
        hourly_counts = {h: 0 for h in range(24)}
        
        for op in operations:
            op_time = datetime.fromisoformat(op['timestamp'])
            if op_time > cutoff:
                hourly_counts[op_time.hour] += 1
        
        return hourly_counts
    
    def get_error_breakdown(self, days: int = 7) -> Dict[str, int]:
        """Get error counts by error type."""
        errors = self.db.get_recent_errors(limit=1000)
        
        cutoff = datetime.now() - timedelta(days=days)
        error_counts = {}
        
        for error in errors:
            error_time = datetime.fromisoformat(error['timestamp'])
            if error_time > cutoff:
                error_type = error.get('error_type', 'unknown')
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return error_counts
    
    def get_agent_metrics(self) -> Dict[str, Dict]:
        """Get performance metrics by agent."""
        return self.db.get_agent_stats()
    
    def get_trend_data(self, days: int = 7) -> List[Dict]:
        """Get daily trend data for the specified period."""
        operations = self.db.get_operations(limit=10000)
        
        cutoff = datetime.now() - timedelta(days=days)
        daily_data = {}
        
        for op in operations:
            op_time = datetime.fromisoformat(op['timestamp'])
            if op_time > cutoff:
                date_key = op_time.date().isoformat()
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        "date": date_key,
                        "total": 0,
                        "success": 0,
                        "failure": 0,
                        "total_duration": 0
                    }
                
                daily_data[date_key]["total"] += 1
                if op['status'] == 'success':
                    daily_data[date_key]["success"] += 1
                else:
                    daily_data[date_key]["failure"] += 1
                daily_data[date_key]["total_duration"] += op.get('duration_ms', 0)
        
        # Calculate averages
        trend = []
        for date_key in sorted(daily_data.keys()):
            data = daily_data[date_key]
            data["avg_duration"] = (
                data["total_duration"] / data["total"] 
                if data["total"] > 0 else 0
            )
            data["success_rate"] = (
                data["success"] / data["total"] 
                if data["total"] > 0 else 0
            )
            trend.append(data)
        
        return trend


# Global instance
_metrics: Optional[MetricsCalculator] = None


def get_metrics() -> MetricsCalculator:
    """Get or create metrics calculator instance."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCalculator()
    return _metrics
