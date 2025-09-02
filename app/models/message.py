from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    id: Optional[int] = None
    interaction_id: int
    role: str  # 'user' | 'assistant' | 'system'
    content: Optional[str] = None
    function_calls: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None

    @field_validator("function_calls", mode="before")
    @classmethod
    def _parse_function_calls(cls, v):
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
        return None

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Message":
        return cls(**row)

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }
