"""WebSocket handler for NetSapiens WebResponder integration."""

import json
import logging
from typing import Dict, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from .session_manager import AgentSessionManager
from .audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class NetSapiensWebSocketHandler:
    """Handles WebSocket connections from NetSapiens WebResponder."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_manager = AgentSessionManager()
        self.audio_processor = AudioProcessor()
    
    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Accept WebSocket connection and initialize session."""
        try:
            await websocket.accept()
            self.active_connections[session_id] = websocket
            logger.info(f"WebSocket connected: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket {session_id}: {str(e)}")
            return False
    
    async def disconnect(self, session_id: str):
        """Clean up WebSocket connection."""
        if session_id in self.active_connections:
            try:
                # Clean up agent session
                await self.session_manager.end_session(session_id)
                del self.active_connections[session_id]
                logger.info(f"WebSocket disconnected: {session_id}")
            except Exception as e:
                logger.error(f"Error during disconnect {session_id}: {str(e)}")
    
    async def handle_netsapiens_stream(self, websocket: WebSocket, session_id: str):
        """Handle incoming NetSapiens WebSocket stream."""
        try:
            #TODO: Get business info
            business_domain = "faketacos"
            
            if not business_domain:
                await self._send_error(websocket, "Unable to identify business domain")
                return
    
            # Start the agent session with Google ADK
            success = await self.session_manager.start_session(
                session_id, business_domain, websocket
            )
            
            if not success:
                await self._send_error(websocket, "Failed to start agent session")
                return
            
            # Handle the streaming conversation
            await self._handle_stream_loop(websocket, session_id)
            
        except WebSocketDisconnect:
            logger.info(f"NetSapiens WebSocket disconnected: {session_id}")
        except Exception as e:
            logger.error(f"Error handling NetSapiens stream {session_id}: {str(e)}")
        finally:
            await self.disconnect(session_id)
    
    async def _handle_stream_loop(self, websocket: WebSocket, session_id: str):
        """Main loop for handling bidirectional streaming."""
        try:
            while True:
                # Receive data from NetSapiens
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process different message types
                await self._process_netsapiens_message(websocket, session_id, message)
                
        except WebSocketDisconnect:
            logger.info(f"NetSapiens WebSocket disconnected in stream loop: {session_id}")
        except Exception as e:
            logger.error(f"Error in stream loop {session_id}: {str(e)}")
    
    async def _process_netsapiens_message(self, websocket: WebSocket, session_id: str, message: Dict[str, Any]):
        """Process incoming message from NetSapiens."""
        message_type = message.get("event", "unknown")
        
        if message_type == "media":
            # Handle audio data
            await self._handle_audio_data(session_id, message) 
        elif message_type == "start":
            # Call started
            await self._handle_call_start(session_id, message)
        elif message_type == "stop":
            # Call ended
            await self._handle_call_stop(session_id, message)  
        else:
            logger.warning(f"Unknown message type from NetSapiens: {message_type}")
    
    async def _handle_audio_data(self, session_id: str, message: Dict[str, Any]):
        """Handle incoming audio data from NetSapiens."""
        try:
            # Extract audio payload
            audio_data = message.get("media", {}).get("payload")
            if not audio_data:
                return
            
            # Process audio and send to agent
            processed_audio = await self.audio_processor.process_incoming_audio(audio_data)
            
            # Send to agent session
            await self.session_manager.send_audio_to_agent(session_id, processed_audio)
            
        except Exception as e:
            logger.error(f"Error handling audio data for session {session_id}: {str(e)}")
    
    async def _handle_call_start(self, session_id: str, message: Dict[str, Any]):
        """Handle call start event."""
        logger.info(f"Call started for session: {session_id}")
        # Notify agent session
        await self.session_manager.notify_call_start(session_id, message)
    
    async def _handle_call_stop(self, session_id: str, message: Dict[str, Any]):
        """Handle call stop event."""
        logger.info(f"Call ended for session: {session_id}")
        # Notify agent session and clean up
        await self.session_manager.notify_call_end(session_id, message)
    
    def _extract_domain_from_connection(self, connection_info: Dict[str, Any]) -> Optional[str]:
        """Extract business domain from NetSapiens connection information."""
        # NetSapiens provides various parameters in the connection
        # Common places to find domain info:
        domain_candidates = [
            connection_info.get("domain"),
            connection_info.get("to_domain"),
            connection_info.get("from_domain"),
            connection_info.get("caller_domain"),
            connection_info.get("callee_domain")
        ]
        
        for candidate in domain_candidates:
            if candidate and isinstance(candidate, str):
                return candidate.lower()
        
        # Try to extract from SIP headers if available
        sip_headers = connection_info.get("sip_headers", {})
        if sip_headers:
            # Look for domain in various SIP headers
            pass
        
        return None
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to NetSapiens."""
        error_response = {
            "event": "error",
            "error": error_message
        }
        await websocket.send_text(json.dumps(error_response))
    
    async def send_audio_to_netsapiens(self, session_id: str, audio_data: bytes):
        """Send audio data back to NetSapiens."""
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session: {session_id}")
            return
        
        websocket = self.active_connections[session_id]
        try:
            # Format audio data for NetSapiens
            audio_message = {
                "event": "media",
                "media": {
                    "payload": audio_data,  # audio_data is already base64-encoded from audio_processor
                    "encoding": "ulaw"
                }
            }
            await websocket.send_text(json.dumps(audio_message))
            
        except Exception as e:
            logger.error(f"Error sending audio to NetSapiens session {session_id}: {str(e)}")
    
    async def send_clear_audio(self, session_id: str):
        """Send clear event to NetSapiens to stop current audio playback."""
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session: {session_id}")
            return
        
        websocket = self.active_connections[session_id]
        try:
            clear_message = {
                "event": "clear",
                "streamId": session_id  # NetSapiens uses the session_id as stream_id
            }
            await websocket.send_text(json.dumps(clear_message))
            logger.info(f"Sent clear audio event for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending clear audio to NetSapiens session {session_id}: {str(e)}")
    
    async def send_response_to_netsapiens(self, session_id: str, response_type: str, data: Dict[str, Any]):
        """Send structured response to NetSapiens."""
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session: {session_id}")
            return
        
        websocket = self.active_connections[session_id]
        try:
            response = {
                "event": response_type,
                **data
            }
            await websocket.send_text(json.dumps(response))
            
        except Exception as e:
            logger.error(f"Error sending response to NetSapiens session {session_id}: {str(e)}")

# Global WebSocket handler instance
netsapiens_handler = NetSapiensWebSocketHandler()
