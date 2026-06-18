"""HMAC-SHA256 signing for webhook payloads.

paris-mock signs outbound webhooks with this; the Phase 3 webhook receiver
verifies inbound ones with the same scheme.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Paris-Signature"


def sign_payload(secret: str, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``body`` keyed by ``secret``."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Constant-time check that ``signature`` matches ``body``."""
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, signature)
