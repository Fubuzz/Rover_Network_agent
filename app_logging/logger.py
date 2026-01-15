"""
Centralized logging service with structured logging and rotation.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any

from config import LoggingConfig, LOGS_DIR


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data["data"] = record.extra_data
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ReadableFormatter(logging.Formatter):
    """Human-readable log formatter."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = None,
    structured: bool = True
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name.
        log_file: Path to log file (optional).
        level: Logging level (default from config).
        structured: Use JSON structured logging for files.
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    
    # Set level
    if level is None:
        level = getattr(logging, LoggingConfig.LOG_LEVEL, logging.INFO)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Console handler (readable format)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ReadableFormatter())
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler (structured format)
    if log_file:
        LOGS_DIR.mkdir(exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LoggingConfig.MAX_LOG_SIZE,
            backupCount=LoggingConfig.BACKUP_COUNT
        )
        
        if structured:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(ReadableFormatter())
        
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "network_agent") -> logging.Logger:
    """Get a configured logger."""
    return setup_logger(name)


def log_with_data(logger: logging.Logger, level: int, message: str,
                 data: Dict[str, Any] = None):
    """Log a message with additional structured data."""
    record = logger.makeRecord(
        logger.name,
        level,
        "(unknown file)",
        0,
        message,
        (),
        None
    )
    
    if data:
        record.extra_data = data
    
    logger.handle(record)


# Pre-configured loggers
_main_logger: Optional[logging.Logger] = None
_operations_logger: Optional[logging.Logger] = None
_agents_logger: Optional[logging.Logger] = None
_errors_logger: Optional[logging.Logger] = None
_changes_logger: Optional[logging.Logger] = None


def get_main_logger() -> logging.Logger:
    """Get the main application logger."""
    global _main_logger
    if _main_logger is None:
        _main_logger = setup_logger(
            "network_agent",
            LOGS_DIR / "app.log"
        )
    return _main_logger


def get_operations_logger() -> logging.Logger:
    """Get the operations logger."""
    global _operations_logger
    if _operations_logger is None:
        _operations_logger = setup_logger(
            "network_agent.operations",
            LoggingConfig.OPERATIONS_LOG
        )
    return _operations_logger


def get_agents_logger() -> logging.Logger:
    """Get the agents logger."""
    global _agents_logger
    if _agents_logger is None:
        _agents_logger = setup_logger(
            "network_agent.agents",
            LoggingConfig.AGENTS_LOG
        )
    return _agents_logger


def get_errors_logger() -> logging.Logger:
    """Get the errors logger."""
    global _errors_logger
    if _errors_logger is None:
        _errors_logger = setup_logger(
            "network_agent.errors",
            LoggingConfig.ERRORS_LOG
        )
    return _errors_logger


def get_changes_logger() -> logging.Logger:
    """Get the changes logger."""
    global _changes_logger
    if _changes_logger is None:
        _changes_logger = setup_logger(
            "network_agent.changes",
            LoggingConfig.CHANGES_LOG
        )
    return _changes_logger


def configure_all_loggers():
    """Configure all application loggers."""
    get_main_logger()
    get_operations_logger()
    get_agents_logger()
    get_errors_logger()
    get_changes_logger()
