"""
order_request.py — Inbound request payloads for the order endpoints.

Every constraint declared here is enforced by FastAPI *before* the route
function runs. A payload that violates one never reaches the controller; the
client receives ``422 Unprocessable Entity`` naming the offending field.

These schemas are deliberately separate from :mod:`core.models.order_model`. A
request carries no id, no owner, and no timestamps — those are assigned
server-side. Accepting them from the client would let a caller create an order
in someone else's name.
"""

from typing import Optional

from pydantic import BaseModel, Field

from core.models.order_model import FoodType, OrderStatus


class OrderCreateRequest(BaseModel):
    """
    Payload for ``POST /v1/orders``.

    Attributes:
        food_item: Name of the food item ordered. Required.
        food_type: Type of the food item (VEG or NON_VEG). Required.
        quantity: Number of units ordered. Required, must be greater than zero.

    Example:
        >>> {"food_item": "Paneer Tikka", "food_type": "VEG", "quantity": 2}

    Note:
        ``food_type`` is typed as the :class:`~core.models.order_model.FoodType`
        enum rather than as ``str``. A plain ``str`` would accept ``"vegg"``,
        pass validation here, and only fail later when the value is written
        against the model — a ``500`` for what is really a client mistake. Typed
        as an enum, the same request is rejected with a ``422`` that lists the
        permitted values.

        ``created_by``, ``status``, and both timestamps are absent by design.
        The server assigns them: the owner from the access token, the status
        from the model default.
    """

    food_item: str = Field(..., description="Name of the food item ordered.")
    food_type: FoodType = Field(
        ..., description="Type of the food item (VEG or NON_VEG)."
    )
    quantity: int = Field(..., description="Number of units ordered.", gt=0)


class OrderUpdateRequest(BaseModel):
    """
    Payload for ``PUT /v1/orders/{order_id}``.

    Every field is optional, which makes this a partial update: send only what
    should change and the rest is left alone.

    Attributes:
        food_item: New item name, if it should change.
        food_type: New food type, if it should change.
        quantity: New quantity, if it should change. Must be greater than zero.
        status: New lifecycle status, if it should change.

    Example:
        >>> {"quantity": 5}
        >>> {"food_item": "Veg Biryani", "status": "COMPLETED"}

    Note:
        ``created_by`` is not accepted. Allowing it would let a caller reassign
        their order to another user, or claim someone else's — the ownership
        check protecting every other operation would be bypassed by an ordinary
        update.
    """

    food_item: Optional[str] = Field(
        None, description="Name of the food item ordered."
    )
    food_type: Optional[FoodType] = Field(
        None, description="Type of the food item (VEG or NON_VEG)."
    )
    quantity: Optional[int] = Field(
        None, description="Number of units ordered.", gt=0
    )
    status: Optional[OrderStatus] = Field(
        None, description="Lifecycle status of the order."
    )
