"""WebSocket handler for NetSapiens WebResponder integration."""

import json
import asyncio
import logging
from typing import Dict, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from .agent_session_manager import AgentSessionManager
from .audio_processor import AudioProcessor
from ..services.database_service import DatabaseService
from ..models import Interaction, Agent, Business

logger = logging.getLogger(__name__)

class NetSapiensWebSocketHandler:
    """Handles WebSocket connections from NetSapiens WebResponder."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_manager = AgentSessionManager()
        self.audio_processor = AudioProcessor()
        self.db = DatabaseService()
    
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
            websocket = self.active_connections.get(session_id)
            try:
                # Clean up agent session first
                await self.session_manager.end_session(session_id)
            except Exception as e:
                logger.error(f"Error ending session during disconnect {session_id}: {str(e)}")
            finally:
                # Attempt to close the websocket gracefully
                try:
                    if websocket and hasattr(websocket, "close"):
                        await websocket.close()
                except Exception:
                    pass
                # Finally remove from active connections
                self.active_connections.pop(session_id, None)
                logger.info(f"WebSocket disconnected: {session_id}")
    
    async def handle_netsapiens_stream(self, websocket: WebSocket, session_id: str):
        """Handle incoming NetSapiens WebSocket stream."""
        try:
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
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                except asyncio.TimeoutError:
                    logger.warning(f"WebSocket idle timeout in stream loop: {session_id}")
                    # Proactively stop the call to avoid lingering sessions
                    await self._handle_call_stop(session_id, {"reason": "idle_timeout"})
                    break
                message = json.loads(data)
                
                # Process different message types
                should_continue = await self._process_netsapiens_message(websocket, session_id, message)
                if not should_continue:
                    # Stop event received or terminal condition; break out
                    break
                
        except WebSocketDisconnect:
            logger.info(f"NetSapiens WebSocket disconnected in stream loop: {session_id}")
        except Exception as e:
            logger.error(f"Error in stream loop {session_id}: {str(e)}")
        finally:
            logger.info(f"Stream loop finished for session: {session_id}")
    
    async def _process_netsapiens_message(self, websocket: WebSocket, session_id: str, message: Dict[str, Any]) -> bool:
        """Process incoming message from NetSapiens.
        
        Returns:
            bool: True to continue stream loop, False to stop.
        """
        message_type = message.get("event", "unknown")
        
        if message_type == "media":
            # Handle audio data
            await self._handle_audio_data(session_id, message)
            return True
        elif message_type == "start":
            # Call started
            await self._handle_call_start(session_id, message)
            return True
        elif message_type == "stop":
            # Call ended
            await self._handle_call_stop(session_id, message)
            return False
        else:
            logger.warning(f"Unknown message type from NetSapiens: {message_type}")
            return True
    
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
        # Extract custom parameters from start event
        start_info = message.get("start", {}) if isinstance(message.get("start"), dict) else {}
        params_raw = (
            start_info.get("customParameters")
            or start_info.get("parameters")
            or message.get("parameters")
            or message.get("customParameters")
            or []
        )
        params: Dict[str, Any] = {}
        # Support list of {name, value} or a dict
        if isinstance(params_raw, list):
            for p in params_raw:
                name = (p or {}).get("name")
                value = (p or {}).get("value")
                if name is not None:
                    params[str(name)] = value
        elif isinstance(params_raw, dict):
            params.update(params_raw)

        account_domain = params.get("AccountDomain")
        called_number = params.get("NmsDnis")
        caller_id = params.get("NmsAni")
        term_call_id = params.get("TermCallID")
        orig_call_id = params.get("OrigCallID")
        stream_id = start_info.get("streamId") or message.get("streamId")
        external_id = orig_call_id or term_call_id or stream_id or session_id

        # Lookup business and agent
        agent = None
        try:
            print("Looking up business with domain:", account_domain)
            agent = await asyncio.to_thread(self.db.get_active_agent_for_domain, account_domain)
        except Exception as e:
            logger.error(f"DB lookup failed on call start {session_id}: {str(e)}")

        # Prepare agent config
        interaction: Optional[Interaction] = None
        business_id = agent.business_id if agent else None
        agent_id = agent.id if agent else None

        # Create interaction
        try:
            interaction = await asyncio.to_thread(
                self.db.create_interaction,
                call_id=external_id,
                business_id=business_id,
                agent_id=agent_id,
                customer_identifier=str(caller_id) if caller_id else None,
            )
        except Exception as e:
            logger.error(f"Failed to create interaction for {session_id}: {str(e)}")

        # Start the agent session lazily on start
        success = await self.session_manager.start_session(
            session_id,
            account_domain,
            self.active_connections.get(session_id),
            agent=agent,
            interaction=interaction,
            external_id=external_id,
        )

        if not success:
            await self._send_error(self.active_connections.get(session_id), "Failed to start agent session")
            return

        # Notify agent session of call start
        await self.session_manager.notify_call_start(session_id, message)
    
    async def _handle_call_stop(self, session_id: str, message: Dict[str, Any]):
        """Handle call stop event."""
        logger.info(f"Call ended for session: {session_id}")
        # Attempt to end interaction regardless of session state
        try:
            stop_info = message.get("stop", {}) if isinstance(message.get("stop"), dict) else {}
            params_raw = (
                stop_info.get("customParameters")
                or stop_info.get("parameters")
                or message.get("parameters")
                or message.get("customParameters")
                or []
            )
            params: Dict[str, Any] = {}
            if isinstance(params_raw, list):
                for p in params_raw:
                    name = (p or {}).get("name")
                    value = (p or {}).get("value")
                    if name is not None:
                        params[str(name)] = value
            elif isinstance(params_raw, dict):
                params.update(params_raw)

            term_call_id = params.get("TermCallID") or params.get("OrigCallID")
            stream_id = stop_info.get("streamId") or message.get("streamId")
            external_id = term_call_id or stream_id or session_id
            reason = message.get("reason") or stop_info.get("reason") or "hangup"
            await asyncio.to_thread(self.db.end_interaction, external_id=external_id, outcome=reason)
        except Exception as e:
            logger.error(f"Failed to end interaction on stop for {session_id}: {str(e)}")

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
    
    async def send_stop_to_netsapiens(self, session_id: str):
        """Send stop event to NetSapiens."""
        await self.send_response_to_netsapiens(session_id, "stop", {})

# Global WebSocket handler instance
netsapiens_handler = NetSapiensWebSocketHandler()
