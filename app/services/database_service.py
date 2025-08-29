"""Service for database operations."""

from typing import Optional, List
from ..models import Business
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseService:
    """Service for database operations."""