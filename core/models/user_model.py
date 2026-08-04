from odmantic import Model, Field
from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone


class UserRole(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    CUSTOMER = "CUSTOMER"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class UserOTP(BaseModel):
    current_otp: str = Field(min_length=6, max_length=6)
    otp_expires_at: str


class UserAddress(BaseModel):
    address_line_1: str
    address_line_2: str
    state: str
    city: str
    pincode: str


class User(Model):
    """
    User Authentication Model

    Args:
        Model (_type_): _description_
    """

    first_name: str
    last_name: str
    mobile_number: str
    user_role: UserRole = UserRole.CUSTOMER
    user_status: UserStatus = UserStatus.ACTIVE
    password: str
    otp: Optional[UserOTP] = None
    address: Optional[list[UserAddress]] = None
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
