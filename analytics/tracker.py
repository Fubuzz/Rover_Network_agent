"""
Operation tracking service for analytics.
"""

import time
import functools
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from data.storage import get_analytics_db
from data.schema import OperationType, OperationStatus


class OperationTracker:
    """Tracks operations for analytics."""
    
    def __init__(self):
        self._db = None
        self._current_operation: Optional[Dict] = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def start_operation(self, operation_type: str, user_id: str = None,
                       command: str = None, agent_name: str = None,
                       crew_name: str = None, input_data: Dict = None) -> int:
        """Start tracking an operation. Returns operation context."""
        self._current_operation = {
            "operation_type": operation_type,
            "start_time": time.time(),
            "user_id": user_id,
            "command": command,
            "agent_name": agent_name,
            "crew_name": crew_name,
            "input_data": input_data
        }
        return id(self._current_operation)
    
    def end_operation(self, success: bool = True, output_data: Dict = None,
                     error_message: str = None, error_type: str = None) -> int:
        """End the current operation and record it."""
        if not self._current_operation:
            return -1
        
        duration_ms = int((time.time() - self._current_operation["start_time"]) * 1000)
        status = OperationStatus.SUCCESS.value if success else OperationStatus.FAILURE.value
        
        operation_id = self.db.record_operation(
            operation_type=self._current_operation["operation_type"],
            status=status,
            duration_ms=duration_ms,
            agent_name=self._current_operation.get("agent_name"),
            crew_name=self._current_operation.get("crew_name"),
            user_id=self._current_operation.get("user_id"),
            command=self._current_operation.get("command"),
            error_message=error_message,
            error_type=error_type,
            input_data=self._current_operation.get("input_data"),
            output_data=output_data
        )
        
        # Track feature usage
        if self._current_operation.get("command"):
            self.db.record_feature_usage(
                feature_name=self._current_operation["command"],
                user_id=self._current_operation.get("user_id"),
                success=success
            )
        
        self._current_operation = None
        return operation_id
    
    def record_quick_operation(self, operation_type: str, success: bool,
                              duration_ms: int = 0, user_id: str = None,
                              command: str = None, error_message: str = None) -> int:
        """Record a quick operation without start/end lifecycle."""
        status = OperationStatus.SUCCESS.value if success else OperationStatus.FAILURE.value
        
        operation_id = self.db.record_operation(
            operation_type=operation_type,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
            command=command,
            error_message=error_message
        )
        
        if command:
            self.db.record_feature_usage(
                feature_name=command,
                user_id=user_id,
                success=success
            )
        
        return operation_id
    
    def get_operation_history(self, limit: int = 100, 
                             status: str = None) -> list:
        """Get operation history."""
        return self.db.get_operations(limit=limit, status=status)
    
    def get_stats(self, days: int = 7) -> Dict:
        """Get operation statistics."""
        return self.db.get_operation_stats(days=days)


def track_operation(operation_type: str, command: str = None):
    """
    Decorator to automatically track operations.
    
    Usage:
        @track_operation(OperationType.ADD_CONTACT, "/add")
        async def add_contact_handler(update, context):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = get_tracker()
            user_id = None
            
            # Try to extract user_id from Telegram update
            if args and hasattr(args[0], 'effective_user'):
                user_id = str(args[0].effective_user.id)
            
            tracker.start_operation(
                operation_type=operation_type,
                user_id=user_id,
                command=command
            )
            
            try:
                result = await func(*args, **kwargs)
                tracker.end_operation(success=True)
                return result
            except Exception as e:
                tracker.end_operation(
                    success=False,
                    error_message=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracker = get_tracker()
            tracker.start_operation(operation_type=operation_type, command=command)
            
            try:
                result = func(*args, **kwargs)
                tracker.end_operation(success=True)
                return result
            except Exception as e:
                tracker.end_operation(
                    success=False,
                    error_message=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Global tracker instance
_tracker: Optional[OperationTracker] = None


def get_tracker() -> OperationTracker:
    """Get or create operation tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = OperationTracker()
    return _tracker
