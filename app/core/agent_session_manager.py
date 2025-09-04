"""Agent session management for Google ADK integration."""
import asyncio
import logging
from typing import Dict, Optional, Any
from fastapi import WebSocket
from google.adk.events import Event
from .audio_processor import AudioProcessor
from google.genai.types import Blob, Content, Part
from ..models.agent import Agent
from .session_utils.agent_session import AgentSession
from ..models.interaction import Interaction

logger = logging.getLogger(__name__)

class AgentSessionManager:
    """Manages active agent sessions with Google ADK."""
    
    def __init__(self):
        self.active_sessions: Dict[str, AgentSession] = {}
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self.audio_processor = AudioProcessor()
        from ..services.database_service import DatabaseService
        self.db = DatabaseService()
    
    async def start_session(self, session_id: str, business_domain: str, websocket: WebSocket,
                            agent: Optional[Agent] = None,
                            interaction: Optional[Interaction] = None,
                            external_id: Optional[str] = None) -> bool:
        """Start a new agent session."""
        try:
            # Create session
            session = AgentSession(session_id, business_domain, websocket,
                                   agent=agent,
                                   interaction=interaction,
                                   external_id=external_id)
            
            # Start ADK session
            if not await session.start_adk_session():
                return False
            
            # Store session
            self.active_sessions[session_id] = session
            
            # Start session management tasks
            await self._start_session_tasks(session)
            
            logger.info(f"Agent session started: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {str(e)}")
            return False
    
    async def end_session(self, session_id: str):
        """End an agent session."""
        if session_id not in self.active_sessions:
            return
        
        try:
            session = self.active_sessions[session_id]
            
            # Stop ADK session
            await session.stop_adk_session()
            
            # Cancel session tasks
            if session_id in self.session_tasks:
                task = self.session_tasks[session_id]
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=5)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                del self.session_tasks[session_id]
            
            # Remove session
            del self.active_sessions[session_id]
            
            logger.info(f"Agent session ended: {session_id}")
            
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {str(e)}")
    
    async def _start_session_tasks(self, session: AgentSession):
        """Start background tasks for managing the session."""
        # Create combined task for handling both directions of communication
        task = asyncio.create_task(
            self._manage_session_communication(session)
        )
        self.session_tasks[session.session_id] = task
    
    async def _manage_session_communication(self, session: AgentSession):
        """Manage bidirectional communication between agent and NetSapiens."""
        try:
            # Create tasks for both directions
            agent_to_netsapiens_task = asyncio.create_task(
                self._agent_to_netsapiens_loop(session)
            )
            
            # Wait for either task to complete or fail
            await agent_to_netsapiens_task
            
        except asyncio.CancelledError:
            logger.info(f"Session communication cancelled: {session.session_id}")

        except Exception as e:
            logger.error(f"Error in session communication {session.session_id}: {str(e)}")
        finally:
            logger.info(f"Session communication task finished: {session.session_id}")
    
    async def _agent_to_netsapiens_loop(self, session: AgentSession):
        """Handle messages from agent to NetSapiens."""
        try:
            if not session.live_events:
                logger.warning(f"No live_events for session {session.session_id}")
                return
            
            logger.info(f"Starting agent-to-NetSapiens loop for {session.session_id}, live_events type: {type(session.live_events)}")
            
            async for event in session.live_events:
                # If the session has been marked inactive, exit the loop promptly
                if not session.is_active:
                    logger.info(f"Session inactive; exiting agent loop: {session.session_id}")
                    break
                await self._process_agent_event(session, event)
                
        except asyncio.CancelledError:
            # Task was cancelled as part of shutdown; exit quietly
            logger.info(f"Agent-to-NetSapiens loop cancelled for {session.session_id}")
        except Exception as e:
            logger.error(f"Error in agent-to-NetSapiens loop {session.session_id}: {str(e)}")
            logger.exception("Full traceback:")
        finally:
            logger.info(f"Agent-to-NetSapiens loop finished for {session.session_id}")
    
    async def _process_agent_event(self, session: AgentSession, event: Event):
        """Process events from the agent."""
        try:
            if not session.is_active:
                # Session terminated; drop any late events to avoid tool/MCP activity
                return
            logger.debug(f"Processing agent event type: {type(event).__name__}")
            
            # All event data is in content
            if hasattr(event, 'content') and event.content:
                # Process each part in the content
                for part in event.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # This is binary data (audio)
                        blob = part.inline_data
                        if blob.mime_type and 'audio' in blob.mime_type:
                            await self._handle_audio_data(session, blob.data)
                    elif hasattr(part, 'text') and part.text:
                        # This is text content
                        logger.info(f"{event.content.role} says: {part.text}")
                        await self._handle_text_response(session, event.content.role, part.text, final=not event.partial)
            
            # Check for interrupt
            if hasattr(event, 'interrupted') and event.interrupted:
                logger.info(f"Agent interrupted for session: {session.session_id}")
                await self._handle_agent_interrupt(session)
            
            # Check for conversation end
            if hasattr(event, 'turn_complete') and event.turn_complete:
                logger.info(f"Turn complete for session: {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error processing agent event {session.session_id}: {str(e)}")
    
    async def _handle_audio_data(self, session: AgentSession, audio_data: bytes):
        """Handle audio data from the agent."""
        try:
            # Convert audio from Gemini format (24kHz PCM) to NetSapiens format
            processed_audio = await self.audio_processor.process_outgoing_audio(audio_data)
            
            if processed_audio:
                # Send to NetSapiens via WebSocket handler
                from .netsapiens_handler import netsapiens_handler
                await netsapiens_handler.send_audio_to_netsapiens(
                    session.session_id, processed_audio
                )
        except Exception as e:
            logger.error(f"Error handling audio data: {str(e)}")
    
    async def _handle_text_response(self, session: AgentSession, role: str, text: str, final: bool = False):
        """Handle text response from agent."""
        # Log assistant message to DB when final response is received
        if not final:
            return

        logger.info(f"Logged {role} message for {session.session_id}: {text}")
        try:
            if session.interaction:
                await asyncio.to_thread(
                    self.db.insert_message,
                    interaction=session.interaction,
                    role=role,
                    content=text,
                    function_calls=None,
                )
        except Exception as e:
            logger.error(f"Failed to log {role} message for {session.session_id}: {str(e)}")
    
    async def _handle_agent_tool_call(self, session: AgentSession, event: Any):
        """Handle tool call from agent."""
        # The ADK handles tool execution internally
        # We just log it for monitoring
        tool_name = getattr(event, 'tool_name', 'unknown')
        logger.info(f"Agent {session.session_id} called tool: {tool_name}")
    
    async def _handle_agent_interrupt(self, session: AgentSession):
        """Handle interrupt from agent - clear audio buffer on NetSapiens."""
        try:
            from .netsapiens_handler import netsapiens_handler
            await netsapiens_handler.send_clear_audio(session.session_id)
        except Exception as e:
            logger.error(f"Error handling interrupt: {str(e)}")
    
    async def _handle_conversation_end(self, session: AgentSession):
        """Handle conversation end from agent."""
        logger.info(f"Agent ended conversation: {session.session_id}")
        # End the session
        await self.end_session(session.session_id)
    
    async def send_audio_to_agent(self, session_id: str, audio_data: bytes):
        """Send audio data to the agent.
        
        Args:
            session_id: The session identifier
            audio_data: Already processed audio (16-bit PCM @ 16kHz) from audio_processor
        """
        if session_id not in self.active_sessions:
            logger.warning(f"No active session for audio: {session_id}")
            return
        
        session = self.active_sessions[session_id]
        try:
            if not session.is_active:
                return
            if session.live_request_queue and audio_data:
                # audio_data is already processed (16-bit PCM @ 16kHz)
                # Create a Blob with audio data
                audio_blob = Blob(
                    data=audio_data,
                    mimeType="audio/pcm;rate=16000"
                )
                # Send audio to agent via ADK using send_realtime
                session.live_request_queue.send_realtime(audio_blob)
        except Exception as e:
            logger.error(f"Error sending audio to agent {session_id}: {str(e)}")
    
    async def send_text_to_agent(self, session_id: str, text: str):
        """Send text input to the agent."""
        if session_id not in self.active_sessions:
            logger.warning(f"No active session for text: {session_id}")
            return
        
        session = self.active_sessions[session_id]
        try:
            if not session.is_active:
                return
            if session.live_request_queue:
                # Create Content object for text
                content = Content(
                    parts=[Part(text=text)]
                )
                
                # Send text to agent via ADK
                session.live_request_queue.send_content(content)
        except Exception as e:
            logger.error(f"Error sending text to agent {session_id}: {str(e)}")
    
    async def send_dtmf_to_agent(self, session_id: str, dtmf: str):
        """Send DTMF input to the agent."""
        if session_id not in self.active_sessions:
            logger.warning(f"No active session for DTMF: {session_id}")
            return
        
        # Convert DTMF to text and send to agent
        dtmf_text = f"User pressed key: {dtmf}"
        await self.send_text_to_agent(session_id, dtmf_text)
    
    async def notify_call_start(self, session_id: str, call_info: Dict[str, Any]):
        """Notify agent that call has started."""
        if session_id not in self.active_sessions:
            return
        
        # Send call start notification to agent
        notification = f"Call started. Caller info: {call_info.get('caller_id', 'unknown')}"
        await self.send_text_to_agent(session_id, notification)
    
    async def notify_call_end(self, session_id: str, call_info: Dict[str, Any]):
        """Notify agent that call has ended."""
        if session_id not in self.active_sessions:
            return
        # Capture external_id before session removal
        session = self.active_sessions[session_id]
        external_id = session.external_id or session.session_id
        outcome = call_info.get('reason') or call_info.get('end_reason') or 'hangup'
        try:
            # End the session
            await self.end_session(session_id)
        finally:
            try:
                # Close interaction in DB
                await asyncio.to_thread(
                    self.db.end_interaction,
                    external_id=external_id,
                    outcome=outcome,
                )
            except Exception as e:
                logger.error(f"Failed to end interaction {external_id}: {str(e)}")
    
    def get_active_sessions(self) -> Dict[str, AgentSession]:
        """Get all active sessions."""
        return self.active_sessions.copy()
    
    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.active_sessions)

    def find_session_id_by_external_id(self, external_id: str) -> Optional[str]:
        """Find the internal session_id by a known external_id (e.g., TermCallID/OrigCallID/streamId)."""
        if not external_id:
            return None
        for sid, sess in self.active_sessions.items():
            try:
                if getattr(sess, "external_id", None) == external_id:
                    return sid
            except Exception:
                continue
        return None

    async def end_session_by_external_id(self, external_id: str) -> bool:
        """End a session referenced by external_id if present.
        Returns True if a session was found and ended, False otherwise.
        """
        sid = self.find_session_id_by_external_id(external_id)
        if not sid:
            return False
        await self.end_session(sid)
        return True
