"""
Configuration module for Telegram Network Nurturing Agent.
Loads environment variables and provides configuration constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).parent.absolute()
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


class TelegramConfig:
    """Telegram Bot configuration."""
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    BOT_NAME: str = os.getenv("BOT_NAME", "NetworkNurturingBot")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate Telegram configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        return True


class GoogleSheetsConfig:
    """Google Sheets configuration."""
    SHEETS_URL: str = os.getenv("GOOGLE_SHEETS_URL", "")
    CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    
    # Sheet column definitions
    CONTACT_COLUMNS = [
        "Name",
        "Job Title",
        "Company",
        "Phone",
        "Email",
        "LinkedIn URL",
        "Location",
        "Classification",
        "Tags",
        "Notes",
        "Last Contacted",
        "Created Date",
        "Enriched Data",
        "Source"
    ]
    
    @classmethod
    def validate(cls) -> bool:
        """Validate Google Sheets configuration."""
        if not cls.SHEETS_URL:
            raise ValueError("GOOGLE_SHEETS_URL is required")
        return True
    
    @classmethod
    def get_sheet_id(cls) -> Optional[str]:
        """Extract sheet ID from URL."""
        if not cls.SHEETS_URL:
            return None
        # Extract ID from URL like: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
        parts = cls.SHEETS_URL.split("/d/")
        if len(parts) > 1:
            return parts[1].split("/")[0]
        return None


class APIConfig:
    """API Keys configuration."""
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate API configuration. At least one AI API should be configured."""
        if not cls.GEMINI_API_KEY and not cls.OPENAI_API_KEY:
            raise ValueError("At least one of GEMINI_API_KEY or OPENAI_API_KEY is required")
        return True


class AnalyticsConfig:
    """Analytics configuration."""
    DB_PATH: Path = Path(os.getenv("ANALYTICS_DB_PATH", str(LOGS_DIR / "analytics.db")))
    ENABLED: bool = os.getenv("ANALYTICS_ENABLED", "true").lower() == "true"


class LoggingConfig:
    """Logging configuration."""
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    # Log file paths
    OPERATIONS_LOG: Path = LOGS_DIR / "operations.log"
    AGENTS_LOG: Path = LOGS_DIR / "agents.log"
    ERRORS_LOG: Path = LOGS_DIR / "errors.log"
    CHANGES_LOG: Path = LOGS_DIR / "changes.log"
    
    # Log rotation settings
    MAX_LOG_SIZE: int = 10 * 1024 * 1024  # 10 MB
    BACKUP_COUNT: int = 5


class AIConfig:
    """AI model configuration."""
    # OpenAI models
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
    
    # Gemini models
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    # Default model selection (openai or gemini)
    DEFAULT_PROVIDER: str = os.getenv("AI_PROVIDER", "openai")
    DEFAULT_MODEL: str = OPENAI_MODEL if DEFAULT_PROVIDER == "openai" else GEMINI_MODEL
    
    # Model parameters
    TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.7"))
    MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "2000"))


class SMTPConfig:
    """SMTP Email configuration."""
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Network Nurturing Agent")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate SMTP configuration."""
        if not cls.SMTP_USER or not cls.SMTP_PASSWORD:
            return False  # SMTP is optional, so we just return False if not configured
        return True
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if SMTP is properly configured."""
        return bool(cls.SMTP_USER and cls.SMTP_PASSWORD and cls.SMTP_FROM_EMAIL)


class FeatureFlags:
    """Feature flags for enabling/disabling features."""
    AUTO_ENRICH: bool = os.getenv("AUTO_ENRICH_ENABLED", "true").lower() == "true"
    AUTO_CLASSIFY: bool = os.getenv("AUTO_CLASSIFY_ENABLED", "true").lower() == "true"
    VOICE_TRANSCRIPTION: bool = os.getenv("VOICE_TRANSCRIPTION_ENABLED", "true").lower() == "true"
    IMAGE_OCR: bool = os.getenv("IMAGE_OCR_ENABLED", "true").lower() == "true"
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"


class SessionConfig:
    """Session and conversation flow configuration."""
    # Timeout in seconds - prompt user after this much inactivity while collecting
    TIMEOUT_SECONDS: int = int(os.getenv("SESSION_TIMEOUT_SECONDS", "120"))

    # Continuation window - messages within this window are treated as continuation
    CONTINUATION_SECONDS: int = int(os.getenv("SESSION_CONTINUATION_SECONDS", "30"))

    # Memory expiry - user memory expires after this many minutes of inactivity
    MEMORY_EXPIRY_MINUTES: int = int(os.getenv("SESSION_MEMORY_EXPIRY_MINUTES", "60"))

    # Whether to show guided prompts for missing fields
    GUIDED_PROMPTS_ENABLED: bool = os.getenv("GUIDED_PROMPTS_ENABLED", "true").lower() == "true"

    # Maximum prompts to show per contact (to avoid being annoying)
    MAX_PROMPTS_PER_CONTACT: int = int(os.getenv("MAX_PROMPTS_PER_CONTACT", "3"))


class ContactClassification:
    """Contact classification categories."""
    FOUNDER = "founder"
    INVESTOR = "investor"
    ENABLER = "enabler"
    PROFESSIONAL = "professional"
    
    ALL_CATEGORIES = [FOUNDER, INVESTOR, ENABLER, PROFESSIONAL]


def validate_all_configs() -> bool:
    """Validate all required configurations."""
    try:
        TelegramConfig.validate()
        GoogleSheetsConfig.validate()
        APIConfig.validate()
        return True
    except ValueError as e:
        print(f"Configuration Error: {e}")
        return False


def get_config_summary() -> dict:
    """Get a summary of current configuration (for debugging)."""
    return {
        "telegram": {
            "bot_name": TelegramConfig.BOT_NAME,
            "token_configured": bool(TelegramConfig.BOT_TOKEN),
        },
        "google_sheets": {
            "url_configured": bool(GoogleSheetsConfig.SHEETS_URL),
            "sheet_id": GoogleSheetsConfig.get_sheet_id(),
        },
        "apis": {
            "serpapi_configured": bool(APIConfig.SERPAPI_KEY),
            "gemini_configured": bool(APIConfig.GEMINI_API_KEY),
            "openai_configured": bool(APIConfig.OPENAI_API_KEY),
        },
        "smtp": {
            "configured": SMTPConfig.is_configured(),
            "host": SMTPConfig.SMTP_HOST,
            "port": SMTPConfig.SMTP_PORT,
        },
        "analytics": {
            "enabled": AnalyticsConfig.ENABLED,
            "db_path": str(AnalyticsConfig.DB_PATH),
        },
        "logging": {
            "level": LoggingConfig.LOG_LEVEL,
            "debug_mode": LoggingConfig.DEBUG_MODE,
        },
        "features": {
            "auto_enrich": FeatureFlags.AUTO_ENRICH,
            "auto_classify": FeatureFlags.AUTO_CLASSIFY,
            "voice_transcription": FeatureFlags.VOICE_TRANSCRIPTION,
            "image_ocr": FeatureFlags.IMAGE_OCR,
            "email_enabled": FeatureFlags.EMAIL_ENABLED,
        },
        "session": {
            "timeout_seconds": SessionConfig.TIMEOUT_SECONDS,
            "continuation_seconds": SessionConfig.CONTINUATION_SECONDS,
            "memory_expiry_minutes": SessionConfig.MEMORY_EXPIRY_MINUTES,
            "guided_prompts_enabled": SessionConfig.GUIDED_PROMPTS_ENABLED,
        },
    }
