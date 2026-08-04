"""
database.py — MongoDB connection management (Motor + ODMantic).

Owns exactly one connection to MongoDB for the lifetime of the process and
shares it with every caller. Establishing a connection is expensive and MongoDB
caps concurrent connections, so opening one per request degrades under load and
eventually exhausts the server's connection limit. A single client holding an
internal pool is the standard arrangement.

Two accessors are exposed:
    * :func:`get_engine` — the ODMantic engine, used by the CRUD layer for
      model-validated queries. Correct for virtually all application code.
    * :func:`MongoDatabase` — the raw Motor database, for operations ODMantic
      cannot express (aggregation pipelines, administrative commands). No schema
      validation applies to anything issued through it.

Configuration:
    ``MONGODB_URL``
        Connection string. Defaults to ``mongodb://localhost:27017``.
    ``DATABASE_NAME``
        Database to read and write. Defaults to ``fastapi_tutorial``.

Warning:
    Both values are read at **import time**. ``.env`` must therefore already be
    loaded before this module is imported, which is why :func:`dotenv.load_dotenv`
    is called in :mod:`core` — the package initialiser Python executes ahead of
    any ``core.*`` submodule.

    Get that ordering wrong and the failure is silent: :func:`os.getenv` returns
    nothing, the defaults below take effect, and the application connects to a
    different database than the one configured. No exception is raised. The only
    evidence is the database name in the startup log line.
"""

import logging
import os
from typing import Optional

from motor import core, motor_asyncio
from odmantic import AIOEngine
from pymongo.driver_info import DriverInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#: Identifies this application in MongoDB's server logs and profiler output,
#: which makes traffic attributable when several services share a cluster.
DRIVER_INFO = DriverInfo(name="fastapi-tutorial", version="0.1.0")

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fastapi_tutorial")


class _MongoClientSingleton:
    """
    Process-wide holder for the Motor client and the ODMantic engine.

    Implements the singleton pattern via ``__new__``: the first instantiation
    builds the client and engine, every later one returns the same instance. As
    a result ``_MongoClientSingleton()`` is cheap to call from anywhere and
    always yields the same connection pool.

    Attributes:
        mongo_client: Async MongoDB client owning the connection pool.
        engine: ODMantic engine bound to :data:`DATABASE_NAME`.

    Note:
        Private by convention. Reach the connection through :func:`get_engine`
        or :func:`MongoDatabase` rather than instantiating this directly.

        Construction is not guarded by a lock. That is safe here because the
        instance is created on a single-threaded startup path; a multi-threaded
        initialiser would need one.
    """

    mongo_client: Optional[motor_asyncio.AsyncIOMotorClient] = None
    engine: Optional[AIOEngine] = None

    def __new__(cls):
        # Reuse the existing instance if one was already built.
        if not hasattr(cls, "instance"):
            cls.instance = super(_MongoClientSingleton, cls).__new__(cls)

            mongodb_uri = MONGODB_URL
            database_name = DATABASE_NAME

            # Motor manages the connection pool internally. This call performs
            # no I/O, so an unreachable host surfaces on first use, not here.
            cls.instance.mongo_client = motor_asyncio.AsyncIOMotorClient(
                mongodb_uri, driver=DRIVER_INFO
            )

            # ODMantic wraps the Motor client and adds model validation.
            cls.instance.engine = AIOEngine(
                client=cls.instance.mongo_client, database=database_name
            )

            # Logged so the target database is verifiable at a glance — the one
            # cheap check against a mis-ordered .env load.
            logger.info(f"MongoDB singleton initialised | DB: {database_name}")

        return cls.instance


def MongoDatabase() -> core.AgnosticDatabase:
    """
    Return the raw Motor database handle.

    Use for operations ODMantic does not cover — aggregation pipelines, bulk
    writes, index management, administrative commands.

    Returns:
        motor.core.AgnosticDatabase: The database named by
        :data:`DATABASE_NAME`, backed by the shared client.

    Warning:
        Documents read or written through this handle bypass
        :class:`odmantic.Model` validation entirely. Prefer :func:`get_engine`
        unless a specific operation makes it impossible.
    """
    return _MongoClientSingleton().mongo_client[DATABASE_NAME]


def get_engine() -> AIOEngine:
    """
    Return the shared ODMantic engine.

    The CRUD layer calls this in its constructor, which is why routers and
    controllers never need to receive a database handle as a dependency.

    Returns:
        odmantic.AIOEngine: Engine bound to :data:`DATABASE_NAME`, offering
        ``save``, ``find``, ``find_one`` and ``delete`` over
        :class:`odmantic.Model` subclasses.
    """
    return _MongoClientSingleton().engine


async def ping() -> None:
    """
    Verify the database is reachable.

    Raises:
        pymongo.errors.PyMongoError: If the server is unreachable, credentials
            are rejected, or the command times out.

    Note:
        Suitable for a readiness probe. A process that starts cleanly but cannot
        reach its database is not ready to serve traffic, and it is far cheaper
        to discover that at startup than on a user's first request.
    """
    await MongoDatabase().command("ping")
    logger.info("MongoDB ping successful")


async def connect_to_mongo() -> None:
    """
    Initialise the connection and confirm the database answers.

    Intended for the application's startup hook, so a misconfigured deployment
    fails immediately and visibly instead of degrading at request time.

    Raises:
        pymongo.errors.PyMongoError: If connectivity cannot be established.

    Note:
        Not yet wired into the FastAPI application. Until it is, the connection
        is created lazily on the first call to :func:`get_engine`. Registering
        this through FastAPI's ``lifespan`` parameter is the intended next step.
    """
    logger.info("Connecting to MongoDB...")
    _MongoClientSingleton()
    await ping()
    logger.info("MongoDB connection established")


async def close_mongo_connection() -> None:
    """
    Close the client and release its pooled sockets.

    Intended for the application's shutdown hook. Closing cleanly lets MongoDB
    reclaim server-side resources at once rather than waiting for the sockets to
    time out.

    Note:
        Safe to call when no client was ever created — the close is guarded.
    """
    singleton = _MongoClientSingleton()

    if singleton.mongo_client:
        singleton.mongo_client.close()
        logger.info("MongoDB connection closed")
