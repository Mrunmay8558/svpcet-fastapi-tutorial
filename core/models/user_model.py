"""
user_model.py — Persistence schema for the ``users`` collection.

Defines the shape of a user document as it is stored in MongoDB, along with the
enumerations and embedded sub-documents it depends on. ODMantic validates every
document against these definitions on write, so this module is the single source
of truth for what a stored user looks like.

Important distinction:
    These models describe **stored** data. The API request payloads live in
    ``core/apis/schemas/requests/`` and are intentionally separate — an incoming
    payload carries a plain-text password and no id, while a stored document
    carries a hashed password and an id. Keeping the two apart prevents
    credential material from leaking into API responses.

    The two definitions must be kept in agreement by hand. A field accepted by a
    request schema but absent from :class:`User` is silently discarded on save.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from odmantic import Field, Model
from pydantic import BaseModel


class UserRole(str, Enum):
    """
    Authorisation level granted to an account.

    The value is embedded in the JWT access token issued at login and is the
    basis for permission checks on protected endpoints.

    Attributes:
        SUPERADMIN: Full administrative access.
        CUSTOMER: Standard end-user access. Default for self-registration.
    """

    SUPERADMIN = "SUPERADMIN"
    CUSTOMER = "CUSTOMER"


class UserStatus(str, Enum):
    """
    Lifecycle state of an account.

    Deactivation is modelled as a status change rather than a delete, which
    preserves history and any records referencing the user.

    Attributes:
        ACTIVE: Account may authenticate normally.
        INACTIVE: Account is suspended and must be refused at login.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class UserOTP(BaseModel):
    """
    A single-use verification code and its expiry, embedded in :class:`User`.

    Reserved for flows that must prove control of a contact channel — email
    verification, mobile verification, or step-up confirmation of a sensitive
    action. It is ``None`` for accounts with no verification in progress.

    Attributes:
        current_otp: The six-digit code most recently issued to the user.
        otp_expires_at: ISO-8601 timestamp after which the code must be
            rejected. Stored as a string; parse with
            :meth:`datetime.datetime.fromisoformat` before comparing, and
            compare against a timezone-aware value.

    Security:
        A code with no enforced expiry is a permanent credential sitting in an
        inbox. Callers must check ``otp_expires_at`` on every verification and
        clear the field once the code has been consumed so it cannot be replayed.
    """

    current_otp: str = Field(min_length=6, max_length=6)
    otp_expires_at: str


class UserAddress(BaseModel):
    """
    A postal address embedded in :class:`User`.

    Stored inline rather than in a separate collection because addresses are
    only ever read together with their owner, which makes embedding the cheaper
    access pattern.

    Attributes:
        address_line_1: Street address, first line.
        address_line_2: Street address, second line (landmark, apartment).
        state: State or province.
        city: City or town.
        pincode: Postal code. Text, not an integer — leading zeros are
            significant and no arithmetic is ever performed on it.
    """

    address_line_1: str
    address_line_2: str
    state: str
    city: str
    pincode: str


class User(Model):
    """
    A registered user account as stored in the ``users`` collection.

    Inheriting from :class:`odmantic.Model` maps this class to MongoDB and
    supplies the ``id`` primary key, which is assigned by the database on first
    save.

    Attributes:
        first_name: Given name.
        last_name: Family name.
        mobile_number: Ten-digit contact number, stored as text so leading
            zeros survive.
        user_role: Authorisation level. Defaults to
            :attr:`UserRole.CUSTOMER`; elevation is never self-service.
        user_status: Lifecycle state. Defaults to :attr:`UserStatus.ACTIVE`.
        password: **Bcrypt hash** of the password — never the plain text.
            Produced by :func:`commons.auth.encrypt_password` and verified with
            :func:`commons.auth.verify_password`.
        otp: Pending verification code, or ``None`` when none is outstanding.
        address: Zero or more postal addresses.
        email: Email address. Functions as the login identifier and is expected
            to be unique; uniqueness is currently enforced in the controller.
        created_at: Timezone-aware UTC timestamp of account creation.
        updated_at: Timezone-aware UTC timestamp of the last modification.
            Callers that mutate a user are responsible for refreshing it.

    Security:
        ``password`` must never be serialised into an API response. Responses
        are built field by field in the controller rather than by dumping this
        model, so the hash cannot escape by accident.

    Note:
        Both timestamps use ``default_factory`` so the current time is evaluated
        per document. A plain default would freeze every account's timestamp at
        the moment the module was imported.

        UTC is used throughout. Localisation belongs in the presentation layer,
        never in stored data.

        ``model_config`` overrides the collection name ODMantic would otherwise
        derive from the class name, mapping this model to ``users`` rather than
        ``user``. Changing that value does not migrate existing documents —
        MongoDB simply begins writing to a different collection, and anything
        written under the previous name becomes invisible to queries.
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

    model_config = {"collection": "users"}
