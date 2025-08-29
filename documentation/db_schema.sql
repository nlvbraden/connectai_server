-- Simplified Database Schema for MVP
-- Core focus: Businesses, Agents, Interactions, Analytics

-- =====================
-- Core Entities
-- =====================

-- Businesses using your platform
CREATE TABLE business (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    external_id TEXT UNIQUE, -- Your internal business identifier
    metadata JSONB DEFAULT '{}', -- Flexible field for extra data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI Agents configured per business
CREATE TABLE agent (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES business(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    voice_name TEXT DEFAULT 'Sulafat',
    system_prompt TEXT, -- The main prompt for the agent
    mcp_server_urls TEXT[], -- Array of MCP server URLs for tools
    config JSONB DEFAULT '{}', -- Any additional configuration
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================
-- Interaction Tracking
-- =====================

-- Conversations/Calls/Interactions
CREATE TABLE interaction (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES business(id),
    agent_id INTEGER REFERENCES agent(id),
    external_id TEXT UNIQUE, -- Your call/session ID
    customer_identifier TEXT, -- Phone number, email, or other ID
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER, -- Calculated after call ends
    
    -- Analytics fields (populated at end of call)
    summary TEXT, -- AI-generated summary
    sentiment TEXT, -- positive/negative/neutral
    outcome TEXT, -- resolved/transferred/dropped/etc
    analytics JSONB DEFAULT '{}', -- Flexible analytics data
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual messages within interactions
CREATE TABLE message (
    id SERIAL PRIMARY KEY,
    interaction_id INTEGER REFERENCES interaction(id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT,
    
    -- Optional: Store function calls inline with message
    function_calls JSONB, -- Array of {name, arguments, result} if you want to track
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================
-- Indexes for Performance
-- =====================

CREATE INDEX idx_agent_business ON agent(business_id) WHERE is_active = true;
CREATE INDEX idx_interaction_business ON interaction(business_id);
CREATE INDEX idx_interaction_dates ON interaction(started_at, ended_at);
CREATE INDEX idx_interaction_external ON interaction(external_id);
CREATE INDEX idx_message_interaction ON message(interaction_id);
CREATE INDEX idx_message_created ON message(created_at);

-- =====================
-- Optional: Simple Analytics Views
-- =====================

-- View for daily analytics
CREATE VIEW daily_interaction_stats AS
SELECT 
    business_id,
    DATE(started_at) as date,
    COUNT(*) as total_interactions,
    AVG(duration_seconds) as avg_duration,
    COUNT(CASE WHEN outcome = 'resolved' THEN 1 END) as resolved_count,
    COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count
FROM interaction
WHERE ended_at IS NOT NULL
GROUP BY business_id, DATE(started_at);