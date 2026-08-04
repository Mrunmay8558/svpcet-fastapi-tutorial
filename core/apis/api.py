from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi import Response
from core.apis.routes.user_router import user_router

# Step 1:
# Create the FastAPI application object.
# This is the central app instance where middleware, routers, and docs are registered.
app = FastAPI(
    title="SVPCET FastAPI Codebase Tutorial",
    version="0.1 - Beta",
    description="Tutorial project showing how to structure a FastAPI codebase.",
    redoc_url="/documentation",
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    # Step 2:
    # Let the request continue to the actual route or next middleware first.
    response = await call_next(request)

    # Step 3:
    # Add security-related response headers.
    # These headers help reduce common browser-based attacks.
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

    # Step 4:
    # Set an explicit allowed method header based on the current request method.
    # This is included here as a simple learning example.
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
    # Step 5:
    # Example endpoint showing how to set a secure cookie.
    # This is useful for teaching cookie flags like httponly, secure, and samesite.
    response.set_cookie(
        key="session",
        value="value",
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=1800,
    )


origins = ["*"]

# Step 6:
# Add CORS middleware so browsers can access this API from frontend apps.
# For a tutorial, "*" keeps the setup simple and easy to test.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, tags=["User Management"])


@app.get("/")
def root():
    return {"message": "Welcome to the SVPCET FastAPI Codebase Tutorial!"}


@app.get("/health")
def health_check():
    # Step 7:
    # A simple health check endpoint to verify the API is running.
    return {"status": "healthy"}


def custom_openapi():
    # Step 9:
    # Reuse the generated schema if it was already created earlier.
    if app.openapi_schema:
        return app.openapi_schema

    # Step 10:
    # Generate a custom OpenAPI schema using the app's routes and metadata.
    openapi_schema = get_openapi(
        title="FastAPI Codebase Tutorial",
        version="0.1 - Beta",
        description="Tutorial project showing how to structure a FastAPI codebase.",
        routes=app.routes,
    )

    # Step 11:
    # Store the schema on the app so it does not need to be rebuilt every time.
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Step 12:
# Replace FastAPI's default OpenAPI generator with our custom function.
app.openapi = custom_openapi
