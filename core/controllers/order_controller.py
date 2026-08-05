"""
order_controller.py — Business logic for the order domain.

This layer owns the application's rules: who may see an order, who may change
one, and what "delete" means. It sits between the transport layer
(:mod:`core.apis.routes.order_router`) and the data-access layer
(:mod:`core.cruds.order_crud`).

Layer contract:
    * Knows nothing about HTTP beyond raising :class:`fastapi.HTTPException` to
      signal an outcome. It never reads headers, sets cookies, or builds
      responses.
    * Issues no MongoDB queries directly; all persistence goes through
      :class:`~core.cruds.order_crud.OrderCRUD`.
    * Returns plain dictionaries, which keeps every method callable from tests,
      CLI scripts, and background jobs with no web server running.

Authorisation model:
    A customer may act on their own orders and no others. An administrator may
    act on anyone's. Both facts come from ``authenticated_user_details``, the
    decoded JWT payload the router hands in — ``id`` says who the caller is and
    ``user_role`` says what they are allowed to do.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from odmantic import ObjectId

from core import logger
from core.cruds.order_crud import OrderCRUD
from core.cruds.user_crud import UserCRUD
from core.models.order_model import OrderStatus
from core.models.user_model import UserRole

logging = logger(__name__)


class OrderController:
    """
    Use cases for the order domain.

    Attributes:
        user_crud: Data-access gateway for the ``users`` collection, used to
            confirm the token's subject still exists.
        order_crud: Data-access gateway for the ``orders`` collection.
    """

    def __init__(self) -> None:
        self.user_crud = UserCRUD()
        self.order_crud = OrderCRUD()

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
            The role comes from a signature-verified JWT, never from the request
            body or a query parameter — either of which the caller controls and
            could simply set to ``SUPERADMIN``.
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

    async def create_order(
        self, request: dict, authenticated_user_details: dict
    ) -> dict:
        """
        Create a new order for an authenticated user.

        Steps, in order:
            1. Confirm the token's subject is a real, existing user.
            2. Stamp the order with that user's ID as its owner.
            3. Persist the order and assemble a response.

        Args:
            request: Order creation values validated by
                :class:`~core.apis.schemas.requests.order_request.OrderCreateRequest`
                and converted to a dict.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token — ``{"id": ..., "user_role": ...}``.

        Returns:
            dict: ``{"message": str, "data": {...}}``. ``data`` carries the
            order's public fields.

        Raises:
            HTTPException: ``404 Not Found`` if the token is valid but its
                subject no longer exists.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                read or write fails. The router converts it to a ``500``.

        Security:
            ``created_by`` is taken from the verified token, never from the
            request body. :class:`OrderCreateRequest` does not accept an owner
            field at all, so there is no path by which a caller can place an
            order in someone else's name.
        """
        try:
            logging.info("Calling OrderController.create_order function")
            user = await self.user_crud.get_by_id(authenticated_user_details["id"])
            if not user:
                # A well-formed token whose subject is gone — the account was
                # deleted after the token was issued. The signature is still
                # valid, so only this lookup catches it.
                logging.warning(
                    f"User with ID {authenticated_user_details['id']} not found"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Authenticated user not found",
                )
            payload = {
                "created_by": ObjectId(authenticated_user_details["id"]),
                **request,
            }
            result = await self.order_crud.create(payload)
            return {
                "message": "Order created successfully",
                "data": {
                    "id": str(result.id),
                    "created_by": str(result.created_by),
                    "food_item": result.food_item,
                    "food_type": result.food_type.value,
                    "quantity": result.quantity,
                    "status": result.status.value,
                    "created_at": result.created_at.isoformat(),
                    "updated_at": result.updated_at.isoformat(),
                },
            }

        except Exception as error:
            # Logged for diagnosis, then re-raised unchanged. A bare `raise`
            # preserves an HTTPException raised above with its intended status
            # code — replacing it with a new 500 here would turn every
            # deliberate 404 and 403 in this class into "Something Went Wrong".
            logging.error(f"Error in OrderController.create_order: {error}")
            raise

    async def get_order_by_id(
        self, order_id: str, authenticated_user_details: dict
    ) -> dict:
        """
        Retrieve an order by its ID.

        Args:
            order_id: The unique identifier of the order to retrieve.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}``. ``data`` carries the
            order's public fields.

        Raises:
            HTTPException:
                * ``404 Not Found`` — no such order, or it has been
                  soft-deleted.
                * ``403 Forbidden`` — the order belongs to another user and the
                  caller is not an administrator.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                read fails. The router converts it to a ``500``.
        """
        try:
            logging.info(
                f"Calling OrderController.get_order_by_id function for ID: {order_id}"
            )
            if not ObjectId.is_valid(order_id):
                logging.warning(f"Malformed order ID received: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            order = await self.order_crud.get_by_id(order_id)
            if not order:
                logging.warning(f"Order with ID {order_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            # str() on both sides: created_by is an ObjectId and the token's id
            # is a string. Comparing them directly is always False, so the real
            # owner would be refused access to their own order.
            is_owner = str(order.created_by) == str(authenticated_user_details["id"])
            is_admin = authenticated_user_details["user_role"] == UserRole.SUPERADMIN.value

            if not is_owner and not is_admin:
                logging.warning(
                    f"User with ID {authenticated_user_details['id']} is not authorized "
                    f"to access order {order_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to access this order",
                )

            return {
                "message": "Order retrieved successfully",
                "data": {
                    "id": str(order.id),
                    "created_by": str(order.created_by),
                    "food_item": order.food_item,
                    "food_type": order.food_type.value,
                    "quantity": order.quantity,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in OrderController.get_order_by_id for ID {order_id}: {error}"
            )
            raise

    async def list_orders(
        self,
        authenticated_user_details: dict,
        order_status: Optional[OrderStatus] = None,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        List the orders visible to the caller, newest first.

        A customer sees only their own orders — the owner filter is forced to
        their own ID and cannot be overridden. An administrator sees everyone's,
        and may narrow the list to one user with ``user_id``.

        Args:
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.
            order_status: Restrict to one lifecycle status, or ``None`` for all.
            user_id: Administrator-only owner filter. Ignored for customers,
                whose list is always scoped to themselves.
            include_deleted: Administrator-only. Includes soft-deleted orders.
                Ignored for customers, so a deleted order stays invisible to the
                person who deleted it.
            page: 1-based page number.
            page_size: Number of orders per page.

        Returns:
            dict: ``{"message": str, "data": [...], "pagination": {...}}``.
            ``pagination`` carries ``page``, ``page_size``, ``total`` and
            ``total_pages`` so a client can render controls without guessing.

        Raises:
            HTTPException: ``404 Not Found`` if an administrator passes a
                malformed ``user_id``.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                read fails. The router converts it to a ``500``.

        Security:
            The owner filter for a customer comes from the token, not from the
            query string. Were ``user_id`` honoured for everyone, reading another
            customer's entire order history would be a matter of editing the URL
            — the single most common way a list endpoint leaks data.
        """
        try:
            logging.info("Calling OrderController.list_orders function")
            is_admin = authenticated_user_details["user_role"] == UserRole.SUPERADMIN.value

            if is_admin:
                # None means "every user's orders"; a value narrows it to one.
                created_by = user_id
                if created_by is not None and not ObjectId.is_valid(created_by):
                    logging.warning(f"Malformed user ID received: {created_by}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )
            else:
                created_by = authenticated_user_details["id"]
                include_deleted = False

            skip = (page - 1) * page_size

            orders = await self.order_crud.get_all(
                created_by=created_by,
                order_status=order_status,
                skip=skip,
                limit=page_size,
                include_deleted=include_deleted,
            )
            total = await self.order_crud.count(
                created_by=created_by,
                order_status=order_status,
                include_deleted=include_deleted,
            )

            return {
                "message": "Orders retrieved successfully",
                "data": [
                    {
                        "id": str(order.id),
                        "created_by": str(order.created_by),
                        "food_item": order.food_item,
                        "food_type": order.food_type.value,
                        "quantity": order.quantity,
                        "status": order.status.value,
                        "is_deleted": order.is_deleted,
                        "created_at": order.created_at.isoformat(),
                        "updated_at": order.updated_at.isoformat(),
                    }
                    for order in orders
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    # Ceiling division: how many pages of `page_size` are needed
                    # to hold `total` items.
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }

        except Exception as error:
            logging.error(f"Error in OrderController.list_orders: {error}")
            raise

    async def update_order(
        self, order_id: str, request: dict, authenticated_user_details: dict
    ) -> dict:
        """
        Update an existing order.

        Args:
            order_id: The unique identifier of the order to update.
            request: Update values validated by
                :class:`~core.apis.schemas.requests.order_request.OrderUpdateRequest`,
                already reduced to the fields the client actually sent.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}`` with the updated order.

        Raises:
            HTTPException:
                * ``404 Not Found`` — no such order, or it is soft-deleted.
                * ``403 Forbidden`` — not the owner and not an administrator.
                * ``409 Conflict`` — the order is ``COMPLETED`` or ``CANCELLED``
                  and the caller is not an administrator.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                write fails. The router converts it to a ``500``.

        Note:
            A finished order is closed to customer edits. Raising the quantity
            on a completed order would change what was delivered after the fact
            and desynchronise it from whatever was invoiced. Administrators are
            exempt, because correcting a mis-recorded order is exactly the kind
            of intervention the role exists for.

            ``updated_at`` is refreshed here rather than in the CRUD layer. It
            records a *business* modification, and the data layer cannot tell an
            edit apart from any other write — a soft delete also saves the
            document.
        """
        try:
            logging.info(
                f"Calling OrderController.update_order function for ID: {order_id}"
            )
            if not ObjectId.is_valid(order_id):
                logging.warning(f"Malformed order ID received: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            order = await self.order_crud.get_by_id(order_id)
            if not order:
                logging.warning(f"Order with ID {order_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            is_owner = str(order.created_by) == str(authenticated_user_details["id"])
            is_admin = authenticated_user_details["user_role"] == UserRole.SUPERADMIN.value

            if not is_owner and not is_admin:
                logging.warning(
                    f"User with ID {authenticated_user_details['id']} is not authorized "
                    f"to update order {order_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to update this order",
                )

            if order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED) and not is_admin:
                logging.warning(
                    f"Rejected update to order {order_id} in terminal state "
                    f"{order.status.value}"
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Order is already {order.status.value} and cannot be modified",
                )

            # Only the keys the client actually sent. The router passes
            # exclude_unset=True, so an omitted field is left as it is rather
            # than being overwritten with None.
            payload = {**request, "updated_at": datetime.now(timezone.utc)}
            result = await self.order_crud.update(order_id, payload)

            return {
                "message": "Order updated successfully",
                "data": {
                    "id": str(result.id),
                    "created_by": str(result.created_by),
                    "food_item": result.food_item,
                    "food_type": result.food_type.value,
                    "quantity": result.quantity,
                    "status": result.status.value,
                    "created_at": result.created_at.isoformat(),
                    "updated_at": result.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in OrderController.update_order for ID {order_id}: {error}"
            )
            raise

    async def delete_order(
        self, order_id: str, authenticated_user_details: dict
    ) -> dict:
        """
        Soft-delete an order — flag it as deleted, keep the document.

        Args:
            order_id: The unique identifier of the order to delete.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token.

        Returns:
            dict: ``{"message": str, "data": {...}}`` showing the flagged order.

        Raises:
            HTTPException:
                * ``404 Not Found`` — no such order, or it is already deleted.
                * ``403 Forbidden`` — not the owner and not an administrator.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                write fails. The router converts it to a ``500``.

        Note:
            Deleting an already-deleted order is a ``404``: the lookup excludes
            soft-deleted records, so a second call cannot find it. That keeps
            the operation honest — the caller is told the record is not there
            rather than being handed a success for a no-op.

            The document survives, so the order still counts towards yesterday's
            revenue figures and any invoice referencing it still resolves. An
            administrator can restore it with :meth:`restore_order` or erase it
            with :meth:`hard_delete_order`.
        """
        try:
            logging.info(
                f"Calling OrderController.delete_order function for ID: {order_id}"
            )
            if not ObjectId.is_valid(order_id):
                logging.warning(f"Malformed order ID received: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            order = await self.order_crud.get_by_id(order_id)
            if not order:
                logging.warning(f"Order with ID {order_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            is_owner = str(order.created_by) == str(authenticated_user_details["id"])
            is_admin = authenticated_user_details["user_role"] == UserRole.SUPERADMIN.value

            if not is_owner and not is_admin:
                logging.warning(
                    f"User with ID {authenticated_user_details['id']} is not authorized "
                    f"to delete order {order_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to delete this order",
                )

            # A soft delete is an ordinary field update. Nothing leaves the
            # collection; every read path simply filters on the flag.
            now = datetime.now(timezone.utc)
            payload = {"is_deleted": True, "deleted_at": now, "updated_at": now}
            result = await self.order_crud.update(order_id, payload)

            return {
                "message": "Order deleted successfully",
                "data": {
                    "id": str(result.id),
                    "is_deleted": result.is_deleted,
                    "deleted_at": result.deleted_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in OrderController.delete_order for ID {order_id}: {error}"
            )
            raise

    async def restore_order(
        self, order_id: str, authenticated_user_details: dict
    ) -> dict:
        """
        Restore a soft-deleted order, undoing a delete.

        Args:
            order_id: The unique identifier of the soft-deleted order.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token. Administrators only.

        Returns:
            dict: ``{"message": str, "data": {...}}`` with the restored order.

        Raises:
            HTTPException:
                * ``403 Forbidden`` — the caller is not an administrator.
                * ``404 Not Found`` — no such order.
                * ``409 Conflict`` — the order is not deleted, so there is
                  nothing to restore.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                write fails. The router converts it to a ``500``.

        Note:
            The order is fetched with ``include_deleted=True``; every other read
            path excludes deleted records, and this one exists precisely to
            reach them.

            This method is the whole case for soft delete in one place. The
            equivalent for a hard delete is restoring last night's backup and
            reconciling everything written since.
        """
        try:
            logging.info(
                f"Calling OrderController.restore_order function for ID: {order_id}"
            )
            self.check_admin(authenticated_user_details)

            if not ObjectId.is_valid(order_id):
                logging.warning(f"Malformed order ID received: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            order = await self.order_crud.get_by_id(order_id, include_deleted=True)
            if not order:
                logging.warning(f"Order with ID {order_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            if not order.is_deleted:
                logging.warning(f"Order with ID {order_id} is not deleted")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Order is not deleted",
                )

            payload = {
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
            result = await self.order_crud.update(order_id, payload)

            return {
                "message": "Order restored successfully",
                "data": {
                    "id": str(result.id),
                    "created_by": str(result.created_by),
                    "food_item": result.food_item,
                    "food_type": result.food_type.value,
                    "quantity": result.quantity,
                    "status": result.status.value,
                    "is_deleted": result.is_deleted,
                    "created_at": result.created_at.isoformat(),
                    "updated_at": result.updated_at.isoformat(),
                },
            }

        except Exception as error:
            logging.error(
                f"Error in OrderController.restore_order for ID {order_id}: {error}"
            )
            raise

    async def hard_delete_order(
        self, order_id: str, authenticated_user_details: dict
    ) -> dict:
        """
        Permanently remove an order document from MongoDB.

        Args:
            order_id: The unique identifier of the order to erase.
            authenticated_user_details: Details of the authenticated user
                obtained from the JWT token. Administrators only.

        Returns:
            dict: ``{"message": str, "data": {"id": str}}``. Only the ID comes
            back — there is no longer a document to describe.

        Raises:
            HTTPException:
                * ``403 Forbidden`` — the caller is not an administrator.
                * ``404 Not Found`` — no such order exists.
            pymongo.errors.PyMongoError: Propagated from the data layer if the
                delete fails. The router converts it to a ``500``.

        Warning:
            Irreversible, and restricted to administrators for that reason. The
            record is gone the moment this returns; anything referencing its ID
            now points at nothing.

            Soft-deleted orders are reachable here (``include_deleted=True``),
            since purging already-deleted records is the common case — a
            retention job erasing whatever was soft-deleted over a year ago.
        """
        try:
            logging.info(
                f"Calling OrderController.hard_delete_order function for ID: {order_id}"
            )
            self.check_admin(authenticated_user_details)

            if not ObjectId.is_valid(order_id):
                logging.warning(f"Malformed order ID received: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            order = await self.order_crud.get_by_id(order_id, include_deleted=True)
            if not order:
                logging.warning(f"Order with ID {order_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found",
                )

            await self.order_crud.hard_delete(order)
            logging.info(
                f"Order {order_id} permanently deleted by admin "
                f"{authenticated_user_details['id']}"
            )

            return {
                "message": "Order permanently deleted",
                "data": {"id": order_id},
            }

        except Exception as error:
            logging.error(
                f"Error in OrderController.hard_delete_order for ID {order_id}: {error}"
            )
            raise
