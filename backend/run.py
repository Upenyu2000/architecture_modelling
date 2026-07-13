from __future__ import annotations

import os

import uvicorn

# Import the ASGI application directly so PyInstaller can discover and bundle
# the complete backend package. Do not pass "app.main:app" as a string here.
from app.main import app as fastapi_app
from app.architecture_api import router as architecture_router

fastapi_app.include_router(architecture_router)


if __name__ == "__main__":
    uvicorn.run(
        fastapi_app,
        host=os.getenv("DREAMHOME_HOST", "127.0.0.1"),
        port=int(os.getenv("DREAMHOME_PORT", "8765")),
        log_level="info",
    )
