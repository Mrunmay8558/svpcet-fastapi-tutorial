"""
order_model.py — Persistence schema for the ``orders`` collection.

Defines the shape of an order document as stored in MongoDB. ODMantic validates
every document against this definition on write, so this module is the single
source of truth for what a stored order looks like.

Soft delete:
    An order is never removed from the collection by the ordinary delete
    endpoint. Instead ``is_deleted`` is set to ``True`` and ``deleted_at`` is
    stamped. Every read filters the flag out, so the record disappears from the
    API while remaining on disk and remaining restorable.

    Deleting an order that a completed payment, an invoice, or a monthly revenue
    figure refers to would leave those records pointing at nothing. A flag keeps
    the history intact and keeps the mistake recoverable.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from odmantic import Field, Model, ObjectId


class FoodType(str, Enum):
    """
    Type of food item.

    Inherits from :class:`str` as well as :class:`~enum.Enum`, so a member
    compares equal to its own text (``FoodType.VEG == "VEG"`` is ``True``) and
    serialises to JSON as a plain string.

    Attributes:
        VEG: Vegetarian food item.
        NON_VEG: Non-vegetarian food item.
    """

    VEG = "VEG"
    NON_VEG = "NON_VEG"


class OrderStatus(str, Enum):
    """
    Current state of an order.

    Attributes:
        IN_PROGRESS: Order has been placed and is being prepared. The state
            every new order starts in.
        COMPLETED: Order has been fulfilled and closed.
        CANCELLED: Order has been cancelled by the user or by staff.
    """

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Order(Model):
    """
    An order placed by a user, as stored in the ``orders`` collection.

    Inheriting from :class:`odmantic.Model` maps this class to MongoDB and
    supplies the ``id`` primary key, assigned by the database on first save.

    Attributes:
        created_by: ``ObjectId`` of the user who placed the order. Typed as an
            ``ObjectId`` rather than a string so it matches the ``_id`` of the
            referenced user document — a string would compare unequal to every
            stored id and quietly break ownership checks.
        food_item: Name of the food item ordered.
        food_type: Whether the item is vegetarian or non-vegetarian.
        quantity: Number of units ordered.
        status: Lifecycle state of the order.
        is_deleted: Soft-delete flag. ``True`` hides the order from every read
            path without removing the document.
        deleted_at: When the order was soft-deleted, or ``None`` if it has not
            been. Kept alongside the flag because "is it deleted" and "when was
            it deleted" answer different questions, and the second is what an
            audit needs.
        created_at: Timezone-aware UTC timestamp of creation.
        updated_at: Timezone-aware UTC timestamp of the last modification.

    Note:
        Both timestamps use ``default_factory`` so the current time is evaluated
        once per document. A plain default would freeze every order's timestamp
        at the moment this module was imported.

        UTC is used throughout. Converting to a local timezone belongs in the
        presentation layer, never in stored data.

        ``model_config`` pins the collection name to ``orders``, overriding the
        ``order`` that ODMantic would otherwise derive from the class name.
        Changing that value does not migrate existing documents — MongoDB simply
        starts writing elsewhere, and anything under the old name becomes
        invisible to queries.
    """

    created_by: ObjectId = Field(
        ..., description="Identifier of the user who placed the order."
    )
    food_item: str = Field(..., description="Name of the food item ordered.")
    food_type: FoodType = Field(
        ..., description="Type of the food item (VEG or NON_VEG)."
    )
    quantity: int = Field(..., description="Number of units ordered.")
    status: OrderStatus = Field(
        default=OrderStatus.IN_PROGRESS, description="Current status of the order."
    )
    is_deleted: bool = Field(
        default=False,
        description="Soft-delete flag. True hides the order from all reads.",
    )
    deleted_at: Optional[datetime] = Field(
        default=None, description="When the order was soft-deleted, if it was."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the order was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the order was last updated.",
    )

    model_config = {"collection": "orders"}
