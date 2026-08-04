"""Authentication utilities for JWT and password management."""

import time
import jwt
import os
import secrets
import hashlib
from passlib.context import CryptContext
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


JWT_SECRET = os.environ.get("secret")
JWT_ALGORITHM = os.environ.get("algorithm", "HS256")


def signJWT(user_role: str, id: str, expiry_duration: int = 3600) -> str:
    """
    Create a signed JWT access token for the given user.

    The token payload contains:
        - user_role: role of the user (e.g., "USER", "ADMIN")
        - id: user's unique identifier (ObjectId as string)
        - expires: Unix timestamp when this token expires

    Args:
        user_role: Role string from UserRole enum
        id: User ID as string
        expiry_duration: Seconds until expiry (default 15 minutes)

    Returns:
        str: Signed JWT token string
    """
    payload = {
        "user_role": user_role,
        "id": id,
        "expires": time.time() + expiry_duration,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodeJWT(token: str) -> dict | None:
    """
    Decode and validate a JWT token.

    Returns the decoded payload if valid and not expired.
    Returns None if the token is invalid or expired.

    Args:
        token: JWT string to decode

    Returns:
        dict | None: Decoded payload or None
    """
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded if decoded.get("expires", 0) > time.time() else None
    except Exception:
        return None


def encrypt_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)
