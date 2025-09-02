from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class Interaction(BaseModel):
    id: Optional[int] = None
    business_id: Optional[int] = None
    agent_id: Optional[int] = None
    external_id: str #Connectware Call ID - origCallID or callID
    customer_identifier: Optional[str] = None

    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    summary: Optional[str] = None
    sentiment: Optional[str] = None
    outcome: Optional[str] = None
    analytics: Optional[Dict[str, Any]] = None

    created_at: Optional[datetime] = None

    @field_validator("analytics", mode="before")
    @classmethod
    def _parse_analytics(cls, v):
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
    def from_db_row(cls, row: Dict[str, Any]) -> "Interaction":
        return cls(**row)

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }
