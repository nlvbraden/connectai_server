"""Agent session management for Google ADK integration."""
import asyncio
from typing import Optional
from fastapi import WebSocket
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from ..agent_manager import create_agent
from google.genai import types
from datetime import datetime
from ...models import Agent, Interaction

# Logging
import logging
logger = logging.getLogger(__name__)

# Application name for ADK
APP_NAME = "connectai_server"

session_service = InMemorySessionService()

async def start_agent_session(
    user_id: str,
    domain: str,
    is_audio: bool = False,
    *,
    agent: Optional[Agent] = None,
):
    """Starts an ADK agent session.
    
    Args:
        user_id: User identifier
        domain: Business domain
        is_audio: Whether to enable audio streaming
        
    Returns:
        Tuple of (runner, session, live_events, live_request_queue)
    """
    try:
        # TODO: Replace with actual agent creation based on business domain
        # For now, create a dummy agent placeholder
        dummy_agent = create_agent(user_id, domain, system_prompt=agent.system_prompt if agent else None, mcp_server_urls=agent.mcp_server_urls if agent else None)
        
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
                voice_name=(agent.voice_name if agent else 'Sulafat')
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
        return runner, session, live_events, live_request_queue
        
    except Exception as e:
        logger.error(f"Failed to start ADK session for user {user_id}: {str(e)}")
        raise

class AgentSession:
    """Represents an active agent session."""
    
    def __init__(self, session_id: str, business_domain: str, websocket: WebSocket,
                 *, 
                 agent: Optional[Agent] = None,
                 interaction: Optional[Interaction] = None,
                 external_id: Optional[str] = None):
        self.session_id = session_id
        self.business_domain = business_domain
        self.websocket = websocket
        self.adk_session = None
        self.runner = None
        self.live_events = None
        self.live_request_queue = None
        self.is_active = False
        self.created_at = asyncio.get_event_loop().time()
        # DB-driven config & logging ids
        self.agent = agent
        self.interaction = interaction
        self.external_id = external_id
    
    async def start_adk_session(self):
        """Start the Google ADK session."""
        try:
            # Start ADK agent session with audio support
            self.runner, self.adk_session, self.live_events, self.live_request_queue = await start_agent_session(
                user_id=self.session_id,
                domain=self.business_domain,
                is_audio=True,  # Enable audio streaming
                agent=self.agent,
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
            # Mark inactive first to gate any further processing
            self.is_active = False

            # Attempt to close the live request queue gracefully
            if self.live_request_queue:
                try:
                    if hasattr(self.live_request_queue, "close"):
                        self.live_request_queue.close()  # type: ignore[attr-defined]
                    elif hasattr(self.live_request_queue, "end_input"):
                        self.live_request_queue.end_input()  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Attempt to close the live events async generator
            if self.live_events and hasattr(self.live_events, "aclose"):
                try:
                    await self.live_events.aclose()  # type: ignore[attr-defined]
                except Exception:
                    pass

            # If the runner exposes any shutdown method, try to call it
            if self.runner:
                try:
                    if hasattr(self.runner, "close"):
                        await self.runner.close()  # type: ignore[attr-defined]
                    elif hasattr(self.runner, "shutdown"):
                        await self.runner.shutdown()  # type: ignore[attr-defined]
                except Exception:
                    pass
            logger.info(f"ADK session stopped for: {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error stopping ADK session {self.session_id}: {str(e)}")
