"""Password hashing helpers for Volco/Vella auth.

Uses passlib's bcrypt handler. bcrypt has a hard 72-byte input limit;
passlib handles truncation/validation for us, so just use these two
functions everywhere instead of touching raw passwords.
"""

from __future__ import annotations

from passlib.context import CryptContext

# bcrypt_sha256 pre-hashes with SHA-256 before bcrypt, which removes the
# 72-byte truncation gotcha entirely. Falls back to verifying legacy
# plain "bcrypt" hashes too, so a mixed-scheme transition period is safe.
pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash."""
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Hash is malformed / not a recognized scheme (e.g. still
        # plaintext because migration hasn't run yet on this row).
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True if the stored hash uses an outdated scheme and should be upgraded."""
    return pwd_context.needs_update(hashed_password)