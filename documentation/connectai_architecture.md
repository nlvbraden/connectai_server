# ConnectAI Server Architecture

## Overview
ConnectAI is an AI-powered voice interaction system that integrates with UCaaS (Unified Communications as a Service) platforms to provide intelligent, real-time call handling with dynamic agent configuration.

## High-Level System Flow

```mermaid
graph TB
    subgraph "UCaaS Platforms"
        NS[NetSapiens/ConnectWare/PhoneSuite]
    end
    
    subgraph "ConnectAI Server"
        WS[WebSocket Handler]
        SM[Session Manager]
        AP[Audio Processor]
        AM[Agent Manager]
        DB[(PostgreSQL Database)]
    end
    
    subgraph "Google Cloud - Gemini Realtime"
        GEMINI[Multimodal AI Model<br/>Processes Audio Natively]
        TRANS[Transcript Events<br/>Optional Output]
    end
    
    subgraph "External Services"
        TOOLS[Dynamic Tools<br/>- Search<br/>- Databases<br/>- APIs]
    end
    
    NS -->|WebSocket Connection| WS
    WS -->|Audio Stream| SM
    SM -->|Raw Audio| AP
    AP -->|Audio Tokens| GEMINI
    GEMINI -->|Audio Response| AP
    GEMINI -.->|Live Transcripts| TRANS
    TRANS -.->|Text Events| SM
    AP -->|Converted Audio| SM
    SM -->|Audio Stream| WS
    WS -->|Audio Response| NS
    
    GEMINI <-->|Tool Calls| AM
    AM <-->|Query/Response| TOOLS
    SM <-->|Session Data| DB
    
    style NS fill:#e1f5fe
    style GEMINI fill:#fff3e0
    style DB fill:#f3e5f5
    style TRANS fill:#e8f5e9
```

## How Gemini Realtime Differs from Traditional Voice AI

```mermaid
graph LR
    subgraph "Traditional Pipeline Approach"
        A1[Audio Input] --> STT1[Speech-to-Text]
        STT1 --> LLM[Language Model]
        LLM --> TTS1[Text-to-Speech]
        TTS1 --> A2[Audio Output]
    end
    
    subgraph "Gemini Realtime Approach"
        B1[Audio Input] --> GM[Gemini Multimodal<br/>Audio → Audio<br/>Direct Processing]
        GM --> B2[Audio Output]
        GM -.->|Optional| TR[Transcripts]
    end
    
    style STT1 fill:#ffcdd2
    style LLM fill:#fff9c4
    style TTS1 fill:#c5e1a5
    style GM fill:#e1bee7
    style TR fill:#b2dfdb
```

### Key Differences:
- **No Pipeline Latency**: Audio is processed as audio, not converted to text and back
- **Natural Conversation**: Understands tone, emotion, interruptions, and overlapping speech
- **Audio-Native Reasoning**: The model "thinks" in audio tokens, preserving nuance
- **Transcripts as Features**: Text transcripts are generated for monitoring/logging, not as part of the processing flow

## Detailed Component Interaction

```mermaid
sequenceDiagram
    participant UC as UCaaS Platform
    participant WS as WebSocket Handler
    participant SM as Session Manager
    participant AP as Audio Processor
    participant AM as Agent Manager
    participant GA as Gemini Realtime<br/>(Multimodal Model)
    participant DB as Database
    
    Note over UC,DB: Call Initiation & Setup
    UC->>WS: WebSocket Connection (SIP Headers)
    WS->>SM: Create Session
    SM->>DB: Store Session Info
    SM->>AM: Initialize Agent (based on routing)
    AM->>GA: Create Gemini Session
    
    Note over UC,DB: Real-time Audio Processing
    loop During Call
        UC->>WS: Audio Chunk (μ-law/8kHz)
        WS->>SM: Forward Audio
        SM->>AP: Process Audio
        AP->>AP: Convert μ-law to PCM16
        AP->>GA: Stream Audio Tokens
        
        Note over GA: Multimodal Processing<br/>Audio → Understanding → Response<br/>(Single model, not pipeline)
        
        GA-->>AM: Tool Calls (if needed)
        AM-->>GA: Tool Results
        
        GA-->>AP: Audio Response Stream
        GA-->>SM: Transcript Events (optional output)
        
        AP->>AP: Convert PCM16 to μ-law
        AP->>SM: Processed Audio
        SM->>WS: Audio Stream
        WS->>UC: Audio Response
        
        Note right of GA: Gemini processes audio<br/>natively - transcripts are<br/>a feature, not the flow
    end
    
    Note over UC,DB: Call Termination
    UC->>WS: Disconnect Signal
    WS->>SM: End Session
    SM->>DB: Update Session & Transcripts
    SM->>AM: Cleanup Agent
    AM->>GA: Close Session
```

