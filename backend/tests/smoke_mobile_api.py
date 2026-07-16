from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


workspace = tempfile.TemporaryDirectory(prefix="roomify-mobile-api-")
os.environ["DREAMHOME_DATA_DIR"] = str(Path(workspace.name) / "data")
os.environ["DREAMHOME_API_TOKEN"] = "mobile-test-token"

from app.asgi import app  # noqa: E402


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        payload = health.json()
        assert payload["version"] == "2.1.0", payload
        assert payload["android_client"] is True, payload

        unauthorized = client.get("/api/v1/projects")
        assert unauthorized.status_code == 401, unauthorized.text

        authorized = client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer mobile-test-token"},
        )
        assert authorized.status_code == 200, authorized.text

        image_style_access = client.get(
            "/api/v1/projects?access_token=mobile-test-token",
        )
        assert image_style_access.status_code == 200, image_style_access.text

        preflight = client.options(
            "/api/v1/projects",
            headers={
                "Origin": "https://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.headers.get("access-control-allow-origin") == "https://localhost", preflight.headers

    print("Android API smoke test passed: Capacitor CORS, optional bearer protection and authenticated file URLs are enabled.")


if __name__ == "__main__":
    try:
        main()
    finally:
        os.environ.pop("DREAMHOME_API_TOKEN", None)
        os.environ.pop("DREAMHOME_DATA_DIR", None)
        workspace.cleanup()
