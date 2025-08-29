"""Agent session management for Google ADK integration."""

import asyncio
import logging
from typing import Dict, Optional, Any
from fastapi import WebSocket
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions.in_memory_session_service import InMemorySessionService
import uuid
from .agent_manager import create_agent
from .audio_processor import AudioProcessor
from google.genai.types import Blob, Content, Part
from google.genai import types
from datetime import datetime
logger = logging.getLogger(__name__)

# Application name for ADK
APP_NAME = "connectai_server"

session_service = InMemorySessionService()

async def start_agent_session(user_id: str, domain: str, is_audio: bool = False):
    """Starts an ADK agent session.
    
    Args:
        user_id: User identifier
        domain: Business domain
        is_audio: Whether to enable audio streaming
        
    Returns:
        Tuple of (live_events, live_request_queue)
    """
    try:
        # TODO: Replace with actual agent creation based on business domain
        # For now, create a dummy agent placeholder
        dummy_agent = create_agent(user_id, domain)
        
        # Create a Runner
        runner = Runner(
            app_name=APP_NAME,
            agent=dummy_agent,
            session_service=session_service,
        )
        
        # Create a Session
        session = await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        )
        
        # Set response modality
        voice_config = types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfigDict(
                voice_name='Sulafat'
            )
        )
        speech_config = types.SpeechConfig(voice_config=voice_config)
        run_config = RunConfig(response_modalities=["AUDIO"],
         speech_config=speech_config,
         output_audio_transcription=types.AudioTranscriptionConfig(),
         input_audio_transcription=types.AudioTranscriptionConfig(),
         )
        
        # Create a LiveRequestQueue for this session
        live_request_queue = LiveRequestQueue()
        
        # Start agent session
        live_events = runner.run_live(
            session=session,
            live_request_queue=live_request_queue,
            run_config=run_config,
        )
        
        logger.info(f"ADK session started for user: {user_id}, audio: {is_audio}, live_events type: {type(live_events)}")
        return live_events, live_request_queue
        
    except Exception as e:
        logger.error(f"Failed to start ADK session for user {user_id}: {str(e)}")
        raise

class AgentSession:
    """Represents an active agent session."""
    
    def __init__(self, session_id: str, business_domain: str, websocket: WebSocket):
        self.session_id = session_id
        self.business_domain = business_domain
        self.websocket = websocket
        self.adk_session = None
        self.live_events = None
        self.live_request_queue = None
        self.is_active = False
        self.created_at = asyncio.get_event_loop().time()
    
    async def start_adk_session(self):
        """Start the Google ADK session."""
        try:
            # Start ADK agent session with audio support
            self.live_events, self.live_request_queue = await start_agent_session(
                user_id=self.session_id,
                domain=self.business_domain,
                is_audio=True  # Enable audio streaming
            )
            self.is_active = True
            logger.info(f"ADK session started for: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start ADK session {self.session_id}: {str(e)}")
            return False
    
    async def stop_adk_session(self):
        """Stop the Google ADK session."""
        try:
            if self.adk_session:
                await self.adk_session.stop()
            self.is_active = False
            logger.info(f"ADK session stopped for: {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error stopping ADK session {self.session_id}: {str(e)}")

class AgentSessionManager:
    """Manages active agent sessions with Google ADK."""
    
    def __init__(self):
        self.active_sessions: Dict[str, AgentSession] = {}
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self.audio_processor = AudioProcessor()
    
    async def start_session(self, session_id: str, business_domain: str, websocket: WebSocket) -> bool:
        """Start a new agent session."""
        try:
            # Create session
            session = AgentSession(session_id, business_domain, websocket)
            
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
                        await task
                    except asyncio.CancelledError:
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
    
    async def _agent_to_netsapiens_loop(self, session: AgentSession):
        """Handle messages from agent to NetSapiens."""
        try:
            if not session.live_events:
                logger.warning(f"No live_events for session {session.session_id}")
                return
            
            logger.info(f"Starting agent-to-NetSapiens loop for {session.session_id}, live_events type: {type(session.live_events)}")
            
            async for event in session.live_events:
                await self._process_agent_event(session, event)
                
        except Exception as e:
            logger.error(f"Error in agent-to-NetSapiens loop {session.session_id}: {str(e)}")
            logger.exception("Full traceback:")
    
    async def _process_agent_event(self, session: AgentSession, event: Any):
        """Process events from the agent."""
        try:
            logger.debug(f"Processing agent event type: {type(event).__name__}")
            
            # All event data is in content
            if hasattr(event, 'content') and event.content:
                # Process each part in the content
                for part in event.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # This is binary data (audio)
                        blob = part.inline_data
                        if blob.mime_type and 'audio' in blob.mime_type:
                            logger.info(f"Received audio from agent: {len(blob.data)} bytes")
                            await self._handle_audio_data(session, blob.data)
                    elif hasattr(part, 'text') and part.text:
                        # This is text content
                        logger.info(f"Received text from agent: {part.text[:50]}...")
                        await self._handle_agent_text_response(session, part.text)
            
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
    
    async def _handle_agent_text_response(self, session: AgentSession, text: str):
        """Handle text response from agent."""
        # For now, we'll send text responses back to NetSapiens
        # In production, you might want to convert to speech first
        from .netsapiens_handler import netsapiens_handler
        await netsapiens_handler.send_response_to_netsapiens(
            session.session_id,
            "text_response",
            {"text": text}
        )
    
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
        
        # End the session when call ends
        await self.end_session(session_id)
    
    def get_active_sessions(self) -> Dict[str, AgentSession]:
        """Get all active sessions."""
        return self.active_sessions.copy()
    
    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.active_sessions)
