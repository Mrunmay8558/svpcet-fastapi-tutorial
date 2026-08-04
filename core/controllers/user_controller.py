from core.cruds.user_crud import UserCRUD
from core import logger
from fastapi import HTTPException, status
from commons.auth import encrypt_password, signJWT

logging = logger(__name__)


class UserController:
    def __init__(self):
        self.user_crud = UserCRUD()

    async def register_user(self, request: dict):
        """
        Register a new user.

        Args:
            request (dict): The request body containing user sign-up details.

        Returns:
            dict: A success message indicating that the user has been created.
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
                user_role=user.user_role.value, id=str(user.id), expiry_duration=3600
            )
            # Build the response explicitly so the password hash is never
            # returned to the client.
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
            logging.error(f"Error in UserController.register_user: {error}")
            raise
