from __future__ import annotations

import os

import uvicorn

# Import one ASGI application for both development and PyInstaller builds.
# The ASGI module registers architecture compilation and opening CRUD routes.
from app.asgi import app as fastapi_app


if __name__ == "__main__":
    uvicorn.run(
        fastapi_app,
        host=os.getenv("DREAMHOME_HOST", "127.0.0.1"),
        port=int(os.getenv("DREAMHOME_PORT", "8765")),
        log_level="info",
    )
