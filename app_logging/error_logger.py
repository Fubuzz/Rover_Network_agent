"""
Error logging with stack traces.
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List

from .logger import get_errors_logger, log_with_data
from data.storage import get_analytics_db


class ErrorLogger:
    """Comprehensive error logging."""
    
    def __init__(self):
        self._logger = None
        self._db = None
    
    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_errors_logger()
        return self._logger
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def log_error(self, error_type: str, error_message: str,
                 operation_id: int = None, agent_name: str = None,
                 context: Dict = None) -> int:
        """Log an error and return error ID."""
        data = {
            "event": "error",
            "error_type": error_type,
            "error_message": error_message,
            "operation_id": operation_id,
            "agent_name": agent_name,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.ERROR,
            f"Error [{error_type}]: {error_message}",
            data
        )
        
        # Record to database
        error_id = self.db.record_error(
            error_type=error_type,
            error_message=error_message,
            operation_id=operation_id,
            agent_name=agent_name
        )
        
        return error_id
    
    def log_exception(self, exception: Exception, operation_id: int = None,
                     agent_name: str = None, context: Dict = None) -> int:
        """Log an exception with full stack trace."""
        error_type = type(exception).__name__
        error_message = str(exception)
        stack_trace = traceback.format_exc()
        
        data = {
            "event": "exception",
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "operation_id": operation_id,
            "agent_name": agent_name,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.ERROR,
            f"Exception [{error_type}]: {error_message}",
            data
        )
        
        # Record to database
        error_id = self.db.record_error(
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            operation_id=operation_id,
            agent_name=agent_name
        )
        
        return error_id
    
    def get_error_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get error summary for the specified period."""
        errors = self.db.get_recent_errors(limit=1000)
        
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
            "total_errors": len(recent_errors),
            "unresolved_count": unresolved,
            "by_type": by_type,
            "by_agent": by_agent,
            "recent": recent_errors[:10],
            "period_days": days
        }
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns."""
        summary = self.get_error_summary(days=30)
        
        # Find most common errors
        most_common = sorted(
            summary["by_type"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Find agents with most errors
        problem_agents = sorted(
            summary["by_agent"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        return {
            "most_common_errors": most_common,
            "problem_agents": problem_agents,
            "error_rate_trend": "increasing" if summary["total_errors"] > 50 else "stable",
            "recommendations": self._generate_recommendations(summary)
        }
    
    def _generate_recommendations(self, summary: Dict) -> List[str]:
        """Generate recommendations based on error analysis."""
        recommendations = []
        
        if summary["unresolved_count"] > 10:
            recommendations.append("Review and resolve unresolved errors")
        
        for error_type, count in summary["by_type"].items():
            if count > 20:
                recommendations.append(f"Investigate frequent {error_type} errors")
        
        if not recommendations:
            recommendations.append("Error rate is within acceptable limits")
        
        return recommendations
    
    def resolve_error(self, error_id: int, resolution: str):
        """Mark an error as resolved."""
        self.db.resolve_error(error_id, resolution)
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Error {error_id} resolved: {resolution}",
            {"error_id": error_id, "resolution": resolution}
        )


# Global instance
_error_logger: Optional[ErrorLogger] = None


def get_error_logger() -> ErrorLogger:
    """Get or create error logger instance."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger
