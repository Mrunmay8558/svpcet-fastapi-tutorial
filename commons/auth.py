"""
auth.py — Password hashing and JWT access-token helpers.

Two independent concerns live here, both shared across the application:

    Password storage
        Passwords are stored as bcrypt hashes and never as plain text. Bcrypt is
        deliberately slow and salts each hash, so identical passwords produce
        different digests and brute-forcing a stolen database stays expensive.

    Stateless authentication
        A signed JSON Web Token carries the caller's identity and role. Because
        the signature is verified with a server-side secret, the payload can be
        trusted without a database lookup on every request.

Configuration:
    Both values are read from the environment at import time and must be present
    in ``.env`` (see ``.env.example``):

    ``secret``
        Key used to sign and verify tokens. Anyone holding it can mint valid
        tokens for any user, so it must never be committed to version control.
        Generate one with ``python -c "import secrets; print(secrets.token_hex(32))"``.
    ``algorithm``
        Signing algorithm. Defaults to ``HS256``.

Security:
    A JWT is signed, not encrypted — its payload is merely base64-encoded and is
    readable by anyone holding the token. Never place confidential data in a
    token payload.

    An issued token cannot be revoked before it expires. Expiry is therefore the
    only bound on the damage a leaked token can do; keep lifetimes short.
"""

import os
import time

import jwt
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

#: Passlib hashing context. ``deprecated="auto"`` marks hashes produced by any
#: superseded scheme as needing a rehash, which allows the hashing strategy to
#: be migrated later without invalidating existing passwords.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


JWT_SECRET = os.environ.get("secret")
JWT_ALGORITHM = os.environ.get("algorithm", "HS256")


def signJWT(user_role: str, id: str, expiry_duration: int = 3600) -> str:
    """
    Issue a signed access token for a user.

    Args:
        user_role: Role granted to the caller, taken from
            :class:`~core.models.user_model.UserRole` (for example
            ``UserRole.CUSTOMER.value``). Pass the enum's ``.value``, never a
            hand-typed string — a literal that does not match the enum will not
            be caught by anything and produces tokens carrying a role that no
            permission check recognises.
        id: The user's MongoDB ``ObjectId`` rendered as a string.
        expiry_duration: Token lifetime in seconds. Defaults to ``3600``
            (one hour).

    Returns:
        str: The encoded token, ``header.payload.signature``.

    Raises:
        jwt.exceptions.InvalidKeyError: If ``secret`` is missing from the
            environment, leaving :data:`JWT_SECRET` as ``None``.

    Note:
        Expiry is carried in a custom ``expires`` claim rather than the standard
        ``exp`` claim. PyJWT validates ``exp`` automatically but ignores
        ``expires``, so the deadline is enforced by hand in :func:`decodeJWT`.
        Any other consumer of these tokens must do the same.
    """
    payload = {
        "user_role": user_role,
        "id": id,
        "expires": time.time() + expiry_duration,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodeJWT(token: str) -> dict | None:
    """
    Verify a token's signature and expiry, returning its payload.

    Args:
        token: Encoded JWT string, without any ``Bearer`` prefix.

    Returns:
        dict | None: The decoded payload (``user_role``, ``id``, ``expires``)
        when the signature is valid and the token has not expired; ``None``
        otherwise.

    Note:
        Every failure mode — tampered signature, malformed string, wrong
        algorithm, expired token — collapses to ``None`` by design. Callers
        cannot distinguish them, which prevents error messages from telling an
        attacker which part of a forged token to fix next. The distinction is
        available in the exception itself if a caller ever needs to log it.
    """
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded if decoded.get("expires", 0) > time.time() else None
    except Exception:
        return None


def encrypt_password(password: str) -> str:
    """
    Hash a plain-text password for storage.

    Args:
        password: The plain-text password as supplied by the user.

    Returns:
        str: A bcrypt hash (``$2b$12$...``) safe to persist. The salt and cost
        factor are embedded in the string, so verification needs nothing else.

    Note:
        Bcrypt truncates input beyond 72 bytes. Enforce a maximum password
        length at the schema layer rather than allowing silent truncation, which
        would make two long passwords sharing a 72-byte prefix interchangeable.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check a candidate password against a stored hash.

    Args:
        plain_password: Password supplied by the caller during authentication.
        hashed_password: The bcrypt hash stored on the user document.

    Returns:
        bool: ``True`` if the password matches, ``False`` otherwise.

    Note:
        The comparison is constant-time, so response timing does not reveal how
        much of a guessed password was correct.

        Callers must not disclose *why* authentication failed. Reporting
        "no such user" separately from "wrong password" confirms which email
        addresses are registered and hands an attacker a list of valid accounts.
    """
    return pwd_context.verify(plain_password, hashed_password)
