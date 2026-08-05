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

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from odmantic import ObjectId

from commons.auth import encrypt_password, signJWT, verify_password
from core import logger
from core.cruds.user_crud import UserCRUD
from core.models.user_model import UserRole, UserStatus

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

    async def login_user(self, request: dict):
        """
        Authenticate a user and issue an access token.

        Args:
            request: Login values validated by
                :class:`~core.apis.schemas.requests.user_request.UserLoginRequest`
                and converted to a dict.
        """
        try:
            logging.info("Calling UserController.login_user function")
            user = await self.user_crud.get_by_email(request.get("email"))
            if not user:
                logging.warning(f"User not found with email {request.get('email')}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invalid email or password",
                )
            if not user.user_status == "ACTIVE":
                logging.warning(f"User with email {request.get('email')} is inactive")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )
            plain_password = request.get("password")
            hashed_password = user.password
            if not verify_password(plain_password, hashed_password):
                logging.warning(f"Invalid password for user {request.get('email')}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )
            access_token = signJWT(
                user_role=user.user_role.value,
                id=str(user.id),
                expiry_duration=ACCESS_TOKEN_EXPIRY_SECONDS,
            )
            # Built explicitly rather than by dumping the stored document, so
            # the password hash cannot reach the client.
            return {
                "message": "Login successful",
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
            logging.error(f"Error in UserController.login_user: {error}")
            raise

    async def change_password(self, request: dict, authenticated_user_details: dict):
        """
        Change the password for an authenticated user.

        Args:
            request: Change password values validated by
                :class:`~core.apis.schemas.requests.user_request.UserChangePasswordRequest`
                and converted to a dict.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str}``. Nothing about the account is echoed
            back; the caller already knows who they are.

        Raises:
            HTTPException:
                * ``404 Not Found`` — the token is valid but its subject no
                  longer exists.
                * ``401 Unauthorized`` — the old password does not match.

        Security:
            The current password is required even though the caller already
            holds a valid token. A token left behind on a shared machine would
            otherwise be enough to lock the real owner out of their account.

            The user ID comes from the token, so a caller can only ever change
            their own password. Accepting it from the request body would make
            this endpoint a way to overwrite anyone's credentials.
        """
        try:
            logging.info("Calling UserController.change_password function")
            user = await self.user_crud.get_by_id(authenticated_user_details.get("id"))
            if not user:
                logging.warning(
                    f"User not found with id {authenticated_user_details.get('id')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            if not verify_password(request.get("old_password"), user.password):
                logging.warning(
                    f"Invalid old password for user {authenticated_user_details.get('id')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid old password",
                )
            new_hashed_password = encrypt_password(request.get("new_password"))
            payload = {
                "password": new_hashed_password,
                "updated_at": datetime.now(timezone.utc),
            }
            # The ID and the changed fields — UserCRUD.update writes them with
            # $set. Mutating the loaded user object instead would leave the
            # database untouched, since nothing would carry the change back.
            await self.user_crud.update(authenticated_user_details.get("id"), payload)
            return {"message": "Password changed successfully"}

        except Exception as error:
            logging.error(f"Error in UserController.change_password: {error}")
            raise

    async def get_profile(self, authenticated_user_details: dict) -> dict:
        """
        Return the profile of the authenticated user.

        Args:
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}`` with the caller's own
            public fields.

        Raises:
            HTTPException: ``404 Not Found`` if the token is valid but its
                subject no longer exists.

        Note:
            The token carries only ``id`` and ``user_role``, so a name or an
            email still requires this lookup. It is also the one place where a
            client learns its *current* role, which matters because the role
            inside a token is a snapshot from login and may be stale.
        """
        try:
            logging.info("Calling UserController.get_profile function")
            user = await self.user_crud.get_by_id(authenticated_user_details.get("id"))
            if not user:
                logging.warning(
                    f"User not found with id {authenticated_user_details.get('id')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            return {
                "message": "Profile retrieved successfully",
                "data": {
                    "id": str(user.id),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "mobile_number": user.mobile_number,
                    "user_role": user.user_role.value,
                    "user_status": user.user_status.value,
                    "address": [address.model_dump() for address in user.address]
                    if user.address
                    else [],
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(f"Error in UserController.get_profile: {error}")
            raise

    async def list_users(
        self,
        authenticated_user_details: dict,
        user_status: Optional[UserStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        List every registered user — administrators only.

        Args:
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.
            user_status: Restrict to ``ACTIVE`` or ``INACTIVE`` accounts, or
                ``None`` for both.
            page: 1-based page number.
            page_size: Number of users per page.

        Returns:
            dict: ``{"message": str, "data": [...], "pagination": {...}}``.

        Raises:
            HTTPException: ``403 Forbidden`` if the caller is not an
                administrator.

        Security:
            The role is read from ``authenticated_user_details["user_role"]``,
            which came out of a signature-verified JWT. It is never read from
            the request body or a query parameter, either of which the caller
            controls and could simply set to ``SUPERADMIN``.

            Password hashes are stripped by building each entry field by field.
            The CRUD layer returns whole :class:`~core.models.user_model.User`
            documents, hash included; returning that list directly would publish
            every hash in the database to any administrator's browser and to
            whatever logs the response.
        """
        try:
            logging.info("Calling UserController.list_users function")
            self.check_admin(authenticated_user_details)

            skip = (page - 1) * page_size
            users = await self.user_crud.get_all(
                user_status=user_status, skip=skip, limit=page_size
            )
            total = await self.user_crud.count(user_status=user_status)

            return {
                "message": "Users retrieved successfully",
                "data": [
                    {
                        "id": str(user.id),
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "mobile_number": user.mobile_number,
                        "user_role": user.user_role.value,
                        "user_status": user.user_status.value,
                        "created_at": user.created_at.isoformat(),
                    }
                    for user in users
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }

        except Exception as error:
            logging.error(f"Error in UserController.list_users: {error}")
            raise

    async def get_user_by_id(
        self, user_id: str, authenticated_user_details: dict
    ) -> dict:
        """
        Retrieve one user by ID — administrators, or the account holder.

        Args:
            user_id: The unique identifier of the user to retrieve.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}``.

        Raises:
            HTTPException:
                * ``404 Not Found`` — no such user.
                * ``403 Forbidden`` — a customer asking for someone else's
                  record.

        Note:
            Customers are allowed through for their own ID so the endpoint works
            for both audiences. Without that, a client would need to know its
            caller's role before choosing between this and ``/v1/user/me``.
        """
        try:
            logging.info(
                f"Calling UserController.get_user_by_id function for ID: {user_id}"
            )
            is_admin = (
                authenticated_user_details.get("user_role") == UserRole.SUPERADMIN.value
            )
            is_self = str(user_id) == str(authenticated_user_details.get("id"))

            if not is_admin and not is_self:
                logging.warning(
                    f"User {authenticated_user_details.get('id')} is not authorized to "
                    f"view user {user_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this user",
                )

            if not ObjectId.is_valid(user_id):
                logging.warning(f"Malformed user ID received: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user = await self.user_crud.get_by_id(user_id)
            if not user:
                logging.warning(f"User with ID {user_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            return {
                "message": "User retrieved successfully",
                "data": {
                    "id": str(user.id),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "mobile_number": user.mobile_number,
                    "user_role": user.user_role.value,
                    "user_status": user.user_status.value,
                    "address": [address.model_dump() for address in user.address]
                    if user.address
                    else [],
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in UserController.get_user_by_id for ID {user_id}: {error}"
            )
            raise

    async def update_user(
        self, user_id: str, request: dict, authenticated_user_details: dict
    ) -> dict:
        """
        Update another user's details — administrators only.

        Args:
            user_id: The unique identifier of the user to update.
            request: Update values validated by
                :class:`~core.apis.schemas.requests.user_request.AdminUserUpdateRequest`,
                already reduced to the fields the client actually sent.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}`` with the updated user.

        Raises:
            HTTPException:
                * ``403 Forbidden`` — the caller is not an administrator.
                * ``404 Not Found`` — no such user.
                * ``400 Bad Request`` — the new email already belongs to another
                  account.

        Security:
            ``user_role`` is accepted here and nowhere else. This is the only
            path by which an account can be promoted to ``SUPERADMIN``, and it
            is reachable only by an existing administrator — which is why
            :class:`~core.apis.schemas.requests.user_request.UserSignInRequest`
            omits the field entirely rather than merely ignoring it.

            ``password`` is not accepted, so this endpoint cannot be used to
            take over an account by overwriting its credentials.
        """
        try:
            logging.info(
                f"Calling UserController.update_user function for ID: {user_id}"
            )
            self.check_admin(authenticated_user_details)

            if not ObjectId.is_valid(user_id):
                logging.warning(f"Malformed user ID received: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user = await self.user_crud.get_by_id(user_id)
            if not user:
                logging.warning(f"User with ID {user_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            # Email is the login identifier, so it has to stay unique. Without
            # this check two accounts could share one address and login would
            # resolve to whichever the database returned first.
            new_email = request.get("email")
            if new_email and new_email != user.email:
                existing_user = await self.user_crud.get_by_email(new_email)
                if existing_user:
                    logging.warning(f"Email {new_email} is already registered")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User with this email already exists",
                    )

            payload = {**request, "updated_at": datetime.now(timezone.utc)}
            result = await self.user_crud.update(user_id, payload)

            return {
                "message": "User updated successfully",
                "data": {
                    "id": str(result.id),
                    "first_name": result.first_name,
                    "last_name": result.last_name,
                    "email": result.email,
                    "mobile_number": result.mobile_number,
                    "user_role": result.user_role.value,
                    "user_status": result.user_status.value,
                    "updated_at": result.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in UserController.update_user for ID {user_id}: {error}"
            )
            raise

    async def update_user_status(
        self, user_id: str, request: dict, authenticated_user_details: dict
    ) -> dict:
        """
        Activate or deactivate an account — administrators only.

        Args:
            user_id: The unique identifier of the user whose status changes.
            request: Values validated by
                :class:`~core.apis.schemas.requests.user_request.UserStatusUpdateRequest`
                and converted to a dict.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}`` with the new status.

        Raises:
            HTTPException:
                * ``403 Forbidden`` — the caller is not an administrator.
                * ``404 Not Found`` — no such user.
                * ``400 Bad Request`` — an administrator deactivating their own
                  account.

        Note:
            Deactivation is this application's version of deleting a user. The
            document stays, so every order that references it still resolves,
            and ``login_user`` refuses an account that is not ``ACTIVE``. The
            action is reversible by sending ``ACTIVE`` here.

            An administrator cannot deactivate themselves. With a single
            administrator that is the difference between a mis-click and an
            application nobody can administer again.

        Security:
            An existing access token keeps working until it expires, because a
            JWT is verified by signature alone and is never checked against the
            database. Deactivation therefore takes effect within one token
            lifetime, not instantly. Where that gap matters, the remedies are a
            shorter expiry, a token version compared on each request, or a
            denylist of revoked tokens.
        """
        try:
            logging.info(
                f"Calling UserController.update_user_status function for ID: {user_id}"
            )
            self.check_admin(authenticated_user_details)

            if str(user_id) == str(authenticated_user_details.get("id")):
                logging.warning(
                    f"Admin {authenticated_user_details.get('id')} attempted to change "
                    f"their own status"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot change your own account status",
                )

            if not ObjectId.is_valid(user_id):
                logging.warning(f"Malformed user ID received: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user = await self.user_crud.get_by_id(user_id)
            if not user:
                logging.warning(f"User with ID {user_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            new_status = UserStatus(request.get("user_status")).value
            payload = {
                "user_status": new_status,
                "updated_at": datetime.now(timezone.utc),
            }
            result = await self.user_crud.update(user_id, payload)

            logging.info(
                f"User {user_id} status changed to {new_status} by admin "
                f"{authenticated_user_details.get('id')}"
            )

            return {
                "message": f"User {new_status.lower()} successfully",
                "data": {
                    "id": str(result.id),
                    "email": result.email,
                    "user_status": result.user_status.value,
                    "updated_at": result.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in UserController.update_user_status for ID {user_id}: {error}"
            )
            raise

    def check_admin(self, authenticated_user_details: dict) -> None:
        """
        Verify the caller holds the ``SUPERADMIN`` role.

        Args:
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            None: Returns silently when the caller is an administrator.

        Raises:
            HTTPException: ``403 Forbidden`` otherwise.

        Note:
            ``401`` and ``403`` answer different questions. ``401`` means "I do
            not know who you are" — retrying with credentials may work. ``403``
            means "I know exactly who you are, and the answer is no" — retrying
            with the same credentials never will. The router has already
            established identity by the time this runs, so the only possible
            answer here is ``403``.
        """
        if authenticated_user_details.get("user_role") != UserRole.SUPERADMIN.value:
            logging.warning(
                f"User {authenticated_user_details.get('id')} with role "
                f"{authenticated_user_details.get('user_role')} attempted an "
                f"admin-only operation"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This operation requires administrator privileges",
            )
