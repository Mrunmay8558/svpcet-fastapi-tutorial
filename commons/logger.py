"""
logger.py — Application-wide logging configuration.

Provides a single factory, :func:`logger`, that returns a named logger writing
to both the console and ``logs/debug.log``. Every module obtains its logger the
same way, which keeps log formatting consistent and makes each record traceable
back to the module that emitted it.

Usage:
    >>> from core import logger
    >>> logging = logger(__name__)
    >>> logging.info("User created")

Record format:
    ``[pid=<pid>] - [timestamp] - [module] - [LEVEL] - [message]``

    The process id matters once the application runs under multiple workers:
    interleaved records from concurrent processes can otherwise be impossible to
    separate.

Note:
    ``logs/`` is excluded from version control. Log files are runtime artefacts,
    and they routinely contain data that must not be committed.

Warning:
    Never log credentials, password hashes, tokens, or OTP codes. Logs are
    copied, forwarded to aggregators, and read by people who are not authorised
    to see that material.
"""

import logging
import os


def get_file_handler(
    log_name: str, mode: int, formatter: logging.Formatter, save_path: str = "logs"
):
    """
    Build a file handler that appends records to ``<save_path>/<log_name>``.

    The destination directory is created if it does not exist, so a fresh
    checkout runs without any manual setup.

    Args:
        log_name: File name to write to, e.g. ``"debug.log"``.
        mode: Minimum level this handler records, e.g. :data:`logging.DEBUG`.
            Named ``mode`` for historical reasons; it is a level, not a file
            mode.
        formatter: Formatter controlling the layout of each record.
        save_path: Directory for the log file. Defaults to ``"logs"``, resolved
            relative to the process's working directory.

    Returns:
        logging.FileHandler: A configured handler, not yet attached to a logger.

    Note:
        Records are appended, never truncated, so history survives a restart.
        The file grows without bound — a deployed service should rotate it, for
        example with :class:`logging.handlers.RotatingFileHandler`.
    """
    os.makedirs(save_path, exist_ok=True)
    file_handler = logging.FileHandler(
        filename=os.path.join(save_path, log_name), mode="a"
    )
    file_handler.setLevel(mode)
    file_handler.setFormatter(formatter)
    return file_handler


def config_logger(logger: logging.Logger, debug_mode: bool = True):
    """
    Attach a console handler and a debug file handler to a logger.

    Both handlers share one formatter, so a record reads identically on screen
    and on disk.

    Args:
        logger: The logger instance to configure. Modified in place.
        debug_mode: Reserved for toggling verbosity. Currently unused; the
            logger is always configured at :data:`logging.DEBUG`.

    Returns:
        logging.Logger: The same instance, now carrying both handlers.

    Warning:
        Handlers are added unconditionally. Calling this twice for the same
        logger name attaches a second pair and each record is then emitted
        twice. Obtain loggers only through :func:`logger`, once per module at
        import time.
    """
    formatter = logging.Formatter(
        "[pid=%(process)s] - [%(asctime)s] - [%(name)s] - [%(levelname)s] - [%(message)s]"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    debug_file_handler = get_file_handler(
        log_name="debug.log", mode=logging.DEBUG, formatter=formatter
    )

    logger.addHandler(console_handler)
    logger.addHandler(debug_file_handler)
    logger.setLevel(logging.DEBUG)
    return logger


def logger(__name__):
    """
    Return a fully configured logger named after the calling module.

    Args:
        __name__: The caller's ``__name__``. Passing the built-in directly makes
            each record carry the originating module path, so a message can be
            traced to its source without searching for the text.

    Returns:
        logging.Logger: A logger writing to the console and ``logs/debug.log``.

    Example:
        >>> logging = logger(__name__)
        >>> logging.error("Error in UserController.register_user: ...")
    """
    logging_obj = config_logger(logging.getLogger(__name__))
    return logging_obj
