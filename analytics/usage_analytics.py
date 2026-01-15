"""
Usage analytics service.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from data.storage import get_analytics_db


class UsageAnalytics:
    """Tracks and analyzes feature usage patterns."""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def track_feature_usage(self, feature_name: str, user_id: str = None,
                           success: bool = True):
        """Track usage of a feature."""
        self.db.record_feature_usage(
            feature_name=feature_name,
            user_id=user_id,
            success=success
        )
    
    def get_feature_stats(self) -> Dict[str, int]:
        """Get overall feature usage statistics."""
        return self.db.get_feature_usage_stats()
    
    def get_top_features(self, limit: int = 10) -> List[Dict]:
        """Get top used features."""
        stats = self.db.get_feature_usage_stats()
        
        sorted_features = sorted(
            stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {"feature": name, "usage_count": count}
            for name, count in sorted_features
        ]
    
    def get_user_patterns(self, days: int = 7) -> Dict[str, Any]:
        """Get user usage patterns."""
        operations = self.db.get_operations(limit=10000)
        
        cutoff = datetime.now() - timedelta(days=days)
        
        user_ops = {}
        hourly_ops = {h: 0 for h in range(24)}
        daily_ops = {}
        
        for op in operations:
            op_time = datetime.fromisoformat(op['timestamp'])
            if op_time > cutoff:
                # User stats
                user_id = op.get('user_id', 'unknown')
                user_ops[user_id] = user_ops.get(user_id, 0) + 1
                
                # Hourly distribution
                hourly_ops[op_time.hour] += 1
                
                # Daily distribution
                day_name = op_time.strftime('%A')
                daily_ops[day_name] = daily_ops.get(day_name, 0) + 1
        
        # Find peak hours
        peak_hour = max(hourly_ops, key=hourly_ops.get) if hourly_ops else 0
        
        return {
            "total_users": len(user_ops),
            "operations_by_user": user_ops,
            "hourly_distribution": hourly_ops,
            "daily_distribution": daily_ops,
            "peak_hour": peak_hour,
            "avg_operations_per_user": (
                sum(user_ops.values()) / len(user_ops) 
                if user_ops else 0
            )
        }
    
    def get_operation_frequency(self, days: int = 7) -> Dict[str, Any]:
        """Get operation frequency analytics."""
        operations = self.db.get_operations(limit=10000)
        
        cutoff = datetime.now() - timedelta(days=days)
        
        op_types = {}
        total_ops = 0
        
        for op in operations:
            op_time = datetime.fromisoformat(op['timestamp'])
            if op_time > cutoff:
                total_ops += 1
                op_type = op.get('operation_type', 'unknown')
                op_types[op_type] = op_types.get(op_type, 0) + 1
        
        return {
            "total_operations": total_ops,
            "operations_per_day": total_ops / max(1, days),
            "by_type": op_types,
            "most_common": max(op_types, key=op_types.get) if op_types else None
        }
    
    def generate_usage_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate a comprehensive usage report."""
        feature_stats = self.get_feature_stats()
        top_features = self.get_top_features()
        user_patterns = self.get_user_patterns(days)
        op_frequency = self.get_operation_frequency(days)
        
        return {
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "features": {
                "total_features_used": len(feature_stats),
                "top_features": top_features,
                "all_features": feature_stats
            },
            "users": {
                "total_active": user_patterns["total_users"],
                "avg_operations_per_user": user_patterns["avg_operations_per_user"]
            },
            "patterns": {
                "peak_hour": user_patterns["peak_hour"],
                "hourly_distribution": user_patterns["hourly_distribution"]
            },
            "operations": op_frequency
        }


# Global instance
_usage_analytics: Optional[UsageAnalytics] = None


def get_usage_analytics() -> UsageAnalytics:
    """Get or create usage analytics instance."""
    global _usage_analytics
    if _usage_analytics is None:
        _usage_analytics = UsageAnalytics()
    return _usage_analytics
