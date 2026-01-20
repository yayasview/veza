"""Configuration module for environment variables and settings."""

import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""

    # Avoma settings
    AVOMA_API_KEY = os.getenv("AVOMA_API_KEY")
    AVOMA_BASE_URL = "https://api.avoma.com/v1"
    AVOMA_RATE_LIMIT = float(os.getenv("AVOMA_RATE_LIMIT", "2"))

    # Notion settings
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    NOTION_API_VERSION = "2022-06-28"
    NOTION_RATE_LIMIT = float(os.getenv("NOTION_RATE_LIMIT", "3"))

    # Export settings
    EXPORT_FROM_DATE = os.getenv("EXPORT_FROM_DATE", "2020-01-01")
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

    # Directories
    EXPORTS_DIR = "exports"
    LOGS_DIR = "logs"

    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        errors = []

        if not cls.AVOMA_API_KEY:
            errors.append("AVOMA_API_KEY is not set")

        if not cls.NOTION_API_KEY:
            errors.append("NOTION_API_KEY is not set")

        if not cls.NOTION_DATABASE_ID:
            errors.append("NOTION_DATABASE_ID is not set")

        if errors:
            raise ValueError(
                "Missing required configuration:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return True

    @classmethod
    def setup_directories(cls):
        """Create necessary directories if they don't exist."""
        os.makedirs(cls.EXPORTS_DIR, exist_ok=True)
        os.makedirs(cls.LOGS_DIR, exist_ok=True)
