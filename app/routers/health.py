"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
# from ..database import SessionLocal, engine
from ..core.session_manager import AgentSessionManager
from ..utils.logging import get_logger
import time

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "connectai_server"
    }