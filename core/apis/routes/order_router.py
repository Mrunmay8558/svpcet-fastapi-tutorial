"""
order_router.py — HTTP endpoints for order management.

This is the transport layer. Its responsibilities begin and end with HTTP:
declaring paths and methods, letting FastAPI validate the payload against a
request schema, decoding the bearer token, delegating to a controller, and
translating failures into status codes.

Layer contract:
    * No business rules and no database access live here. A route that grows
      past a handful of lines has almost certainly absorbed work belonging to
      :mod:`core.controllers.order_controller`.
    * Deliberate failures raised by the controller are re-raised unchanged so
      the intended status code survives.
    * Unexpected failures are logged in full and returned to the client as a
      generic ``500`` — internal detail (stack traces, driver messages, library
      versions) is never exposed to callers.

Authentication:
    Every endpoint here is protected. ``Depends(oauth2_scheme)`` pulls the token
    out of the ``Authorization: Bearer <token>`` header, :func:`decodeJWT`
    verifies its signature and expiry, and the resulting payload —
    ``{"id": ..., "user_role": ...}`` — is handed to the controller as
    ``authenticated_user_details``. That payload is the only source of the
    caller's identity and role; neither is ever read from the request body.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer

from commons.auth import decodeJWT
from core import logger
from core.apis.schemas.requests.order_request import (
    OrderCreateRequest,
    OrderUpdateRequest,
)
from core.controllers.order_controller import OrderController
from core.models.order_model import OrderStatus

logging = logger(__name__)

order_router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/user/login")


@order_router.post("/v1/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderCreateRequest, token: str = Depends(oauth2_scheme)
):
    """
    Create a new order for an authenticated user.

    Args:
        request: Validated order payload. FastAPI rejects malformed bodies with
            ``422`` before this function is entered.
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the created order.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``404 Not Found`` — the token is valid but its subject no longer
              exists.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling /v1/orders endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order creation")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        # `await` is required: create_order is an async function, so calling it
        # without awaiting hands back a coroutine object rather than the result.
        # FastAPI then fails to serialise it and the endpoint answers 500 while
        # the order is never written at all.
        result = await OrderController().create_order(
            request.model_dump(), authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/orders: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/orders: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.get("/v1/orders", status_code=status.HTTP_200_OK)
async def list_orders(
    order_status: Optional[OrderStatus] = Query(
        None, description="Filter by order status."
    ),
    user_id: Optional[str] = Query(
        None, description="Filter by owner. Administrators only."
    ),
    include_deleted: bool = Query(
        False, description="Include soft-deleted orders. Administrators only."
    ),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(20, ge=1, le=100, description="Orders per page."),
    token: str = Depends(oauth2_scheme),
):
    """
    List orders, newest first.

    A customer receives only their own orders. An administrator receives every
    user's, and may narrow the list with ``user_id`` or include soft-deleted
    records with ``include_deleted``.

    Args:
        order_status: Restrict to one lifecycle status.
        user_id: Owner filter, honoured for administrators only.
        include_deleted: Include soft-deleted orders, administrators only.
        page: 1-based page number.
        page_size: Orders per page, capped at 100.
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": [...], "pagination": {...}}``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        ``page_size`` is capped at 100 by ``le=100``. Without a ceiling, a
        request for ``page_size=1000000`` would ask MongoDB for the entire
        collection and load it into memory — a denial of service that takes one
        line in a URL bar.

        This route is declared before ``/v1/orders/{order_id}``, but the order
        does not matter here: FastAPI matches the literal path first regardless.
        It would matter if a *static* path could be read as a parameter — with
        ``/v1/orders/search`` declared after ``/v1/orders/{order_id}``, the
        word "search" would arrive as an order ID.
    """
    try:
        logging.info("Calling GET /v1/orders endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order listing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().list_orders(
            authenticated_user_details=authenticated_user_details,
            order_status=order_status,
            user_id=user_id,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/orders: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in GET /v1/orders: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.get("/v1/orders/{order_id}", status_code=status.HTTP_200_OK)
async def get_order_by_id(order_id: str, token: str = Depends(oauth2_scheme)):
    """
    Retrieve an order by its ID.

    Args:
        order_id: The unique identifier of the order to retrieve.
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": {...}}``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the order belongs to another user.
            * ``404 Not Found`` — no such order, or it has been soft-deleted.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info(f"Calling /v1/orders/{order_id} endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order retrieval")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().get_order_by_id(
            order_id, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/orders/{order_id}: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/orders/{order_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.put("/v1/orders/{order_id}", status_code=status.HTTP_200_OK)
async def update_order(
    order_id: str,
    request: OrderUpdateRequest,
    token: str = Depends(oauth2_scheme),
):
    """
    Update an existing order.

    Every field of the payload is optional; only what is sent is changed.

    Args:
        order_id: The unique identifier of the order to update.
        request: Validated update payload.
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the updated order.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the order belongs to another user.
            * ``404 Not Found`` — no such order, or it has been soft-deleted.
            * ``409 Conflict`` — the order is already completed or cancelled.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        ``exclude_unset=True`` is what makes this a partial update. Without it,
        ``model_dump()`` returns every field of the schema — the omitted ones as
        ``None`` — and the controller would dutifully overwrite the item name
        and quantity with nulls on a request that only meant to change the
        status.
    """
    try:
        logging.info(f"Calling PUT /v1/orders/{order_id} endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order update")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().update_order(
            order_id,
            request.model_dump(exclude_unset=True),
            authenticated_user_details,
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in PUT /v1/orders/{order_id}: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in PUT /v1/orders/{order_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.delete("/v1/orders/{order_id}", status_code=status.HTTP_200_OK)
async def delete_order(order_id: str, token: str = Depends(oauth2_scheme)):
    """
    Soft-delete an order.

    The document is flagged, not removed: it disappears from every read while
    remaining on disk and remaining restorable.

    Args:
        order_id: The unique identifier of the order to delete.
        token: JWT token obtained from the login endpoint.

    Returns:
        dict: ``{"message": str, "data": {...}}`` showing the flagged order.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the order belongs to another user.
            * ``404 Not Found`` — no such order, or it is already deleted.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        Answers ``200`` with a body rather than the ``204 No Content`` a delete
        often returns, because the response carries the resulting state —
        ``is_deleted`` and ``deleted_at`` — which makes it visible that the
        record was flagged rather than erased. ``204`` forbids a body entirely.
    """
    try:
        logging.info(f"Calling DELETE /v1/orders/{order_id} endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order deletion")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().delete_order(
            order_id, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in DELETE /v1/orders/{order_id}: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in DELETE /v1/orders/{order_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.post("/v1/orders/{order_id}/restore", status_code=status.HTTP_200_OK)
async def restore_order(order_id: str, token: str = Depends(oauth2_scheme)):
    """
    Restore a soft-deleted order — administrators only.

    Args:
        order_id: The unique identifier of the soft-deleted order.
        token: JWT token of an administrator.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the restored order.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the caller is not an administrator.
            * ``404 Not Found`` — no such order.
            * ``409 Conflict`` — the order is not deleted.
            * ``500 Internal Server Error`` — any unexpected failure.

    Note:
        ``POST`` rather than ``PUT``: this triggers an action on an existing
        resource rather than replacing its representation, and it is not
        idempotent in a useful sense — the second call answers ``409``.
    """
    try:
        logging.info(f"Calling POST /v1/orders/{order_id}/restore endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for order restore")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().restore_order(
            order_id, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in POST /v1/orders/{order_id}/restore: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in POST /v1/orders/{order_id}/restore: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@order_router.delete(
    "/v1/orders/{order_id}/permanent", status_code=status.HTTP_200_OK
)
async def hard_delete_order(order_id: str, token: str = Depends(oauth2_scheme)):
    """
    Permanently erase an order — administrators only.

    Args:
        order_id: The unique identifier of the order to erase.
        token: JWT token of an administrator.

    Returns:
        dict: ``{"message": str, "data": {"id": str}}``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — the caller is not an administrator.
            * ``404 Not Found`` — no such order.
            * ``500 Internal Server Error`` — any unexpected failure.

    Warning:
        Irreversible. The document leaves the collection and only a backup can
        bring it back.

        The path is deliberately explicit — ``/permanent`` rather than a
        ``?permanent=true`` flag on the ordinary delete. A destructive operation
        should not be one mistyped query parameter away from a recoverable one,
        and a separate path is far easier to restrict in a proxy or an audit
        rule.
    """
    try:
        logging.info(f"Calling DELETE /v1/orders/{order_id}/permanent endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for hard delete")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await OrderController().hard_delete_order(
            order_id, authenticated_user_details
        )
        return result

    except HTTPException as httperror:
        logging.error(f"Error in DELETE /v1/orders/{order_id}/permanent: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in DELETE /v1/orders/{order_id}/permanent: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