## Dynamic Configuration System

```mermaid
graph LR
    subgraph "Configuration Layer"
        RC[Route Configuration]
        AC[Agent Configuration]
        TC[Tool Configuration]
        PC[Prompt Configuration]
    end
    
    subgraph "Routing Logic"
        SIP[SIP Headers]
        DN[Dialed Number]
        BD[Business Domain]
        CID[Caller ID]
    end
    
    subgraph "Agent Selection"
        CS[Customer Service Agent]
        TS[Technical Support Agent]
        SA[Sales Agent]
        CA[Custom Agent]
    end
    
    SIP --> RC
    DN --> RC
    CID --> RC
    RC --> BD
    BD --> AC
    AC --> CS
    AC --> TS
    AC --> SA
    AC --> CA
    
    TC --> CS
    TC --> TS
    TC --> SA
    TC --> CA
    
    PC --> CS
    PC --> TS
    PC --> SA
    PC --> CA
    
    style RC fill:#ffecb3
    style AC fill:#c8e6c9
    style TC fill:#b3e5fc
    style PC fill:#f8bbd0
```

## Audio Processing Pipeline

```mermaid
graph LR
    subgraph "Inbound Audio"
        IA1[UCaaS Audio<br/>μ-law 8kHz]
        IA2[Decode μ-law]
        IA3[Convert to PCM16]
        IA4[Resample to 16kHz]
        IA5[Stream to Gemini]
    end
    
    subgraph "Outbound Audio"
        OA1[Gemini Audio<br/>PCM16 24kHz]
        OA2[Resample to 8kHz]
        OA3[Convert to μ-law]
        OA4[Encode for UCaaS]
        OA5[Stream to Caller]
    end
    
    IA1 --> IA2 --> IA3 --> IA4 --> IA5
    OA1 --> OA2 --> OA3 --> OA4 --> OA5
    
    style IA1 fill:#e3f2fd
    style IA5 fill:#e8f5e9
    style OA1 fill:#e8f5e9
    style OA5 fill:#e3f2fd
```

## Live Transcription Flow

```mermaid
graph TB
    subgraph "Real-time Transcription (Feature Output)"
        AS[Audio Conversation]
        GA[Gemini Realtime<br/>Multimodal Model]
        RT[Transcript Events<br/>Side Output]
        WC[WebSocket Client]
        UI[UI Dashboard]
        DB[(Transcript Storage)]
    end
    
    AS -->|Audio Processing| GA
    GA -.->|Optional Events| RT
    RT -->|JSON Stream| WC
    WC -->|Display| UI
    RT -->|Store| DB
    
    Note1[Transcripts are generated<br/>alongside audio processing:<br/>- User speech<br/>- Agent responses<br/>- Timestamps<br/>- Tool calls<br/>- Interim/Final results]
    
    Note2[The model processes<br/>and responds to audio<br/>directly - transcripts<br/>are for visibility]
    
    RT -.-> Note1
    GA -.-> Note2
    
    style GA fill:#e1bee7
    style RT fill:#c5e1a5
    style UI fill:#b2dfdb
```

## Database Schema

```mermaid
erDiagram
    SESSIONS {
        uuid id PK
        string call_id
        string caller_number
        string called_number
        timestamp start_time
        timestamp end_time
        json metadata
    }
    
    TRANSCRIPTS {
        uuid id PK
        uuid session_id FK
        string speaker
        string text
        float confidence
        timestamp timestamp
        boolean is_final
    }
    
    AGENTS {
        uuid id PK
        string name
        string type
        json configuration
        json tools
        text system_prompt
    }
    
    ROUTES {
        uuid id PK
        string pattern
        string business_domain
        uuid agent_id FK
        json conditions
        boolean active
    }
    
    SESSIONS ||--o{ TRANSCRIPTS : generates
    ROUTES ||--|| AGENTS : uses
    SESSIONS }o--|| AGENTS : assigned
```

## Key Features for Product Managers

### 1. **Dynamic Agent Configuration**
- Agents can be configured per business domain
- Custom prompts and personalities
- Tool access control (search, databases, APIs)
- Real-time configuration updates without restarts

### 2. **Multi-Platform Support**
- NetSapiens integration
- ConnectWare compatibility
- PhoneSuite support
- Extensible for other UCaaS platforms

### 3. **Real-time Capabilities**
- Live call transcription
- Instant AI responses
- Stream processing (no recording needed)
- Low-latency audio processing

