from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import Job, Project
from .storage import load_project, project_dir, write_json
from .services.jobs import create_job, submit
from .services.presentation import STYLE_PRESETS, available_styles, prepare_presentation_scene
from .services.rendering_v20 import render_presentation_views


router = APIRouter()


class PresentationRenderRequest(BaseModel):
    style: str = Field(default="modern", min_length=2, max_length=60)
    quality: Literal["preview", "1080p", "4k"] = "1080p"
    engine: Literal["auto", "blender"] = "auto"
    auto_furnish: bool = True
    optimize_dining: bool = True


def _project_or_404(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _remove_failed_outputs(output_dir: Path, archive: Path, temporary_archive: Path) -> None:
    shutil.rmtree(output_dir, ignore_errors=True)
    archive.unlink(missing_ok=True)
    temporary_archive.unlink(missing_ok=True)


@router.get("/api/v1/design-styles")
def design_styles() -> dict[str, object]:
    return {"styles": available_styles(), "default": "modern"}


@router.post("/api/v1/projects/{project_id}/presentation-renders", response_model=Job)
def create_presentation_renders(project_id: str, request: PresentationRenderRequest) -> Job:
    project = _project_or_404(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyse or create the floor-plan geometry first")
    if request.style not in STYLE_PRESETS:
        raise HTTPException(status_code=422, detail=f"Unknown design style: {request.style}")

    job = create_job(project_id, "architectural_presentation")
    output_dir = project_dir(project_id) / "outputs" / f"presentation-{job.id[:8]}"
    scene_path = output_dir / "presentation-scene.json"
    top_down = output_dir / "top-down.png"
    perspective = output_dir / "eye-level-interior.png"
    manifest_path = output_dir / "presentation.json"
    archive = output_dir.with_suffix(".zip")
    temporary_archive = archive.with_name(f".{archive.name}.tmp")
    url_root = f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}"
    archive_url = f"/api/v1/projects/{project_id}/files/outputs/{archive.name}"

    def task(progress):
        _remove_failed_outputs(output_dir, archive, temporary_archive)
        try:
            progress(3, "Preparing verified text-free floor-plan geometry")
            payload, metadata = prepare_presentation_scene(
                project.scene,
                request.style,
                auto_furnish=request.auto_furnish,
                optimise_dining=request.optimize_dining,
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(scene_path, payload)
            render_presentation_views(
                scene_path,
                top_down,
                perspective,
                request.quality,
                request.engine,
                progress,
            )

            top_url = f"{url_root}/{top_down.name}"
            perspective_url = f"{url_root}/{perspective.name}"
            result_metadata = {
                **metadata,
                "quality": request.quality,
                "engine": request.engine,
                "top_down_url": top_url,
                "top_down_path": str(top_down),
                "perspective_url": perspective_url,
                "perspective_path": str(perspective),
                "bundle_url": archive_url,
                "bundle_path": str(archive),
                "source_geometry_preserved": True,
                "room_proportions_preserved": True,
            }
            write_json(manifest_path, result_metadata)
            progress(97, "Packaging top-down and eye-level presentation files")
            with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.write(top_down, top_down.name)
                bundle.write(perspective, perspective.name)
                bundle.write(manifest_path, manifest_path.name)
            if not temporary_archive.exists() or temporary_archive.stat().st_size < 128:
                raise RuntimeError("Presentation archive was not created correctly")
            temporary_archive.replace(archive)
            return archive, archive_url, result_metadata
        except Exception:
            _remove_failed_outputs(output_dir, archive, temporary_archive)
            raise

    return submit(job, task)
