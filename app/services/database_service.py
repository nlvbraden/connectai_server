"""Service for database operations via AWS RDS Data API (Aurora Serverless Postgres)."""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
import boto3
from botocore.client import BaseClient
from botocore.config import Config

from ..utils.logging import get_logger
from ..settings import settings
from ..models import Business, Agent, Interaction, Message

logger = get_logger(__name__)


def _to_sql_param(name: str, value: Any) -> Dict[str, Any]:
    """Convert Python value to RDS Data API parameter."""
    param: Dict[str, Any] = {"name": name, "value": {}}
    if value is None:
        param["value"]["isNull"] = True
    elif isinstance(value, bool):
        param["value"]["booleanValue"] = value
    elif isinstance(value, int):
        param["value"]["longValue"] = value
    elif isinstance(value, float):
        param["value"]["doubleValue"] = value
    elif isinstance(value, (list, tuple)):
        # Represent arrays as JSON text for portability
        param["value"]["stringValue"] = json.dumps(value)
    elif isinstance(value, (dict,)):
        # JSONB fields as JSON text
        param["value"]["stringValue"] = json.dumps(value)
    else:
        param["value"]["stringValue"] = str(value)
    return param


def _rows_to_dicts(records: List[Dict[str, Any]], column_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert RDS Data API records into a list of dicts.

    RDS Data API returns each field as a dict with exactly one of the keys:
    stringValue | longValue | doubleValue | booleanValue | isNull | blobValue | arrayValue
    """
    def _field_to_py(field: Dict[str, Any]) -> Any:
        if field.get("isNull"):
            return None
        if "stringValue" in field:
            return field["stringValue"]
        if "longValue" in field:
            return field["longValue"]
        if "doubleValue" in field:
            return field["doubleValue"]
        if "booleanValue" in field:
            return field["booleanValue"]
        if "blobValue" in field:
            return field["blobValue"]
        if "arrayValue" in field:
            arr = field["arrayValue"]
            # Prefer explicit typed lists if present
            for k in ("stringValues", "longValues", "doubleValues", "booleanValues"):
                if k in arr:
                    return arr[k]
            # Fallback: generic list of value objects under 'values'
            if "values" in arr and isinstance(arr["values"], list):
                return [_field_to_py(v) for v in arr["values"]]
        # Unknown structure – return as-is for visibility
        return field

    cols = [c.get("name") for c in column_metadata]
    out: List[Dict[str, Any]] = []
    for row in records:
        item: Dict[str, Any] = {}
        for col, field in zip(cols, row):
            item[col] = _field_to_py(field)
        out.append(item)
    return out


class DatabaseService:
    """Aurora Serverless Data API wrapper for business/agent and call logging."""

    def __init__(self):
        if not settings.rds_cluster_arn or not settings.rds_secret_arn or not settings.rds_db_name:
            missing = []
            if not settings.rds_cluster_arn:
                missing.append("RDS_CLUSTER_ARN")
            if not settings.rds_secret_arn:
                missing.append("RDS_SECRET_ARN")
            if not settings.rds_db_name:
                missing.append("RDS_DB_NAME")
            logger.warning(
                "RDS Data API not fully configured; missing: %s; aws_region=%s. "
                "DatabaseService will operate in no-op mode until configured.",
                ",".join(missing),
                settings.aws_region,
            )
        # Configure client with conservative timeouts/retries to avoid event loop hangs
        boto_cfg = Config(
            read_timeout=5,
            connect_timeout=3,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        self._client: BaseClient = boto3.client(
            "rds-data",
            region_name=settings.aws_region or None,
            config=boto_cfg,
        )
        self._db = settings.rds_db_name
        self._cluster = settings.rds_cluster_arn
        self._secret = settings.rds_secret_arn

    # (row mapping now handled by model constructors)

    def _exec(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not (self._cluster and self._secret and self._db):
            logger.error(
                "RDS Data API not configured. Skipping SQL. Present: cluster=%s, secret=%s, db=%s",
                bool(self._cluster), bool(self._secret), bool(self._db)
            )
            return []
        sql_params = []
        if params:
            sql_params = [_to_sql_param(k, v) for k, v in params.items()]
        try:
            resp = self._client.execute_statement(
                resourceArn=self._cluster,
                secretArn=self._secret,
                database=self._db,
                sql=sql,
                parameters=sql_params,
                includeResultMetadata=True,
            )
            print(f"RDS Data API execute response: {resp}")
            records = resp.get("records", [])
            metadata = resp.get("columnMetadata", [])
            return _rows_to_dicts(records, metadata) if records else []
        except Exception as e:
            logger.error(f"RDS Data API execute failed: {e}")
            return []

    # -------- Business & Agent Lookup --------

    def get_business_by_account_domain(self, account_domain: str) -> Optional[Business]:
        if not account_domain:
            return None
        print(f"\n\n\n---------------------------------------------------------\n\nSearching for Domain: {account_domain}\n\n\n---------------------------------------------------------\n\n\n")
        sql = """
            SELECT * FROM business
            WHERE domain = :account_domain
            LIMIT 1
        """
        rows = self._exec(sql, {"account_domain": account_domain})
        print(f"Rows from business lookup: {rows}")
        return Business.from_db_row(rows[0]) if rows else None


    def get_active_agent_for_business(self, business_id: int) -> Optional[Agent]:
        sql = """
            SELECT a.*
            FROM agent a
            WHERE a.business_id = :business_id AND a.is_active = true
            ORDER BY a.updated_at DESC
            LIMIT 1
        """
        rows = self._exec(sql, {"business_id": business_id})
        return Agent.from_db_row(rows[0]) if rows else None

    # -------- Interaction & Message Logging --------

    def create_interaction(
        self,
        *,
        call_id: str,
        business_id: Optional[int],
        agent_id: Optional[int],
        customer_identifier: Optional[str],
    ) -> Optional[Interaction]:
        sql = """
            INSERT INTO interaction (external_id, business_id, agent_id, customer_identifier, started_at)
            VALUES (:external_id, :business_id, :agent_id, :customer_identifier, NOW())
            ON CONFLICT (external_id)
            DO UPDATE SET external_id = EXCLUDED.external_id
            RETURNING id, external_id, business_id, agent_id, customer_identifier, started_at, ended_at
        """
        rows = self._exec(
            sql,
            {
                "external_id": call_id,
                "business_id": business_id,
                "agent_id": agent_id,
                "customer_identifier": customer_identifier,
            },
        )
        print(rows)
        return Interaction.from_db_row(rows[0]) if rows else None

    def end_interaction(
        self,
        *,
        external_id: str,
        outcome: Optional[str] = None,
        sentiment: Optional[str] = None,
        summary: Optional[str] = None,
        analytics: Optional[Dict[str, Any]] = None,
    ) -> Optional[Interaction]:
        sql = """
            UPDATE interaction
            SET ended_at = NOW(),
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int,
                outcome = COALESCE(:outcome, outcome),
                sentiment = COALESCE(:sentiment, sentiment),
                summary = COALESCE(:summary, summary),
                analytics = COALESCE(CAST(:analytics AS jsonb), analytics)
            WHERE external_id = :external_id
            RETURNING *
        """
        rows = self._exec(
            sql,
            {
                "external_id": external_id,
                "outcome": outcome,
                "sentiment": sentiment,
                "summary": summary,
                "analytics": analytics or None,
            },
        )
        return Interaction.from_db_row(rows[0]) if rows else None

    def insert_message(
        self,
        *,
        interaction: Interaction,
        role: str,
        content: Optional[str],
        function_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Message]:
        sql = """
            INSERT INTO message (interaction_id, role, content, function_calls)
            VALUES (:interaction_id, :role, :content, CAST(:function_calls AS jsonb))
            RETURNING *
        """
        rows = self._exec(
            sql,
            {
                "interaction_id": interaction.id,
                "role": role,
                "content": content,
                "function_calls": function_calls or None,
            },
        )
        return Message.from_db_row(rows[0]) if rows else None

    """Service for database operations."""