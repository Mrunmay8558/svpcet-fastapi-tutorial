from fastapi import APIRouter, Depends, HTTPException, status
from core import logger
from core.apis.schemas.requests.user_request import UserSignInRequest
from core.controllers.user_controller import UserController

logging = logger(__name__)

user_router = APIRouter()


@user_router.post("/v1/users/signup", status_code=status.HTTP_201_CREATED)
async def user_signup(request: UserSignInRequest):
    """
    Endpoint for user sign-up.

    Args:
        request (UserSignInRequest): The request body containing user sign-up details.

    Returns:
        dict: A success message indicating that the user has been created.
    """
    try:
        logging.info("Calling /v1/users/signup endpoint")
        request = request.model_dump()
        result = await UserController().register_user(request)
        return result

    except HTTPException as httperror:
        # Re-raise so the intended status code (e.g. 400 for duplicate email)
        # reaches the client instead of returning an empty 201 response.
        logging.error(f"Error in /v1/users/signup: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/users/signup: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
