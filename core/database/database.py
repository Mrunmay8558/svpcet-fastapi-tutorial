"""
database.py — MongoDB connection management using Motor (async) + ODMantic (ODM).

Concepts taught here:
    - Singleton pattern for database clients
    - Async MongoDB with Motor
    - ODMantic AIOEngine for type-safe queries
    - Simple configuration using one MongoDB URL and one database name
    - Shared engine access via get_engine() inside the CRUD layer
"""

import os
import logging
from motor import motor_asyncio, core
from odmantic import AIOEngine
from pymongo.driver_info import DriverInfo
from typing import Optional

# Set up basic logging so connection events are visible in the console.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DriverInfo helps MongoDB identify which application is making the connection.
DRIVER_INFO = DriverInfo(name="fastapi-tutorial", version="0.1.0")

# Read the MongoDB settings once from environment variables.
# These values are then reused throughout this file.
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fastapi_tutorial")


class _MongoClientSingleton:
    """
    Singleton that holds the async Motor client and the ODMantic engine.

    Why a singleton?
    MongoDB connections are expensive to create. We create ONE connection pool
    at startup and reuse it across every request — this is the industry standard.
    """

    mongo_client: Optional[motor_asyncio.AsyncIOMotorClient] = None
    engine: Optional[AIOEngine] = None

    def __new__(cls):
        # Step 1:
        # Check whether we already created the singleton instance earlier.
        # If it already exists, we reuse it instead of creating a new connection.
        if not hasattr(cls, "instance"):
            # Step 2:
            # Create the singleton object for the first time.
            cls.instance = super(_MongoClientSingleton, cls).__new__(cls)

            # Keep the tutorial simple: one connection string and one database name.
            mongodb_uri = MONGODB_URL
            database_name = DATABASE_NAME

            # Step 3:
            # Create the async MongoDB client.
            # Motor manages the connection pool for us under the hood.
            cls.instance.mongo_client = motor_asyncio.AsyncIOMotorClient(
                mongodb_uri, driver=DRIVER_INFO
            )

            # Step 4:
            # Wrap the Motor client with ODMantic's engine.
            # This is what the CRUD layer uses for model-based queries.
            cls.instance.engine = AIOEngine(
                client=cls.instance.mongo_client, database=database_name
            )

            # Step 5:
            # Log the database name so developers can confirm the connection target.
            logger.info(f"MongoDB singleton initialised | DB: {database_name}")

        # Step 6:
        # Always return the same singleton instance.
        return cls.instance


def MongoDatabase() -> core.AgnosticDatabase:
    """
    Return the raw cMotor database object.
    Use this when you need to run raw MongoDB queries (aggregations, etc.).
    """
    # Step 1: get the singleton client.
    # Step 2: select the configured database from that client.
    return _MongoClientSingleton().mongo_client[DATABASE_NAME]


def get_engine() -> AIOEngine:
    """
    Return the ODMantic AIOEngine instance.
    CRUD classes import this function directly so the router and controller
    layers do not need to receive a database dependency.
    """
    # Return the ODMantic engine stored inside the singleton.
    return _MongoClientSingleton().engine


async def ping():
    """Verify the MongoDB connection is alive."""
    # Run MongoDB's built-in ping command.
    # If this fails, the application should treat the database as unavailable.
    await MongoDatabase().command("ping")
    logger.info("MongoDB ping successful")


async def connect_to_mongo():
    """
    Called during application startup (lifespan).
    Initialises the singleton and verifies connectivity.
    """
    logger.info("Connecting to MongoDB...")

    # Step 1: create the singleton if it does not already exist.
    _MongoClientSingleton()

    # Step 2: confirm that the database is reachable.
    await ping()

    # Step 3: log success so startup flow is easy to trace.
    logger.info("MongoDB connection established")


async def close_mongo_connection():
    """
    Called during application shutdown (lifespan).
    Closes the Motor client to release all connection pool resources.
    """
    # Step 1: fetch the same singleton instance used during startup.
    singleton = _MongoClientSingleton()

    # Step 2: close the MongoDB client only if it exists.
    if singleton.mongo_client:
        singleton.mongo_client.close()

        # Step 3: log shutdown completion for easier debugging.
        logger.info("MongoDB connection closed")
