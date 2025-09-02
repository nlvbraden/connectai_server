"""NetSapiens webhook and WebSocket endpoints."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from typing import Dict, Any, Optional
from pydantic import BaseModel
from ..core.netsapiens_handler import netsapiens_handler
from ..utils.logging import get_logger
from ..settings import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class WebhookPayload(BaseModel):
    """Generic webhook payload."""
    event: str
    data: Dict[str, Any]
    timestamp: Optional[float] = None
    domain: Optional[str] = None

async def _process_webhook_event(payload: WebhookPayload, client_ip: str):
    """Process different types of webhook events."""
    event_type = payload.event
    
    if event_type == "call_started":
        await _handle_call_started_event(payload, client_ip)
    elif event_type == "call_ended":
        await _handle_call_ended_event(payload, client_ip)
    elif event_type == "call_transfer":
        await _handle_call_transfer_event(payload, client_ip)
    elif event_type == "dtmf_received":
        await _handle_dtmf_event(payload, client_ip)
    else:
        logger.warning(f"Unknown webhook event type: {event_type}")

async def _handle_call_started_event(payload: WebhookPayload, client_ip: str):
    """Handle call started webhook event."""
    logger.info(f"Call started event from {client_ip}: {payload.data}")
    
    # Extract call information
    call_data = payload.data
    session_id = call_data.get('session_id')
    caller_id = call_data.get('caller_id')
    called_number = call_data.get('called_number')
    
    # Log call start for analytics/tracking
    # In production, you might want to store this in the database
    logger.info(f"Call started - Session: {session_id}, From: {caller_id}, To: {called_number}")

async def _handle_call_ended_event(payload: WebhookPayload, client_ip: str):
    """Handle call ended webhook event."""
    logger.info(f"Call ended event from {client_ip}: {payload.data}")
    
    # Extract call information
    call_data = payload.data
    session_id = call_data.get('session_id')
    duration = call_data.get('duration')
    end_reason = call_data.get('end_reason')
    
    # Log call end for analytics/tracking
    logger.info(f"Call ended - Session: {session_id}, Duration: {duration}s, Reason: {end_reason}")

async def _handle_call_transfer_event(payload: WebhookPayload, client_ip: str):
    """Handle call transfer webhook event."""
    logger.info(f"Call transfer event from {client_ip}: {payload.data}")
    
    # Extract transfer information
    transfer_data = payload.data
    session_id = transfer_data.get('session_id')
    transfer_to = transfer_data.get('transfer_to')
    
    logger.info(f"Call transferred - Session: {session_id}, To: {transfer_to}")

async def _handle_dtmf_event(payload: WebhookPayload, client_ip: str):
    """Handle DTMF (key press) webhook event."""
    logger.info(f"DTMF event from {client_ip}: {payload.data}")
    
    # Extract DTMF information
    dtmf_data = payload.data
    session_id = dtmf_data.get('session_id')
    digit = dtmf_data.get('digit')
    
    logger.info(f"DTMF received - Session: {session_id}, Digit: {digit}")

@router.get("/netsapiens/status")
async def netsapiens_status():
    """Get status of NetSapiens integration."""
    try:
        # Get active WebSocket connections
        active_connections = len(netsapiens_handler.active_connections)
        
        # Get session manager status
        session_manager = netsapiens_handler.session_manager
        active_sessions = session_manager.get_session_count()
        
        return {
            "status": "operational",
            "active_websocket_connections": active_connections,
            "active_agent_sessions": active_sessions,
            "integration": "netsapiens_webresponder"
        }
        
    except Exception as e:
        logger.error(f"Error getting NetSapiens status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get status")

@router.post("/netsapiens/test")
async def test_netsapiens_integration(test_payload: Dict[str, Any]):
    """Test endpoint for NetSapiens integration."""
    try:
        logger.info(f"NetSapiens test payload received: {test_payload}")
        
        # Simulate processing
        domain = test_payload.get('domain', 'test.example.com')
        
        # Check if we can create an agent for this domain
        from ..database import SessionLocal, get_business_by_domain
        db = SessionLocal()
        try:
            business = get_business_by_domain(db, domain)
            if business:
                return {
                    "status": "success",
                    "message": f"Test successful for domain: {domain}",
                    "business_found": True,
                    "business_name": business.name
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Business not found for domain: {domain}",
                    "business_found": False
                }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in NetSapiens test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

# NetSapiens WebResponder XML response endpoints
@router.post("/netsapiens/webresponder")
async def netsapiens_webresponder_endpoint(request: Request):
    """Handle NetSapiens WebResponder XML requests."""
    try:
        # Get request body
        body = await request.body()
        content_type = request.headers.get('content-type', '')
        
        logger.info(f"NetSapiens WebResponder request received: {len(body)} bytes")
        
        # Parse NetSapiens parameters
        # NetSapiens sends form-encoded data with call parameters
        if 'application/x-www-form-urlencoded' in content_type:
            # Parse form data
            form_data = await request.form()
            call_params = dict(form_data)
            
            logger.info(f"NetSapiens call parameters: {call_params}")
            
            # Generate WebResponder XML response
            xml_response = _generate_webresponder_xml(call_params)
            
            return Response(
                content=xml_response,
                media_type="application/xml"
            )
        else:
            logger.warning(f"Unexpected content type: {content_type}")
            return Response(
                content="<Response><Say>Service unavailable</Say></Response>",
                media_type="application/xml"
            )
            
    except Exception as e:
        logger.error(f"Error in WebResponder endpoint: {str(e)}")
        return Response(
            content="<Response><Say>Service error</Say></Response>",
            media_type="application/xml"
        )

def _generate_webresponder_xml(call_params: Dict[str, Any]) -> str:
    """Generate NetSapiens WebResponder XML response."""
    try:
        # Extract call information
        caller_id = call_params.get('From', 'unknown')
        called_number = call_params.get('To', 'unknown')
        domain = call_params.get('Domain', 'unknown')
        
        logger.info(f"Generating WebResponder XML for call: {caller_id} -> {called_number} @ {domain}")
        
        # Generate WebSocket URL for streaming
        websocket_url = f"wss://{settings.host}:{settings.port}/webhooks/netsapiens/stream"
        
        # Create XML response with Stream verb for bidirectional audio
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! Connecting you to our AI assistant.</Say>
    <Stream url="{websocket_url}">
        <Parameter name="domain" value="{domain}" />
        <Parameter name="caller_id" value="{caller_id}" />
        <Parameter name="called_number" value="{called_number}" />
    </Stream>
</Response>"""
        
        return xml_response
        
    except Exception as e:
        logger.error(f"Error generating WebResponder XML: {str(e)}")
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was an error processing your call.</Say>
    <Hangup/>
</Response>"""
