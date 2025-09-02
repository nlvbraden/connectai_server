"""Call handling endpoints for NetSapiens integration."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from typing import Dict, Any
from ..utils.logging import get_logger
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.responses import Response
from typing import Dict, Any, Optional
from pydantic import BaseModel
import uuid
from ..core.netsapiens_handler import netsapiens_handler
from ..utils.logging import get_logger
from ..settings import settings


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["calls"])

@router.get("/call")
@router.post("/call")
async def handle_call(request: Request):
    """
    Handle incoming call webhook from NetSapiens.
    Returns TwiML response to establish WebSocket connection to existing /stream endpoint.
    """
    # Extract parameters from query string for both GET and POST
    params = dict(request.query_params)
    # NetSapiens call parameters
    term_call_id = params.get("TermCallID", "")
    nms_dnis = params.get("NmsDnis", "")
    account_domain = params.get("AccountDomain", "")
    account_user = params.get("AccountUser", "")
    nms_ani = params.get("NmsAni", "")
    orig_call_id = params.get("OrigCallID", "")
    
    logger.info(f"Incoming call - Domain: {account_domain}, DNIS: {nms_dnis}, ANI: {nms_ani}, CallID: {term_call_id}")
    
    # Get host from request headers
    host = request.headers.get("host", "localhost")
    
    # Create TwiML response to establish WebSocket connection to existing /stream endpoint
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Connect>
                <Stream action="/api/v1/end" url="wss://{host}/api/v1/stream">
                    <Parameter name="TermCallID" value="{term_call_id}"/>
                    <Parameter name="NmsDnis" value="{nms_dnis}"/>
                    <Parameter name="AccountDomain" value="{account_domain}"/>
                    <Parameter name="AccountUser" value="{account_user}"/>
                    <Parameter name="NmsAni" value="{nms_ani}"/>
                    <Parameter name="OrigCallID" value="{orig_call_id}"/>
                </Stream>
            </Connect>
        </Response>
    """
    
    logger.debug(f"Returning TwiML for WebSocket connection to /webhooks/stream")
    return Response(content=response, media_type="application/xml")

@router.websocket("/stream")
async def netsapiens_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for NetSapiens WebResponder streaming."""
    session_id = str(uuid.uuid4())
    logger.info(f"New NetSapiens WebSocket connection attempt: {session_id}")
    
    try:
        # Accept connection
        success = await netsapiens_handler.connect(websocket, session_id)
        if not success:
            logger.error(f"Failed to establish WebSocket connection: {session_id}")
            return
            
        # Handle the NetSapiens stream
        await netsapiens_handler.handle_netsapiens_stream(websocket, session_id)
        
    except WebSocketDisconnect:
        logger.info(f"NetSapiens WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Error in NetSapiens WebSocket endpoint {session_id}: {str(e)}")
    finally:
        await netsapiens_handler.disconnect(session_id)

@router.post("/end")
async def handle_call_end(request: Request):
    """
    Handle call end webhook from NetSapiens.
    """
    try:
        # Extract call end parameters
        params = dict(request.query_params)
        term_call_id = params.get("TermCallID", "")
        
        logger.info(f"Call ended - CallID: {term_call_id}")
        
        # TODO: Notify existing websocket handler about call end
        # This should integrate with the existing netsapiens_handler
        
        return {"status": "ok", "message": "Call end processed"}
        
    except Exception as e:
        logger.error(f"Error processing call end: {str(e)}")
        return {"status": "error", "message": str(e)}
