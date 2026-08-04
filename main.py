"""
main.py — Development entry point.

Launches the ASGI server for local work. The module is deliberately thin: the
application object, its middleware, and its routes are all assembled in
:mod:`core.apis.api`, so nothing here needs to change as the API grows.

Usage:
    Local development::

        python main.py

    Equivalent, invoking uvicorn directly::

        uvicorn core.apis.api:app --reload --port 8000

Warning:
    The settings below are development settings.

    ``reload=True`` watches the filesystem and restarts the process on every
    change. It is unsuitable for production: it costs CPU, it holds extra file
    descriptors, and a restart mid-request drops that request.

    ``host="0.0.0.0"`` binds every network interface, so the server is reachable
    from other machines on the network. Bind ``127.0.0.1`` if it should stay
    local to this machine.

    A deployment runs a process manager instead — for example
    ``gunicorn -k uvicorn.workers.UvicornWorker`` with several workers behind a
    reverse proxy that terminates TLS.

Note:
    ``server_header=False`` suppresses the ``server: uvicorn`` response header.
    Advertising the server software and version tells an attacker which
    published vulnerabilities are worth attempting.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "core.apis.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only — see the module docstring.
        server_header=False,  # Do not advertise the server software or version.
    )
