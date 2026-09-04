"""
RecoverAI Configuration Settings
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""
    
    # Server Settings
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Database Settings
    DATABASE_URL: str = "sqlite:///./recoverai.db"
    ECHO_SQL: bool = False
    
    # LLM API Keys
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # Razorpay API Credentials (Test Mode)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    
    # Safety & Execution Controls
    MAX_REAL_PAYMENT_LINKS: int = 10
    SIMULATE_OPENAI_FAILURE: bool = False
    SIMULATE_GEMINI_FAILURE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
