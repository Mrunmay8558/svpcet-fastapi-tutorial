from pydantic import BaseModel, Field
from typing import Optional, List
from core.models.user_model import UserAddress


class UserSignInRequest(BaseModel):
    """
    Request model for user sign-in.

    Attributes:
        email (str): The user's email address.
        password (str): The user's password.
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
