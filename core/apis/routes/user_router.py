"""
user_router.py — HTTP endpoints for user management.

This is the transport layer. Its responsibilities begin and end with HTTP:
declaring paths and methods, letting FastAPI validate the payload against a
request schema, delegating to a controller, and translating failures into status
codes.

Layer contract:
    * No business rules and no database access live here. A route that grows
      past a handful of lines has almost certainly absorbed work belonging to
      :mod:`core.controllers.user_controller`.
    * Deliberate failures raised by the controller are re-raised unchanged so
      the intended status code survives.
    * Unexpected failures are logged in full and returned to the client as a
      generic ``500`` — internal detail (stack traces, driver messages, library
      versions) is never exposed to callers.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import OAuth2PasswordBearer

from core import logger
from core.apis.schemas.requests.user_request import (
    UserSignInRequest,
    UserLoginRequest,
    UserChangePasswordRequest,
    AdminUserUpdateRequest,
    UserStatusUpdateRequest,
)
from core.controllers.user_controller import UserController
from core.models.user_model import UserStatus
from commons.auth import decodeJWT

logging = logger(__name__)

user_router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/user/login")


@user_router.post("/v1/users/signup", status_code=status.HTTP_201_CREATED)
async def user_signup(request: UserSignInRequest):
    """
    Register a new user account and issue an access token.

    The password is hashed before storage and the newly created account is
    returned together with a JWT, so the caller is authenticated immediately and
    need not follow registration with a separate login request.

    Args:
        request: Validated sign-up payload. FastAPI rejects malformed bodies
            with ``422`` before this function is entered.

    Returns:
        dict: ``{"message": str, "data": {...}}`` where ``data`` holds the
        created user's public fields and an ``access_token``. The password hash
        is never included.

    Raises:
        HTTPException:
            * ``400 Bad Request`` — the email is already registered.
            * ``422 Unprocessable Entity`` — payload failed schema validation
              (raised by FastAPI before this function runs).
            * ``500 Internal Server Error`` — any unexpected failure. Details
              are written to the log, not returned to the client.

    Note:
        ``model_dump()`` converts the Pydantic object into a plain dict so the
        controller stays independent of the transport layer and remains callable
        from tests, scripts, and background jobs.
    """
    try:
        logging.info("Calling /v1/users/signup endpoint")
        request = request.model_dump()
        result = await UserController().register_user(request)
        return result

    except HTTPException as httperror:
        # Deliberate, meaningful failure from the controller — log it, then let
        # it through untouched so the intended status code reaches the client.
        # Swallowing it here would return an empty 201 for a failed request.
        logging.error(f"Error in /v1/users/signup: {httperror}")
        raise
    except Exception as error:
        # Unexpected failure: the log gets the full cause, the client gets a
        # generic message that reveals nothing about internals.
        logging.error(f"Error in /v1/users/signup: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.post("/v1/user/login", status_code=status.HTTP_200_OK)
async def user_login(request: UserLoginRequest):
    """
    Authenticate a user and issue an access token.

    Args:
        request: Validated login payload. FastAPI rejects malformed bodies with
            ``422`` before this function is entered.
    """
    try:
        logging.info("Calling /v1/user/login endpoint")
        request = request.model_dump()
        result = await UserController().login_user(request)
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/user/login: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/user/login: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.post("/v1/user/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: UserChangePasswordRequest, token: str = Depends(oauth2_scheme)
):
    """
    Change the password for an authenticated user.

    Args:
        request: Validated change password payload. FastAPI rejects malformed bodies with
            ``422`` before this function is entered.
    """
    try:
        logging.info("Calling /v1/user/change-password endpoint")
        request = request.model_dump()
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for password change")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        logging.info(f"Authenticated user details: {authenticated_user_details}")

        result = await UserController().change_password(
            request, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/user/change-password: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/user/change-password: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.get("/v1/user/me", status_code=status.HTTP_200_OK)
async def get_my_profile(token: str = Depends(oauth2_scheme)):
    """
    Return the profile of the authenticated user.

    Args:
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the caller's own fields.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``404 Not Found`` — the token is valid but its subject no longer
              exists.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        No ID is accepted. The endpoint answers for whoever the token says the
        caller is, which is what makes "me" impossible to point at anyone else.
    """
    try:
        logging.info("Calling /v1/user/me endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for profile retrieval")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await UserController().get_profile(authenticated_user_details)
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/user/me: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/user/me: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.get("/v1/users", status_code=status.HTTP_200_OK)
async def list_users(
    user_status: Optional[UserStatus] = Query(
        None, description="Filter by account status."
    ),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(20, ge=1, le=100, description="Users per page."),
    token: str = Depends(oauth2_scheme),
):
    """
    List every registered user — administrators only.

    Args:
        user_status: Restrict to ``ACTIVE`` or ``INACTIVE`` accounts.
        page: 1-based page number.
        page_size: Users per page, capped at 100.
        token: JWT token of an administrator.

    Returns:
        dict: ``{"message": str, "data": [...], "pagination": {...}}``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the caller is not an administrator.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        Authentication and authorisation are two separate steps and happen in
        that order. This function establishes *who* is calling by decoding the
        token; the controller then decides whether that caller is *allowed*, by
        reading ``user_role`` from the decoded payload.
    """
    try:
        logging.info("Calling GET /v1/users endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for user listing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await UserController().list_users(
            authenticated_user_details=authenticated_user_details,
            user_status=user_status,
            page=page,
            page_size=page_size,
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/users: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in GET /v1/users: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.get("/v1/users/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_by_id(user_id: str, token: str = Depends(oauth2_scheme)):
    """
    Retrieve one user by ID — administrators, or the account holder.

    Args:
        user_id: The unique identifier of the user to retrieve.
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": {...}}``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — a customer asking for someone else's record.
            * ``404 Not Found`` — no such user.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info(f"Calling GET /v1/users/{user_id} endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for user retrieval")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await UserController().get_user_by_id(
            user_id, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/users/{user_id}: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in GET /v1/users/{user_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.put("/v1/users/{user_id}", status_code=status.HTTP_200_OK)
async def update_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    token: str = Depends(oauth2_scheme),
):
    """
    Update another user's details — administrators only.

    Every field of the payload is optional; only what is sent is changed.

    Args:
        user_id: The unique identifier of the user to update.
        request: Validated update payload.
        token: JWT token of an administrator.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the updated user.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the caller is not an administrator.
            * ``404 Not Found`` — no such user.
            * ``400 Bad Request`` — the new email already belongs to another
              account.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        ``exclude_unset=True`` is what makes this a partial update. Without it,
        every field of the schema is sent to the controller — the omitted ones
        as ``None`` — and a request meaning to change a surname would blank out
        the email, the mobile number, and the role along with it.
    """
    try:
        logging.info(f"Calling PUT /v1/users/{user_id} endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for user update")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await UserController().update_user(
            user_id,
            request.model_dump(exclude_unset=True),
            authenticated_user_details,
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in PUT /v1/users/{user_id}: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in PUT /v1/users/{user_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@user_router.patch("/v1/users/{user_id}/status", status_code=status.HTTP_200_OK)
async def update_user_status(
    user_id: str,
    request: UserStatusUpdateRequest,
    token: str = Depends(oauth2_scheme),
):
    """
    Activate or deactivate a user account — administrators only.

    Args:
        user_id: The unique identifier of the user whose status changes.
        request: Validated status payload — ``{"user_status": "ACTIVE"}`` or
            ``{"user_status": "INACTIVE"}``.
        token: JWT token of an administrator.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the new status.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the caller is not an administrator.
            * ``404 Not Found`` — no such user.
            * ``400 Bad Request`` — an administrator changing their own status.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        ``PATCH`` rather than ``PUT``: this modifies one attribute of the user
        rather than replacing the whole representation. ``PUT`` on this path
        with only a status would, read strictly, mean "the user is now nothing
        but a status".

        This is how a user is retired. There is no ``DELETE /v1/users/{id}`` —
        removing the document would leave every order that references it
        pointing at an owner who no longer exists, and would erase the record of
        who placed them.
    """
    try:
        logging.info(f"Calling PATCH /v1/users/{user_id}/status endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for status update")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await UserController().update_user_status(
            user_id, request.model_dump(), authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in PATCH /v1/users/{user_id}/status: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in PATCH /v1/users/{user_id}/status: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
