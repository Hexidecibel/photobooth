"""Simple password authentication for the admin panel."""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, expected = stored_hash.split(":", 1)
    actual = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(actual, expected)


def generate_token() -> str:
    """Generate a session token."""
    return secrets.token_urlsafe(32)
