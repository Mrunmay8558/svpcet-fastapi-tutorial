"""
api.py — Application assembly.

Constructs the FastAPI instance and wires everything attached to it: security
headers, CORS, routers, operational endpoints, and the OpenAPI schema. This
module is the composition root — importing ``app`` from here yields a fully
configured application, which is what both :mod:`main` and any ASGI server
target.

Structure:
    1. Application instance
    2. Security-header middleware
    3. CORS policy
    4. Router registration
    5. Operational endpoints (``/``, ``/health``)
    6. OpenAPI schema customisation

Note:
    Business logic never appears here. This module composes; the routers it
    registers delegate to controllers, which own the rules.
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from core.apis.routes.user_router import user_router
from core.apis.routes.order_router import order_router

#: The ASGI application. Referenced as ``core.apis.api:app`` by the server.
app = FastAPI(
    title="SVPCET FastAPI Codebase Tutorial",
    version="0.1 - Beta",
    description="Tutorial project showing how to structure a FastAPI codebase.",
    redoc_url="/documentation",
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """
    Attach hardening headers to every outbound response.

    Middleware wraps the entire request cycle, so these headers are applied
    uniformly — including on error responses, which are easy to miss when
    headers are set per route.

    Args:
        request: The incoming request.
        call_next: Continuation that dispatches to the next middleware or the
            matched route and returns its response.

    Returns:
        starlette.responses.Response: The downstream response with security
        headers added.

    Note:
        Headers applied and the attack each addresses:

        * ``X-Frame-Options: DENY`` — refuses framing by another origin,
          defeating clickjacking, where a hostile page overlays an invisible
          frame of this site so a user's clicks land on it unknowingly.
        * ``X-Content-Type-Options: nosniff`` — stops the browser from
          second-guessing a declared content type, which can otherwise turn an
          uploaded file into executable script.
        * ``X-XSS-Protection`` — legacy filter toggle, retained for old
          browsers; superseded by Content-Security-Policy.
        * ``Strict-Transport-Security`` — pins the origin to HTTPS for a year,
          closing the window in which an initial plaintext request could be
          intercepted.
        * ``Permissions-Policy`` — withholds geolocation and microphone access.
        * ``Cache-Control: no-store`` — keeps authenticated responses out of
          browser and proxy caches, where a later user could retrieve them.
        * ``Server`` — replaces the software banner, since version disclosure
          tells an attacker which known vulnerabilities to try.

        ``Access-Control-Allow-Methods`` is then set to echo the request's own
        method. This is illustrative only; the CORS middleware below is what
        actually governs cross-origin access.
    """
    # Dispatch first — headers are applied to the response on its way out.
    response = await call_next(request)

    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Server"] = "Custom Server"

    method = request.method

    if method == "GET":
        response.headers["Access-Control-Allow-Methods"] = "GET"
    elif method == "POST":
        response.headers["Access-Control-Allow-Methods"] = "POST"
    elif method == "PUT":
        response.headers["Access-Control-Allow-Methods"] = "PUT"
    elif method == "DELETE":
        response.headers["Access-Control-Allow-Methods"] = "DELETE"

    return response


@app.get("/set-cookie")
def set_cookie(response: Response):
    """
    Demonstrate issuing a hardened cookie.

    Args:
        response: Response object injected by FastAPI, mutated to carry the
            ``Set-Cookie`` header.

    Returns:
        None: The response body is empty; the cookie travels in the header.

    Note:
        The flags are what make a session cookie safe to use:

        * ``httponly`` — hides the value from JavaScript, so injected script
          cannot read and exfiltrate the session.
        * ``secure`` — sends it only over HTTPS.
        * ``samesite="strict"`` — withholds it from cross-site requests,
          blocking cross-site request forgery.
        * ``max_age`` — bounds its lifetime to 30 minutes.

    Warning:
        A demonstration endpoint. Remove it before deploying; it serves no
        purpose in a real deployment and needlessly widens the API surface.
    """
    response.set_cookie(
        key="session",
        value="value",
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=1800,
    )


#: Origins permitted to call this API from a browser.
#:
#: ``"*"`` allows every origin, which is convenient for local work and too
#: permissive for a deployment. Replace it with an explicit list, e.g.
#: ``["https://app.example.com"]``.
#:
#: Note that ``"*"`` combined with ``allow_credentials=True`` is rejected by
#: browsers, so credentialed cross-origin requests will not succeed under this
#: configuration regardless.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, tags=["User Management"])
app.include_router(order_router, tags=["Order Management"])


@app.get("/")
def root():
    """
    Return a greeting confirming the application is serving.

    Returns:
        dict: ``{"message": str}``.
    """
    return {"message": "Welcome to the SVPCET FastAPI Codebase Tutorial!"}


@app.get("/health")
def health_check():
    """
    Report process liveness.

    Consumed by load balancers, container orchestrators, and uptime monitors,
    which restart or drain an instance that stops answering.

    Returns:
        dict: ``{"status": "healthy"}``.

    Note:
        This is a liveness check only — it reports that the process is running,
        not that its dependencies are reachable. A readiness check would also
        call :func:`core.database.database.ping`, so an instance that cannot
        reach MongoDB is removed from rotation rather than served traffic it
        will fail.
    """
    return {"status": "healthy"}


def custom_openapi():
    """
    Build and cache the OpenAPI schema.

    Returns:
        dict: The OpenAPI document backing ``/docs`` and ``/documentation``.

    Note:
        The schema is generated once and stored on ``app.openapi_schema``;
        later calls return the cached document instead of walking every route
        again.

        Assigned to ``app.openapi`` below, replacing FastAPI's default
        generator. This is also the hook for adding shared metadata — security
        schemes, servers, tags — that cannot be expressed on individual routes.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="FastAPI Codebase Tutorial",
        version="0.1 - Beta",
        description="Tutorial project showing how to structure a FastAPI codebase.",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
