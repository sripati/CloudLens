"""Encryption for cloud credentials saved from the Cloud Accounts screen (Fernet: AES-128-CBC + HMAC-SHA256).

The key is derived from JWT_SECRET. Changing JWT_SECRET makes saved credentials unreadable, so they
have to be entered again.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Dict

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class CredentialsUnreadable(Exception):
    """Saved credentials were encrypted with a different key."""


def _material() -> bytes:
    return get_settings().JWT_SECRET.encode("utf-8")


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(_material()).digest()))


def encrypt_secrets(values: Dict[str, str]) -> str:
    return _fernet().encrypt(json.dumps(values).encode("utf-8")).decode("ascii")


def decrypt_secrets(token: str) -> Dict[str, str]:
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode("ascii")))
    except InvalidToken as exc:
        raise CredentialsUnreadable("Saved credentials cannot be decrypted with the current key") from exc


def fingerprint(values: Dict[str, str]) -> str:
    """Keyed hash of a configuration: proves a config was tested without storing it in clear."""
    return hmac.new(_material(), json.dumps(values, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
