"""Password hashing and session-token helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 310_000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 password hash.

    Passwords are never stored in plain text. PBKDF2 is available in Python's
    standard library, so the project does not depend on platform-specific crypto
    packages.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "$".join(
        [
            ALGORITHM,
            str(ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_session_token() -> str:
    return secrets.token_urlsafe(48)
