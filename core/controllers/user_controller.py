"""
user_controller.py — Business logic for user management.

This layer owns the application's rules: what is permitted, in what order steps
must occur, and what the caller is allowed to see. It sits between the transport
layer (:mod:`core.apis.routes.user_router`) and the data-access layer
(:mod:`core.cruds.user_crud`).

Layer contract:
    * Knows nothing about HTTP beyond raising :class:`fastapi.HTTPException` to
      signal an outcome. It never reads headers, sets cookies, or builds
      responses.
    * Issues no MongoDB queries directly; all persistence goes through
      :class:`~core.cruds.user_crud.UserCRUD`.
    * Returns plain dictionaries, which keeps every method callable from tests,
      CLI scripts, and background jobs with no web server running.
"""

from fastapi import HTTPException, status

from commons.auth import encrypt_password, signJWT
from core import logger
from core.cruds.user_crud import UserCRUD

logging = logger(__name__)

#: Lifetime of an issued access token, in seconds (one hour). Short-lived by
#: design: a leaked token cannot be revoked, so expiry is what bounds the damage.
ACCESS_TOKEN_EXPIRY_SECONDS = 3600


class UserController:
    """
    Use cases for the user domain.

    Attributes:
        user_crud: Data-access gateway for the ``users`` collection.
    """

    def __init__(self) -> None:
        self.user_crud = UserCRUD()

    async def register_user(self, request: dict) -> dict:
        """
        Register a new account and issue an access token.

        Steps, in order:
            1. Reject the request if the email is already registered.
            2. Replace the plain-text password with a bcrypt hash.
            3. Persist the account.
            4. Issue a JWT scoped to the new user's id and role.
            5. Assemble a response containing only publicly safe fields.

        Args:
            request: Sign-up values validated by
                :class:`~core.apis.schemas.requests.user_request.UserSignInRequest`
                and converted to a dict. Mutated in place: ``password`` is
                overwritten with its hash before the value is persisted.

        Returns:
            dict: ``{"message": str, "data": {...}}``. ``data`` carries the
            account's public fields plus ``access_token``.

        Raises:
            HTTPException: ``400 Bad Request`` if the email is already
                registered.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                read or write fails. The router converts it to a ``500``.

        Security:
            The plain-text password is hashed before it reaches the database and
            is never logged. The response is assembled field by field rather
            than by returning the stored document, so the hash cannot leak into
            the API surface.
        """
        try:
            logging.info("Calling UserController.register_user function")
            email = request.get("email")
            user = await self.user_crud.get_by_email(email)
            if user:
                logging.warning(f"User with email {email} already exists")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists",
                )
            password = request.get("password")
            hashed_password = encrypt_password(password)
            request["password"] = hashed_password
            user = await self.user_crud.create_user(request)
            access_token = signJWT(
                user_role=user.user_role.value,
                id=str(user.id),
                expiry_duration=ACCESS_TOKEN_EXPIRY_SECONDS,
            )
            # Built explicitly rather than by dumping the stored document, so
            # the password hash cannot reach the client.
            return {
                "message": "User created successfully",
                "data": {
                    "id": str(user.id),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "mobile_number": user.mobile_number,
                    "user_role": user.user_role.value,
                    "user_status": user.user_status.value,
                    "access_token": access_token,
                },
            }

        except Exception as error:
            # Logged for diagnosis, then re-raised so the failure still counts.
            # Swallowing it here would return None and report success.
            logging.error(f"Error in UserController.register_user: {error}")
            raise
