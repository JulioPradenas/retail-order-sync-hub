"""Secret Manager loader (V2).

In production on GCP, secrets (HMAC keys, OAuth client secret) live in Secret
Manager instead of ``.env``. ``load_secrets_into_env`` fetches each configured
secret and injects it as an environment variable *before* ``Settings`` parses,
so the rest of the code is unchanged. Disabled by default; when the client or a
secret is unavailable it logs and skips rather than crashing the boot.
"""

from __future__ import annotations

import os

from src.common.logging import get_logger

log = get_logger()


def _secret_env_name(secret_id: str) -> str:
    """Map a secret id to its env var (``paris-api-secret`` -> ``PARIS_API_SECRET``)."""
    return secret_id.replace("-", "_").upper()


def load_secrets_into_env(
    *,
    project_id: str,
    secret_ids: list[str],
    version: str = "latest",
) -> int:
    """Fetch ``secret_ids`` from Secret Manager and set them as env vars.

    Returns the number of secrets successfully loaded. Existing env vars are not
    overwritten, so a local ``.env`` still wins during development.
    """
    if not project_id or not secret_ids:
        return 0

    try:
        from google.cloud import secretmanager
    except ImportError:
        log.warning(
            "secrets.client_unavailable", reason="google-cloud-secret-manager not installed"
        )
        return 0

    client = secretmanager.SecretManagerServiceClient()
    loaded = 0
    for secret_id in secret_ids:
        env_name = _secret_env_name(secret_id)
        if os.environ.get(env_name):
            continue
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
        try:
            response = client.access_secret_version(name=name)
            os.environ[env_name] = response.payload.data.decode("utf-8")
            loaded += 1
        except Exception as exc:
            log.warning("secrets.fetch_failed", secret_id=secret_id, error=str(exc))
    log.info("secrets.loaded", count=loaded, requested=len(secret_ids))
    return loaded


def maybe_load_secrets() -> int:
    """Load secrets when ``USE_SECRET_MANAGER`` is enabled, reading raw env (pre-Settings).

    Called at the very start of a service's ``main()`` so values land in the env
    before ``get_settings()`` parses them.
    """
    if os.environ.get("USE_SECRET_MANAGER", "").lower() not in ("1", "true", "yes"):
        return 0
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("BQ_PROJECT_ID", "")
    raw = os.environ.get("SECRET_MANAGER_SECRETS", "PARIS_API_SECRET,ML_WEBHOOK_SECRET")
    secret_ids = [s.strip() for s in raw.split(",") if s.strip()]
    return load_secrets_into_env(project_id=project_id, secret_ids=secret_ids)
