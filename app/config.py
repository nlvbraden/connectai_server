"""Configuration management for the AI Agent Server."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings."""
    
    # Google AI Configuration
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    
    # Database Configuration
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/connectai_db")
    
    # NetSapiens Configuration
    netsapiens_auth_token: str = os.getenv("NETSAPIENS_AUTH_TOKEN", "")
    
    # ConnectWare Configuration
    connectware_api_key: str = os.getenv("CONNECTWARE_API_KEY", "")
    connectware_url: str = os.getenv("CONNECTWARE_URL", "")
    
    # PhoneSuite Configuration
    phonesuite_api_key: str = os.getenv("PHONESUITE_API_KEY", "")
    phonesuite_url: str = os.getenv("PHONESUITE_URL", "")
    
    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    
    # Gemini Model Configuration
    gemini_model: str = "gemini-2.0-flash-exp"  # Supports Live API
    
    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields from .env

settings = Settings()