### 4. **Business Intelligence**
- Call analytics and metrics
- Transcript storage and search
- Agent performance tracking
- Custom reporting capabilities

### 5. **Scalability**
- Microservices architecture
- Horizontal scaling support
- Load balancing ready
- Cloud-native design

## Technical Integration Points

### For VoIP Developers

1. **WebSocket Protocol**
   - Standard WSS connection
   - SIP header passthrough
   - Binary audio frames
   - JSON control messages

2. **Audio Formats**
   - Input: μ-law 8kHz (standard telephony)
   - Processing: PCM16 16kHz/24kHz
   - Output: μ-law 8kHz
   - Real-time conversion

3. **API Endpoints**
   ```
   POST /api/sessions/create
   GET  /api/sessions/{id}/transcript
   POST /api/agents/configure
   GET  /api/metrics/calls
   ```

4. **Event Streams**
   - Call start/end events
   - Transcription events
   - Agent action events
   - Error notifications

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        LB[Load Balancer]
        subgraph "Application Tier"
            CS1[ConnectAI Server 1]
            CS2[ConnectAI Server 2]
            CS3[ConnectAI Server N]
        end
        subgraph "Data Tier"
            PG[(PostgreSQL)]
            RD[(Redis Cache)]
        end
        subgraph "Monitoring"
            PM[Prometheus]
            GF[Grafana]
            ELK[ELK Stack]
        end
    end
    
    subgraph "External Services"
        GCP[Google Cloud Platform]
        UCaaS[UCaaS Platforms]
    end
    
    UCaaS -->|WebSocket| LB
    LB --> CS1
    LB --> CS2
    LB --> CS3
    
    CS1 --> PG
    CS2 --> PG
    CS3 --> PG
    
    CS1 --> RD
    CS2 --> RD
    CS3 --> RD
    
    CS1 --> GCP
    CS2 --> GCP
    CS3 --> GCP
    
    CS1 -.-> PM
    CS2 -.-> PM
    CS3 -.-> PM
    
    PM --> GF
    CS1 -.-> ELK
    CS2 -.-> ELK
    CS3 -.-> ELK
    
    style LB fill:#ffccbc
    style PG fill:#c5cae9
    style GCP fill:#fff3e0
```

## Benefits Summary

### For Product Managers
- **Reduced Call Center Costs**: AI handles routine inquiries
- **24/7 Availability**: No human agent limitations
- **Consistent Service**: Standardized responses
- **Scalability**: Handle unlimited concurrent calls
- **Analytics**: Deep insights into customer interactions

### For VoIP Developers
- **Standard Protocols**: WebSocket, SIP, RTP compatible
- **Easy Integration**: RESTful APIs and webhooks
- **Format Agnostic**: Handles multiple audio codecs
- **Real-time Processing**: Sub-second latency
- **Debugging Tools**: Comprehensive logging and monitoring

## Understanding the Multimodal Architecture

### What Makes This Different

Unlike traditional voice AI systems that chain together separate STT → LLM → TTS services, Gemini Realtime is a **single multimodal model** that:

1. **Processes Audio Natively**: The model receives audio tokens and generates audio tokens directly
2. **Maintains Audio Context**: Understands interruptions, tone, pace, emotion without converting to text
3. **Reasons in Audio Space**: The AI's "thinking" happens in the audio domain, not text
4. **Provides Transcripts as Output**: Text transcripts are generated for human visibility, not for processing

### Live Transcript Feature

The system provides real-time transcripts as a **monitoring feature**:

1. **Parallel Generation**: Transcripts are generated alongside (not before) audio responses
2. **WebSocket Distribution**: Transcript events stream to connected clients
3. **Dual Output**: Both interim (partial) and final transcripts for real-time display
4. **Rich Metadata**: Includes timestamps, tool calls, and conversation turns
5. **Storage**: All transcripts saved to database for compliance and analytics
6. **API Access**: REST endpoints to fetch historical transcripts

This enables:
- Live monitoring of ongoing calls
- Real-time coaching capabilities
- Compliance recording
- Quality assurance
- Customer insight gathering

### Technical Implications

For VoIP developers, this means:
- **Lower Latency**: No STT/TTS conversion delays (~300-500ms faster)
- **Better Interruption Handling**: Natural conversation flow with barge-in support
- **Preserved Audio Nuance**: Emotion and tone inform responses
- **Simplified Architecture**: One model instead of three services
- **Consistent Voice**: No TTS voice selection needed

---

*This document provides a comprehensive overview of the ConnectAI server architecture. The system is designed to be modular, scalable, and easily configurable to meet various business needs while integrating seamlessly with existing UCaaS infrastructure.*