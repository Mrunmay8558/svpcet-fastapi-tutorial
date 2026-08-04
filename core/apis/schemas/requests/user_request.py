"""
user_request.py — Inbound request payloads for the user endpoints.

Every field constraint declared here is enforced by FastAPI *before* the route
function runs. A payload that violates one never reaches the controller; the
client receives ``422 Unprocessable Entity`` describing the offending field.

These schemas are deliberately separate from :mod:`core.models.user_model`.
A request carries a plain-text password and no identifier; a stored document
carries a bcrypt hash and an id. Sharing one class between the two roles is how
password hashes end up in API responses.

Note:
    Constraints here are structural (presence, type, length). Rules that require
    reading the database — "is this email already taken?" — belong to the
    controller, not to a schema.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from core.models.user_model import UserAddress


class UserSignInRequest(BaseModel):
    """
    Payload for ``POST /v1/users/signup``.

    Attributes:
        first_name: Given name. Required.
        last_name: Family name. Required.
        mobile_number: Contact number. Required, exactly ten characters. Typed
            as text rather than an integer so leading zeros are preserved.
        password: Plain-text password, minimum eight characters. Hashed by the
            controller before it reaches the database and never stored or
            returned as given.
        email: Email address, used as the login identifier. Required.
        address: Optional list of postal addresses; omit or send ``null`` when
            the user supplies none.

    Example:
        >>> {
        ...     "first_name": "Test",
        ...     "last_name": "User",
        ...     "mobile_number": "9876543210",
        ...     "password": "SecurePass123",
        ...     "email": "testuser@example.com"
        ... }

    Note:
        ``user_role`` and ``user_status`` are intentionally absent. Accepting
        them here would let a client register itself as ``SUPERADMIN``; both are
        assigned server-side from the :class:`~core.models.user_model.User`
        defaults.
    """

    first_name: str = Field(..., description="The user's first name.")
    last_name: str = Field(..., description="The user's last name.")
    mobile_number: str = Field(
        ..., description="The user's mobile number.", min_length=10, max_length=10
    )
    password: str = Field(..., description="The user's password.", min_length=8)
    email: str = Field(..., description="The user's email address.")
    address: Optional[List[UserAddress]] = Field(
        None, description="The user's address information."
    )
