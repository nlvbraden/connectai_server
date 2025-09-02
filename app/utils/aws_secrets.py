"""AWS Secrets Manager loader utilities.

This utility loads key/value environment settings from one secret (env secret)
And loads the Gemini service account JSON from another secret, writes it to a
secure temporary file, and sets env vars pointing to it.

Env variables used (optional):
- ENV_SECRETS_ARN or AWS_ENV_SECRETS_ARN: ARN or name of the env secret (JSON mapping)
- GEMINI_SERVICE_ACCOUNT_SECRET_ARN or GEMINI_KEY_SECRET_ARN: ARN or name of the Gemini SA JSON secret
- AWS_REGION: AWS region for the Secrets Manager client (falls back to default chain)
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Optional
import logging

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - optional dependency in some envs
    boto3 = None
    BotoCoreError = ClientError = Exception

ENV_SECRET_NAME = "nlv-prod-connectai-env-vars"
GEMINI_SECRET_NAME = "nlv-prod-connectai-gcp-service-account-key"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

logger = logging.getLogger(__name__)

class AwsSecretsLoader:
    def __init__(
        self,
    ) -> None:
        self.region_name = AWS_REGION

        self._client = None
        if boto3 is not None:
            try:
                # region_name may be None; boto3 will fall back to config/instance metadata
                self._client = boto3.client("secretsmanager", region_name=self.region_name)
            except Exception:
                # Defer errors until actual calls
                logger.error("Failed to initialize AWS Secrets Manager client", exc_info=True)
                self._client = None

    def _get_secret_string(self, secret_id: str) -> Optional[str]:
        if not self._client:
            logger.error("AWS Secrets Manager client not initialized")
            return None
        try:
            resp = self._client.get_secret_value(SecretId=secret_id)
            if "SecretString" in resp and resp["SecretString"]:
                return resp["SecretString"]
            # If it's binary, attempt to decode
            if "SecretBinary" in resp and resp["SecretBinary"]:
                try:
                    return resp["SecretBinary"].decode("utf-8")
                except Exception:
                    return None
        except (BotoCoreError, ClientError):
            logger.error(f"Failed to get secret {secret_id}", exc_info=True)
            return None

    def load_env_secret(self) -> Dict[str, str]:
        """Load key/value pairs from the env secret into os.environ.
        The secret must be a JSON object mapping.
        """
        updated: Dict[str, str] = {}
        secret_str = self._get_secret_string(ENV_SECRET_NAME)
        if not secret_str:
            return updated

        try:
            data = json.loads(secret_str)
            if not isinstance(data, dict):
                return updated
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    # store complex values as compact JSON strings
                    v = json.dumps(v)
                if v is None:
                    continue
                os.environ[str(k)] = str(v)
                updated[str(k)] = str(v)
        except json.JSONDecodeError:
            # Not JSON; best-effort parse key=value lines
            for line in secret_str.splitlines():
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k:
                        os.environ[k] = v
                        updated[k] = v
        except Exception:
            logger.error("Failed to load env secret", exc_info=True)
        return updated

    def load_gemini_key_secret(self) -> Optional[str]:
        """Fetch Gemini service account JSON and write it to a temp file.
        Returns path to the written JSON, or None if unavailable.
        """
        secret_str = self._get_secret_string(GEMINI_SECRET_NAME)
        if not secret_str:
            return None

        # Validate it's JSON
        try:
            json.loads(secret_str)
        except json.JSONDecodeError:
            return None

        # Write to a secure temp file
        temp_dir = tempfile.mkdtemp(prefix="gemini_key_")
        key_path = os.path.join(temp_dir, "gemini_service_account.json")
        with open(key_path, "w") as f:
            f.write(secret_str)

        # Set environment variables for consumers
        os.environ["GEMINI_SERVICE_ACCOUNT_KEY_PATH"] = key_path
        # Also set Google default credentials env for cloud libs
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", key_path)
        return key_path

    def load_all(self) -> Dict[str, str]:
        updated = self.load_env_secret()
        self.load_gemini_key_secret()
        return updated
