"""Configuration management for the AI Agent Server."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load secrets from AWS Secrets Manager (if configured) before defining Settings
try:
    from .utils.aws_secrets import AwsSecretsLoader
    AwsSecretsLoader().load_all()
except Exception:
    # Fallback silently in local/dev if AWS not configured
    pass

class Settings(BaseSettings):
    """Application settings."""
    
    # ConnectWare Configuration
    connectware_api_key: str = os.getenv("CONNECTWARE_API_KEY")
    connectware_url: str = os.getenv("CONNECTWARE_URL")
    
    # PhoneSuite Configuration
    phonesuite_api_key: str = os.getenv("PHONESUITE_API_KEY")
    phonesuite_url: str = os.getenv("PHONESUITE_URL")
    
    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")

    # Google Configuration
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account-key.json")
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "connectai-457621")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    google_genai_use_vertexai: str = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-live-2.5-flash-preview-native-audio")
    
    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    rds_cluster_arn: str = os.getenv("RDS_CLUSTER_ARN")
    rds_secret_arn: str = os.getenv("RDS_SECRET_ARN")
    rds_db_name: str = os.getenv("RDS_DB_NAME")
    
    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields from .env

settings = Settings()
