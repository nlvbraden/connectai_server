# ConnectAI Server

A modular, scalable AI agent server that integrates with NetSapiens WebResponder via bidirectional WebSocket streaming. The server dynamically creates domain-specific agents using Google Agent Development Kit (ADK) and Gemini Flash 2.5 Live API, loads business prompts and tools from a remote PostgreSQL database, and supports extensible tools and integrations.

## Features

- **Real-time Voice Communication**: Bidirectional WebSocket streaming with NetSapiens WebResponder
- **Dynamic AI Agents**: Business-specific agents created on-demand using Google ADK
- **Database-Driven Configuration**: Business prompts, tools, and knowledge loaded from PostgreSQL
- **Extensible Tool System**: Modular architecture for adding custom tools and integrations
- **Real-time Audio Processing**: μ-law to PCM conversion and audio stream handling
- **Comprehensive Monitoring**: Health checks, agent management, and session tracking