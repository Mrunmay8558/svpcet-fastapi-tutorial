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

from core.models.user_model import UserAddress, UserRole, UserStatus


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


class UserLoginRequest(BaseModel):
    """
    Payload for ``POST /v1/users/login``.

    Attributes:
        email: Email address, used as the login identifier. Required.
        password: Plain-text password, minimum eight characters. Hashed by the
            controller before it reaches the database and never stored or
            returned as given.
    """

    email: str = Field(..., description="The user's email address.")
    password: str = Field(..., description="The user's password.", min_length=8)


class UserChangePasswordRequest(BaseModel):
    """
    Payload for ``POST /v1/users/change-password``.

    Attributes:
        old_password: Plain-text current password, minimum eight characters.
            Hashed by the controller before it reaches the database and never
            stored or returned as given.
        new_password: Plain-text new password, minimum eight characters. Hashed
            by the controller before it reaches the database and never stored or
            returned as given.
    """

    old_password: str = Field(
        ..., description="The user's current password.", min_length=8
    )
    new_password: str = Field(..., description="The user's new password.", min_length=8)


class AdminUserUpdateRequest(BaseModel):
    """
    Payload for ``PUT /v1/users/{user_id}`` — administrator only.

    Every field is optional, making this a partial update: send only what should
    change. Omitting a field leaves the stored value untouched.

    Attributes:
        first_name: New given name, if it should change.
        last_name: New family name, if it should change.
        mobile_number: New contact number, exactly ten characters.
        email: New email address. Also the login identifier, so changing it
            changes how the account signs in.
        address: Replacement list of postal addresses. Replaces the stored list
            wholesale rather than appending to it.
        user_role: New authorisation level. Restricted to administrators for
            obvious reasons — see the note below.
        user_status: New lifecycle state. ``INACTIVE`` blocks the account at
            login.

    Example:
        >>> {"first_name": "Updated", "user_status": "INACTIVE"}

    Note:
        ``password`` is deliberately absent. An administrator setting another
        user's password directly would hand them a credential the user never
        chose and leave no trace of who typed it. Password changes belong to
        ``POST /v1/user/change-password``, which requires the current password
        and can only be performed by the account holder.

        This schema is *not* what protects ``user_role`` from self-elevation —
        the controller's role check is. The separation matters:
        :class:`UserSignInRequest` omits the field entirely, so a
        self-registering caller cannot send it at all, while this schema accepts
        it and relies on the controller having established that the caller is an
        administrator.
    """

    first_name: Optional[str] = Field(None, description="The user's first name.")
    last_name: Optional[str] = Field(None, description="The user's last name.")
    mobile_number: Optional[str] = Field(
        None, description="The user's mobile number.", min_length=10, max_length=10
    )
    email: Optional[str] = Field(None, description="The user's email address.")
    address: Optional[List[UserAddress]] = Field(
        None, description="The user's address information."
    )
    user_role: Optional[UserRole] = Field(
        None, description="Authorisation level (SUPERADMIN or CUSTOMER)."
    )
    user_status: Optional[UserStatus] = Field(
        None, description="Account lifecycle state (ACTIVE or INACTIVE)."
    )


class UserStatusUpdateRequest(BaseModel):
    """
    Payload for ``PATCH /v1/users/{user_id}/status`` — administrator only.

    A dedicated single-field schema for activating and deactivating an account,
    kept separate from :class:`AdminUserUpdateRequest`.

    Attributes:
        user_status: ``ACTIVE`` to restore access, ``INACTIVE`` to suspend it.

    Example:
        >>> {"user_status": "INACTIVE"}

    Note:
        Suspension is its own operation for two reasons. It is the one user
        change most likely to be audited or alerted on, and a narrow endpoint
        makes that trivial to hook. And a request that can *only* alter status
        cannot rename an account by accident, which a partial update with one
        mistyped key can.

        Typed as the :class:`~core.models.user_model.UserStatus` enum, so
        ``{"user_status": "DISABLED"}`` is rejected with a ``422`` listing the
        two values that exist rather than being written as nonsense.
    """

    user_status: UserStatus = Field(
        ..., description="Account lifecycle state (ACTIVE or INACTIVE)."
    )
