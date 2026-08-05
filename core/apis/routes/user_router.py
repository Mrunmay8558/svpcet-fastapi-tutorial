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

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from core import logger
from core.apis.schemas.requests.user_request import (
    UserSignInRequest,
    UserLoginRequest,
    UserChangePasswordRequest,
)
from core.controllers.user_controller import UserController
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
