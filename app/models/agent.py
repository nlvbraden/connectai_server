from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class Agent(BaseModel):
    id: Optional[int] = None
    business_id: Optional[int] = None
    name: str
    voice_name: Optional[str] = "Sulafat"
    system_prompt: Optional[str] = None
    mcp_server_urls: Optional[List[str]] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("mcp_server_urls", mode="before")
    @classmethod
    def _parse_urls(cls, v):
        # Accept list, JSON string, comma-separated string, or None
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                import json
                loaded = json.loads(v)
                if isinstance(loaded, list):
                    return loaded
            except Exception:
                pass
            # Fallback: split by comma
            return [s.strip() for s in v.split(",") if s and s.strip()]
        return v

    @field_validator("config", mode="before")
    @classmethod
    def _parse_config(cls, v):
        if v is None or isinstance(v, dict):
            return v or {}
        if isinstance(v, str):
            try:
                import json
                loaded = json.loads(v)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass
        return {}

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Agent":
        return cls(**row)

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }
