from odmantic import AIOEngine
from core.database.database import get_engine
from core.models.user_model import User
from core import logger

logging = logger(__name__)


class UserCRUD:
    """
    CRUD operations for the User model.
    """

    def __init__(self):
        self.engine: AIOEngine = get_engine()

    async def create_user(self, user: dict) -> User:
        """
        Create a new user in the database.

        Args:
            user (User): The user object to be created.

        Returns:
            User: The created user object.
        """
        try:
            logging.info("Creating a new user in the database")
            # save() returns the persisted document, which now carries the
            # generated MongoDB id. Return that instead of the input dict.
            return await self.engine.save(User(**user))
        except Exception as error:
            logging.error(f"Error creating user: {error}")
            raise

    async def get_by_email(self, email: str):
        """
        Retrieve a user by their email address.

        Args:
            email (str): The email address of the user to retrieve.

        Returns:
            User: The user object if found, else None.
        """
        try:
            logging.info("Executing UserCRUD.get_by_email function")
            user = await self.engine.find_one(User, User.email == email)
            return user
        except Exception as error:
            logging.error(f"Error in UserCRUD.get_by_email: {error}")
            raise
