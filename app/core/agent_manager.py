from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import LlmAgent
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import random
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
import google.genai.types as genai_types
import re

def get_current_time(time_zone: str) -> str:
    """Get the current time with robust timezone fallback.
    
    Args:
        time_zone: IANA timezone name (e.g., "America/Denver").
    Returns:
        str: The current time in the format "Month Day, Year at HH:MM AM/PM".
    """
    try:
        tz = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        # Fallback for legacy aliases or missing tzdata
        fallback = "America/New_York" if time_zone in ("US/Eastern", "EST", "America/New_York") else "UTC"
        try:
            tz = ZoneInfo(fallback)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
    current_time = datetime.now(tz)
    formatted = current_time.strftime("%B %d, %Y at %I:%M %p")
    return formatted

def get_mcp_tools(mcp_server_urls: list[str] | None = None):
    toolsets = []
    if mcp_server_urls:
        for url in mcp_server_urls:
            toolset =  MCPToolset( 
                connection_params=StreamableHTTPConnectionParams(
                    server_name='MCP Toolset ' + str(len(toolsets) + 1),
                    url=url,    
                )
            )
            toolsets.append(toolset)
    return toolsets

def create_agent(user_id, domain, *, system_prompt: str | None = None, mcp_server_urls: list[str] | None = None):
        """Create an agent for a specific domain.
        
        Args:
            user_id: The user identifier
            domain: The business domain
            system_prompt: Optional system prompt from DB
            mcp_server_urls: Optional MCP server URLs array from DB
        
        Returns:
            LlmAgent: The configured agent
        """
        #Define Hangup function and Tools
        async def hangup():
            """
            Hangup also known as end the call.
            First speak a goodbye to the user then immediately use this function to hangup so that resources are not wasted.
            Call this function before ending the turn when saying goodbye or have a great day.
            """
            from .netsapiens_handler import netsapiens_handler
            print("ENDING CALL")
            await netsapiens_handler.send_stop_to_netsapiens(user_id)

        mcp_toolsets = get_mcp_tools(mcp_server_urls)
        tools = [hangup]
        if mcp_toolsets:
            tools.extend(mcp_toolsets)
        
        #Add the prompt to the instruction
        instruction = (system_prompt or "Something is wrong please try again later.") + "\n\nCurrent Time: " + get_current_time("America/New_York")
        #Make sure the domain is cleaned for naming agent - It should start with a letter (a-z, A-Z) or an underscore (_), and can only contain letters, digits (0-9), and underscores. -
        agent_name = re.sub(r'[^a-zA-Z0-9_]', '', domain)
        agent_config = {
            'name': f'agent_{agent_name}',
            'instruction': instruction,
            'tools': tools,
            'model': 'gemini-live-2.5-flash-preview-native-audio',
            'generate_content_config' : genai_types.GenerateContentConfig(
                temperature=0.77
            )   
        }
        
        # 3. Create the agent
        agent = LlmAgent(**agent_config)
        
        return agent
