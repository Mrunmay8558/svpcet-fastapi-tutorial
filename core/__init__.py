"""
core — Application package initialiser.

Runs two pieces of setup that must happen before anything else in the package.

Environment loading
    :func:`dotenv.load_dotenv` is called here, not in a submodule. Python
    executes a package's ``__init__`` before any of its submodules, so this is
    the earliest point at which every ``core.*`` import is guaranteed to see the
    values from ``.env``.

    The ordering is load-bearing. :mod:`core.database.database` resolves
    ``MONGODB_URL`` and ``DATABASE_NAME`` at import time; if ``.env`` has not
    been loaded by then, :func:`os.getenv` returns nothing, the module's
    fallbacks apply, and the application connects to the wrong database without
    raising anything.

Logger re-export
    :func:`commons.logger.logger` is re-exported so modules can obtain a logger
    with ``from core import logger`` rather than reaching into ``commons``
    directly.

Usage:
    >>> from core import logger
    >>> logging = logger(__name__)
"""

from dotenv import load_dotenv

load_dotenv()

from commons.logger import logger  # noqa: E402  (must follow load_dotenv)
