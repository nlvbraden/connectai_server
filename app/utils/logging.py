"""Logging configuration for the application."""

import logging
import sys
from typing import Optional
from ..settings import settings

def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure application logging."""
    
    level = log_level or settings.log_level
    log_level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    
    # Configure root logger
    logging.basicConfig(
        level=log_level_map.get(level.lower(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log', mode='a')
        ]
    )
    
    # Configure specific loggers
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('fastapi').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    
    # Set our application loggers
    logging.getLogger('app').setLevel(log_level_map.get(level.lower(), logging.INFO))
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {level.upper()}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"app.{name}")
