from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class Business(BaseModel):
    id: Optional[int] = None
    name: str
    domain: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("metadata", mode="before")
    @classmethod
    def _parse_metadata(cls, v):
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
    def from_db_row(cls, row: Dict[str, Any]) -> "Business":
        """Construct from a DB row dict; relies on validators for coercion."""
        return cls(**row)

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }
