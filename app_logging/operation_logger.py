"""
Operation-specific logging.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from .logger import get_operations_logger, log_with_data


class OperationLogger:
    """Logs operation lifecycle events."""
    
    def __init__(self):
        self._logger = None
    
    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_operations_logger()
        return self._logger
    
    def log_operation_start(self, operation_type: str, user_id: str = None,
                           command: str = None, input_data: Dict = None):
        """Log the start of an operation."""
        data = {
            "event": "operation_start",
            "operation_type": operation_type,
            "user_id": user_id,
            "command": command,
            "input_data": input_data,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Operation started: {operation_type}",
            data
        )
    
    def log_operation_progress(self, operation_type: str, step: str,
                               details: Dict = None):
        """Log progress during an operation."""
        data = {
            "event": "operation_progress",
            "operation_type": operation_type,
            "step": step,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.DEBUG,
            f"Operation progress: {operation_type} - {step}",
            data
        )
    
    def log_operation_complete(self, operation_type: str, duration_ms: int,
                               result: Dict = None):
        """Log successful completion of an operation."""
        data = {
            "event": "operation_complete",
            "operation_type": operation_type,
            "duration_ms": duration_ms,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Operation completed: {operation_type} ({duration_ms}ms)",
            data
        )
    
    def log_operation_failure(self, operation_type: str, error_message: str,
                              error_type: str = None, duration_ms: int = 0):
        """Log operation failure."""
        data = {
            "event": "operation_failure",
            "operation_type": operation_type,
            "error_message": error_message,
            "error_type": error_type,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.ERROR,
            f"Operation failed: {operation_type} - {error_message}",
            data
        )


# Global instance
_operation_logger: Optional[OperationLogger] = None


def get_operation_logger() -> OperationLogger:
    """Get or create operation logger instance."""
    global _operation_logger
    if _operation_logger is None:
        _operation_logger = OperationLogger()
    return _operation_logger
