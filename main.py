"""
main.py — Application entry point.

Run with:
    python main.py
    OR
    uvicorn core.apis.api:app --reload --port 8000

The import here is intentionally minimal — all setup happens inside api.py.
main.py is only the launcher.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "core.apis.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on file changes (development only)
        server_header=False,  # Don't expose uvicorn version in response headers
    )
