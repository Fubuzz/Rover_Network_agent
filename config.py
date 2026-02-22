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


class AirtableConfig:
    """Airtable configuration."""
    AIRTABLE_PAT: str = os.getenv("AIRTABLE_PAT", "")
    AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")
    AIRTABLE_CONTACTS_TABLE: str = os.getenv("AIRTABLE_CONTACTS_TABLE", "Contacts")
    AIRTABLE_MATCHES_TABLE: str = os.getenv("AIRTABLE_MATCHES_TABLE", "Matches")
    AIRTABLE_DRAFTS_TABLE: str = os.getenv("AIRTABLE_DRAFTS_TABLE", "Drafts")

    @classmethod
    def validate(cls) -> bool:
        """Validate Airtable configuration."""
        if not cls.AIRTABLE_PAT:
            raise ValueError("AIRTABLE_PAT is required")
        if not cls.AIRTABLE_BASE_ID:
            raise ValueError("AIRTABLE_BASE_ID is required")
        return True


class APIConfig:
    """API Keys configuration."""
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
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
    DEFAULT_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")
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


class LinkedInConfig:
    """LinkedIn scraper configuration."""
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")
    CHROME_USER_DATA_DIR: str = os.getenv("CHROME_USER_DATA_DIR", "")
    LINKEDIN_HEADLESS: bool = os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true"
    LINKEDIN_PAGE_TIMEOUT: int = int(os.getenv("LINKEDIN_PAGE_TIMEOUT", "30"))
    LINKEDIN_ELEMENT_TIMEOUT: int = int(os.getenv("LINKEDIN_ELEMENT_TIMEOUT", "10"))

    @classmethod
    def validate(cls) -> bool:
        """Validate LinkedIn configuration."""
        if not cls.LINKEDIN_EMAIL or not cls.LINKEDIN_PASSWORD:
            return False
        return True

    @classmethod
    def is_configured(cls) -> bool:
        """Check if LinkedIn scraper is properly configured."""
        return bool(cls.LINKEDIN_EMAIL and cls.LINKEDIN_PASSWORD)


class FeatureFlags:
    """Feature flags for enabling/disabling features."""
    AUTO_ENRICH: bool = os.getenv("AUTO_ENRICH_ENABLED", "true").lower() == "true"
    AUTO_CLASSIFY: bool = os.getenv("AUTO_CLASSIFY_ENABLED", "true").lower() == "true"
    VOICE_TRANSCRIPTION: bool = os.getenv("VOICE_TRANSCRIPTION_ENABLED", "true").lower() == "true"
    IMAGE_OCR: bool = os.getenv("IMAGE_OCR_ENABLED", "true").lower() == "true"
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    LINKEDIN_SCRAPER: bool = os.getenv("LINKEDIN_SCRAPER_ENABLED", "false").lower() == "true"


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
    TelegramConfig.validate()
    AirtableConfig.validate()
    APIConfig.validate()
    return True


def get_config_summary() -> dict:
    """Get a summary of current configuration (for debugging)."""
    return {
        "telegram": {
            "bot_name": TelegramConfig.BOT_NAME,
            "token_configured": bool(TelegramConfig.BOT_TOKEN),
        },
        "airtable": {
            "pat_configured": bool(AirtableConfig.AIRTABLE_PAT),
            "base_id": AirtableConfig.AIRTABLE_BASE_ID,
            "contacts_table": AirtableConfig.AIRTABLE_CONTACTS_TABLE,
            "matches_table": AirtableConfig.AIRTABLE_MATCHES_TABLE,
            "drafts_table": AirtableConfig.AIRTABLE_DRAFTS_TABLE,
        },
        "apis": {
            "tavily_configured": bool(APIConfig.TAVILY_API_KEY),
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
        "linkedin": {
            "configured": LinkedInConfig.is_configured(),
            "headless": LinkedInConfig.LINKEDIN_HEADLESS,
        },
        "features": {
            "auto_enrich": FeatureFlags.AUTO_ENRICH,
            "auto_classify": FeatureFlags.AUTO_CLASSIFY,
            "voice_transcription": FeatureFlags.VOICE_TRANSCRIPTION,
            "image_ocr": FeatureFlags.IMAGE_OCR,
            "email_enabled": FeatureFlags.EMAIL_ENABLED,
            "linkedin_scraper": FeatureFlags.LINKEDIN_SCRAPER,
        },
        "session": {
            "timeout_seconds": SessionConfig.TIMEOUT_SECONDS,
            "continuation_seconds": SessionConfig.CONTINUATION_SECONDS,
            "memory_expiry_minutes": SessionConfig.MEMORY_EXPIRY_MINUTES,
            "guided_prompts_enabled": SessionConfig.GUIDED_PROMPTS_ENABLED,
        },
    }
