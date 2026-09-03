"""
Cryptographic User ID Token & Checksum Module for Frame Talk
Generates and verifies HMAC-SHA256 checksums on client user IDs to prevent
arbitrary random user generation and Sybil quota drain attacks.
"""

import hmac
import hashlib
import time
import secrets
from typing import Tuple, Optional
from server.core.config import config

def sign_user_id(base_id: Optional[str] = None) -> str:
    """
    Generates a cryptographically signed User ID: usr_<timestamp>_<nonce>.<checksum>
    If base_id is provided, strips any preexisting signature and signs it.
    """
    if not base_id:
        ts = int(time.time())
        nonce = secrets.token_hex(6)
        base_id = f"usr_{ts}_{nonce}"
    elif not base_id.startswith("usr_"):
        base_id = f"usr_{base_id}"

    # Strip any preexisting signature if passed
    if "." in base_id:
        base_id = base_id.split(".", 1)[0]

    secret = config.session_secret_key.encode("utf-8")
    sig = hmac.new(secret, base_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{base_id}.{sig}"

def verify_user_id(signed_user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validates the cryptographic HMAC checksum of the user ID.
    Returns (is_valid, base_id).
    """
    if not signed_user_id or not isinstance(signed_user_id, str):
        return False, None

    signed_user_id = signed_user_id.strip()
    if "." not in signed_user_id:
        return False, None

    parts = signed_user_id.split(".", 1)
    if len(parts) != 2:
        return False, None

    base_id, sig = parts
    if not base_id or not sig or len(sig) != 16:
        return False, None

    secret = config.session_secret_key.encode("utf-8")
    expected_sig = hmac.new(secret, base_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    if hmac.compare_digest(sig, expected_sig):
        return True, base_id

    return False, None
