"""
order_crud.py — Data-access layer for the :class:`Order` document.

This module is the ONLY place in the codebase that issues MongoDB queries for
orders. Everything above it (controllers, routers) works through the
:class:`OrderCRUD` interface, which keeps persistence concerns isolated and
makes the storage engine swappable without touching business logic.

Layer contract:
    * Methods here persist and retrieve data. They never enforce business rules.
    * Methods here never raise :class:`fastapi.HTTPException` — mapping a
      failure to an HTTP status code is the controller's responsibility.
    * "Not found" is expressed by returning ``None``, not by raising.
    * Ownership is not checked here. A caller asking for an order gets it; the
      controller decides whether that caller was entitled to it.

Soft delete:
    Reads exclude soft-deleted orders by default. ``include_deleted=True`` opts
    back in, which is what the restore and administrative paths need. Making
    exclusion the default is what keeps a deleted order from reappearing through
    an endpoint whose author forgot the flag existed.
"""

from typing import List, Optional

from odmantic import AIOEngine, ObjectId

from core import logger
from core.database.database import get_engine
from core.models.order_model import Order, OrderStatus

logging = logger(__name__)


class OrderCRUD:
    """
    Create/read/update/delete operations for the ``orders`` collection.

    The instance borrows the process-wide ODMantic engine created by
    :func:`core.database.database.get_engine`. No connection is opened here —
    the engine owns a shared pool that is reused across requests.

    Attributes:
        engine: Shared ODMantic engine used for all queries in this class.
    """

    def __init__(self) -> None:
        self.engine: AIOEngine = get_engine()

    async def create(self, order_data: dict) -> Order:
        """
        Create a new order in the database.

        Args:
            order_data: A dictionary containing the order details. Must satisfy
                the :class:`Order` schema, including a ``created_by`` of type
                ``ObjectId``.

        Returns:
            Order: The created order, including the ``id`` assigned by MongoDB
            during the write.

        Raises:
            pydantic.ValidationError: If ``order_data`` does not satisfy the
                :class:`Order` schema.
            pymongo.errors.PyMongoError: If the write fails at the database
                level.

        Note:
            The return value of ``engine.save()`` is returned deliberately. The
            input dictionary has no ``id`` — that value is assigned during the
            write and exists only on the returned document.
        """
        try:
            logging.info("Executing OrderCRUD.create function")
            order = Order(**order_data)
            return await self.engine.save(order)
        except Exception as error:
            logging.error(f"Error in OrderCRUD.create function: {error}")
            raise

    async def get_by_id(
        self, order_id: str, include_deleted: bool = False
    ) -> Optional[Order]:
        """
        Fetch a single order by ID.

        Args:
            order_id: The ID of the order to retrieve, as a string.
            include_deleted: When ``True``, soft-deleted orders are returned as
                well. Needed by the restore and hard-delete paths, which have to
                be able to see a record precisely because it is deleted.

        Returns:
            Order | None: The matching order, or ``None`` when none matches.

        Raises:
            pymongo.errors.PyMongoError: If the query fails at the database
                level.

        Note:
            The string is converted to an ``ObjectId`` before the query is
            built. ``Order.id == "68a1b2c3..."`` produces the valid-looking
            query ``{"_id": {"$eq": "68a1b2c3..."}}``, which matches nothing,
            because ids are stored as ``ObjectId`` and never as text. Nothing
            raises — the method just returns ``None``, and the endpoint answers
            ``404`` for an order that exists.
        """
        try:
            logging.info(f"Executing OrderCRUD.get_by_id function for ID: {order_id}")

            queries = [Order.id == ObjectId(order_id)]
            if not include_deleted:
                # "$ne: True" rather than "== False" so that orders written
                # before the is_deleted field existed — which have no such key
                # at all — are still matched. {"is_deleted": False} does not
                # match a document where the field is missing.
                queries.append(Order.is_deleted != True)  # noqa: E712

            order = await self.engine.find_one(Order, *queries)
            return order
        except Exception as error:
            logging.error(f"Error in OrderCRUD.get_by_id for ID {order_id}: {error}")
            raise

    async def get_all(
        self,
        created_by: Optional[str] = None,
        order_status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> List[Order]:
        """
        Fetch a page of orders, newest first.

        Args:
            created_by: Restrict to orders owned by this user ID. ``None``
                returns every user's orders — only administrators reach that.
            order_status: Restrict to one lifecycle status. ``None`` returns all
                statuses.
            skip: Number of matching documents to step over before collecting
                results.
            limit: Maximum number of documents to return.
            include_deleted: When ``True``, soft-deleted orders are included.

        Returns:
            list[Order]: The matching page, sorted by ``created_at`` descending.
            Empty when nothing matches — an empty page is not an error.

        Raises:
            pymongo.errors.PyMongoError: If the query fails at the database
                level.

        Note:
            ``skip``/``limit`` paging is applied by MongoDB, not in Python.
            Fetching everything and slicing the list afterwards would pull the
            whole collection into the process — fine with fifty orders, fatal
            with fifty thousand.
        """
        try:
            logging.info(
                f"Executing OrderCRUD.get_all function (created_by={created_by}, "
                f"status={order_status}, skip={skip}, limit={limit})"
            )

            queries = self.build_queries(created_by, order_status, include_deleted)

            orders = await self.engine.find(
                Order,
                *queries,
                sort=Order.created_at.desc(),
                skip=skip,
                limit=limit,
            )
            return orders
        except Exception as error:
            logging.error(f"Error in OrderCRUD.get_all function: {error}")
            raise

    async def count(
        self,
        created_by: Optional[str] = None,
        order_status: Optional[OrderStatus] = None,
        include_deleted: bool = False,
    ) -> int:
        """
        Count the orders matching the same filters :meth:`get_all` accepts.

        Args:
            created_by: Restrict to orders owned by this user ID.
            order_status: Restrict to one lifecycle status.
            include_deleted: When ``True``, soft-deleted orders are counted.

        Returns:
            int: Number of matching documents.

        Raises:
            pymongo.errors.PyMongoError: If the query fails at the database
                level.

        Note:
            Counted by the database rather than by measuring the returned page.
            The page is capped by ``limit`` and would report at most that many;
            the total is what tells a client how many pages exist.
        """
        try:
            logging.info("Executing OrderCRUD.count function")
            queries = self.build_queries(created_by, order_status, include_deleted)
            return await self.engine.count(Order, *queries)
        except Exception as error:
            logging.error(f"Error in OrderCRUD.count function: {error}")
            raise

    def build_queries(
        self,
        created_by: Optional[str],
        order_status: Optional[OrderStatus],
        include_deleted: bool,
    ) -> list:
        """
        Build the list of filter conditions shared by :meth:`get_all` and
        :meth:`count`.

        Args:
            created_by: Owner filter, or ``None`` for no owner filter.
            order_status: Status filter, or ``None`` for no status filter.
            include_deleted: When ``False``, adds the soft-delete exclusion.

        Returns:
            list: Query conditions. ODMantic ANDs them together when they are
            passed as positional arguments to ``find`` or ``count``.

        Note:
            Shared by both methods so the list and its total can never disagree.
            Built separately, a page could show three orders while the total
            claimed nine.
        """
        queries = []

        if created_by is not None:
            queries.append(Order.created_by == ObjectId(created_by))
        if order_status is not None:
            queries.append(Order.status == order_status)
        if not include_deleted:
            queries.append(Order.is_deleted != True)  # noqa: E712

        return queries

    async def update(self, order_id: str, update_data: dict) -> Optional[Order]:
        """
        Update an order document by its ID.

        Args:
            order_id: The ID of the order to update, as a string.
            update_data: A dictionary containing the fields to update. Only the
                keys present are written; everything else is left as it is.

        Returns:
            The updated :class:`Order`, or ``None`` if no document matches.

        Raises:
            pymongo.errors.PyMongoError: If the update fails at the database
                level.

        Note:
            This is also how a **soft delete** is performed — the controller
            calls it with ``{"is_deleted": True, "deleted_at": ...}``. A soft
            delete is not a special kind of operation; it is an ordinary field
            update that every read path happens to filter on.

            ``get_collection`` is a plain function, not a coroutine. It returns
            a collection handle without touching the database, so it must not be
            awaited.
        """
        try:
            logging.info(
                f"Executing OrderCRUD.update function for ID: {order_id} "
                f"with data: {update_data}"
            )
            order_collection = self.engine.get_collection(Order)
            docs = await order_collection.find_one_and_update(
                {"_id": ObjectId(order_id)},
                {"$set": update_data},
                return_document=True,
            )
            if docs is None:
                return None
            return Order.model_validate_doc(docs)
        except Exception as error:
            logging.error(f"Error in OrderCRUD.update for ID {order_id}: {error}")
            raise

    async def hard_delete(self, order: Order) -> None:
        """
        Permanently remove an order document from MongoDB.

        Args:
            order: The order to delete.

        Returns:
            None

        Raises:
            pymongo.errors.PyMongoError: If the delete fails at the database
                level.

        Warning:
            Irreversible. The document is gone from the collection the moment
            this returns, and the only route back is restoring a backup.
            Anything still referencing this order's ID — an invoice, a delivery
            record, a monthly total — now points at nothing.

            Kept for the cases that genuinely require erasure: a data-deletion
            request under GDPR or similar, or purging test data. Both are
            administrator work, which is why the endpoint that calls this checks
            for the ``SUPERADMIN`` role first.
        """
        try:
            logging.info(f"Executing OrderCRUD.hard_delete function for ID: {order.id}")
            await self.engine.delete(order)
        except Exception as error:
            logging.error(f"Error in OrderCRUD.hard_delete for ID {order.id}: {error}")
            raise
