from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from starlette.datastructures import UploadFile

from app import storage
from app.storage import UploadStorageError, project_dir, save_upload


async def _save(
    project_id: str,
    filename: str,
    data: bytes,
    prefix: str = "",
    folder: str = "uploads",
) -> Path:
    upload = UploadFile(file=io.BytesIO(data), filename=filename, size=len(data))
    return await save_upload(project_id, upload, folder, prefix)


async def run_checks() -> None:
    original_projects_dir = storage.PROJECTS_DIR
    original_limit = os.environ.get("DREAMHOME_MAX_UPLOAD_BYTES")
    with TemporaryDirectory() as temporary:
        storage.PROJECTS_DIR = Path(temporary) / "projects"
        os.environ["DREAMHOME_MAX_UPLOAD_BYTES"] = str(1024 * 1024)
        try:
            destination = await _save("project", "../unsafe plan.png", b"valid-plan", "floorplan-")
            assert destination.name == "floorplan-unsafe_plan.png"
            assert destination.read_bytes() == b"valid-plan"
            assert destination.parent == project_dir("project") / "uploads"
            assert not list(destination.parent.glob("*.upload"))

            replacement_candidate = await _save("project", "unsafe plan.png", b"new-candidate", "floorplan-")
            assert replacement_candidate != destination
            assert replacement_candidate.read_bytes() == b"new-candidate"
            assert destination.read_bytes() == b"valid-plan", "A new candidate must not overwrite the current valid source before semantic validation."

            prefixed = await _save("project", "chair.glb", b"model", "../dining/slot-")
            assert prefixed.parent == destination.parent
            assert "/" not in prefixed.name and "\\" not in prefixed.name
            assert prefixed.read_bytes() == b"model"

            try:
                await _save("../outside", "escape.bin", b"escape")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Invalid project identifiers must not escape the project root.")

            try:
                await _save("project", "escape.bin", b"escape", folder="../outside")
            except UploadStorageError as exc:
                assert exc.status_code == 400
            else:
                raise AssertionError("Invalid upload folders must not escape the project root.")

            try:
                await _save("project", "empty.png", b"", "floorplan-")
            except UploadStorageError as exc:
                assert exc.status_code == 422
            else:
                raise AssertionError("An empty upload must be rejected.")
            assert destination.read_bytes() == b"valid-plan", "A failed replacement must preserve the previous valid file."

            try:
                await _save("project", "large.bin", b"x" * (1024 * 1024 + 1))
            except UploadStorageError as exc:
                assert exc.status_code == 413
            else:
                raise AssertionError("An oversized upload must be rejected.")
            assert not (destination.parent / "large.bin").exists()
            assert not list(destination.parent.glob("*.upload"))
        finally:
            storage.PROJECTS_DIR = original_projects_dir
            if original_limit is None:
                os.environ.pop("DREAMHOME_MAX_UPLOAD_BYTES", None)
            else:
                os.environ["DREAMHOME_MAX_UPLOAD_BYTES"] = original_limit


def main() -> None:
    asyncio.run(run_checks())
    print("Storage smoke test passed: collision-safe candidates, project/folder/prefix traversal protection, safe filenames, atomic replacement, empty-file rejection, size limits and temporary-file cleanup.")


if __name__ == "__main__":
    main()
