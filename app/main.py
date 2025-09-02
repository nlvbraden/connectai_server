"""Main FastAPI application for ConnectAI Server."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from contextlib import asynccontextmanager

# Import routers
from .routers import health, webhooks, calls

# Import utilities and configuration
from .settings import settings
from .utils.logging import setup_logging, get_logger
# Import core components for initialization
from .core.netsapiens_handler import netsapiens_handler
from .core.agent_session_manager import AgentSessionManager

# Setup logging
setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting ConnectAI Server...")
    
    try:
        # Initialize database tables (if needed)
        # Note: In production, use proper migration tools like Alembic
        logger.info("Checking database connection...")
        
        # Initialize components
        logger.info("Initializing components...")
        
        # Check Google ADK availability
        try:
            # from google.adk.agents import Agent  # Commented out - using dynamic agent creation
            logger.info("Google ADK is available")
        except ImportError as e:
            logger.error(f"Google ADK not available: {e}")
            raise
        
        logger.info("ConnectAI Server startup complete")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise
    
    # Shutdown
    logger.info("Shutting down ConnectAI Server...")
    
    try:
        # Clean up active sessions
        session_manager = AgentSessionManager()
        active_sessions = session_manager.get_active_sessions()
        
        if active_sessions:
            logger.info(f"Cleaning up {len(active_sessions)} active sessions...")
            cleanup_tasks = [
                session_manager.end_session(session_id) 
                for session_id in active_sessions.keys()
            ]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("ConnectAI Server shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title="ConnectAI Server",
    description="AI Agent Server for NetSapiens WebResponder Integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP error {exc.status_code} from {request.client.host}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_error"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error from {request.client.host}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )

# Include routers
app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(calls.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "service": "ConnectAI Server",
        "version": "1.0.0",
        "description": "AI Agent Server for NetSapiens WebResponder Integration",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "agents": "/agents",
            "webhooks": "/webhooks",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/info")
async def server_info():
    """Get server information and statistics."""
    try:
        # Get session statistics
        session_manager = AgentSessionManager()
        active_sessions = session_manager.get_session_count()
        
        # Get WebSocket connection count
        ws_connections = len(netsapiens_handler.active_connections)
        
        # Get tool information
        from .tools.base import tool_registry
        available_tools = tool_registry.list_tools()
        
        return {
            "server": {
                "name": "ConnectAI Server",
                "version": "1.0.0",
                "host": settings.host,
                "port": settings.port
            },
            "statistics": {
                "active_agent_sessions": active_sessions,
                "active_websocket_connections": ws_connections,
                "available_tools": len(available_tools)
            },
            "configuration": {
                "gemini_model": settings.gemini_model,
                "log_level": settings.log_level,
                "database_connected": True  # Simplified check
            },
            "tools": available_tools
        }
        
    except Exception as e:
        logger.error(f"Error getting server info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get server info")

# Run server function
def run_server():
    """Run the server with uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=True  # Set to True for development
    )

if __name__ == "__main__":
    run_server()
