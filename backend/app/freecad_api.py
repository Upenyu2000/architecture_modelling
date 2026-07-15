from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .models import BuildingModelFile, Job, Project
from .storage import load_project, project_dir, save_project, save_upload, write_json
from .services.freecad_bridge import (
    EXPORT_EXTENSIONS,
    SUPPORTED_IMPORT_SUFFIXES,
    export_scene,
    find_freecad_cmd,
    find_freecad_gui,
    freecad_status,
    history_summary,
    import_model,
    launch_freecad,
    model_tree,
    quantity_schedule,
    record_history,
    redo_history,
    scene_parameters,
    undo_history,
)
from .services.jobs import create_job, submit

router = APIRouter()


class FreeCADExportRequest(BaseModel):
    format: Literal["fcstd", "step", "iges", "brep", "ifc", "dxf", "svg", "stl", "obj"] = "fcstd"
    include_furniture: bool = True
    unit_system: Literal["metric", "imperial"] = "metric"


class FreeCADParameterUpdate(BaseModel):
    wall_height_m: float = Field(default=2.8, ge=1.8, le=20.0)
    default_wall_thickness_m: float = Field(default=0.16, ge=0.04, le=1.5)
    ceiling_height_m: float = Field(default=2.8, ge=1.8, le=20.0)
    cutaway_height_m: float = Field(default=1.65, ge=0.4, le=10.0)
    unit_system: Literal["metric", "imperial"] = "metric"


def _project_or_404(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _require_scene(project: Project):
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyse or create the architectural scene first")
    return project.scene


def _require_freecad() -> None:
    if not find_freecad_cmd():
        raise HTTPException(
            status_code=409,
            detail="FreeCADCmd was not found. Install FreeCAD 1.x or select FreeCADCmd.exe in Settings.",
        )


@router.get("/api/v1/freecad/status")
def get_freecad_status() -> dict[str, object]:
    return freecad_status()


@router.get("/api/v1/projects/{project_id}/freecad/model-tree")
def get_model_tree(project_id: str) -> dict[str, object]:
    project = _project_or_404(project_id)
    scene = _require_scene(project)
    return model_tree(scene)


@router.get("/api/v1/projects/{project_id}/freecad/quantities")
def get_quantities(project_id: str) -> dict[str, object]:
    project = _project_or_404(project_id)
    scene = _require_scene(project)
    return quantity_schedule(scene)


@router.get("/api/v1/projects/{project_id}/freecad/parameters")
def get_parameters(project_id: str) -> dict[str, object]:
    project = _project_or_404(project_id)
    scene = _require_scene(project)
    return scene_parameters(scene)


@router.put("/api/v1/projects/{project_id}/freecad/parameters", response_model=Project)
def update_parameters(project_id: str, request: FreeCADParameterUpdate) -> Project:
    project = _project_or_404(project_id)
    scene = _require_scene(project)
    record_history(project, "Initial parametric scene")
    scene.wall_height_m = request.wall_height_m
    scene.ceiling_height_m = request.ceiling_height_m
    scene.cutaway_height_m = min(request.cutaway_height_m, request.ceiling_height_m)
    for wall in scene.walls:
        wall.height = request.wall_height_m
        wall.thickness = request.default_wall_thickness_m
    project.status = "cad_parameters_updated"
    write_json(project_dir(project_id) / "working" / "scene.json", scene.model_dump(mode="json"))
    save_project(project)
    record_history(project, "Updated FreeCAD parameters")
    return project


@router.get("/api/v1/projects/{project_id}/freecad/history")
def get_history(project_id: str) -> dict[str, object]:
    project = _project_or_404(project_id)
    _require_scene(project)
    record_history(project, "Current parametric scene")
    return history_summary(project_id)


@router.post("/api/v1/projects/{project_id}/freecad/undo", response_model=Project)
def undo(project_id: str) -> Project:
    project = _project_or_404(project_id)
    _require_scene(project)
    record_history(project, "Current parametric scene")
    try:
        return undo_history(project_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/api/v1/projects/{project_id}/freecad/redo", response_model=Project)
def redo(project_id: str) -> Project:
    project = _project_or_404(project_id)
    _require_scene(project)
    try:
        return redo_history(project_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/api/v1/projects/{project_id}/freecad/export", response_model=Job)
def create_export(project_id: str, request: FreeCADExportRequest) -> Job:
    project = _project_or_404(project_id)
    _require_scene(project)
    _require_freecad()
    job = create_job(project_id, f"freecad_export_{request.format}")
    output_dir = project_dir(project_id) / "outputs" / f"freecad-{job.id[:8]}"
    extension = EXPORT_EXTENSIONS[request.format]
    output = output_dir / f"{project.name.replace(' ', '-')}{extension}"
    output_url = f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/{output.name}"
    quantity_path = output_dir / "quantity-schedule.json"
    tree_path = output_dir / "model-tree.json"

    def task(progress):
        output_dir.mkdir(parents=True, exist_ok=True)
        progress(3, "Preparing parametric model tree and quantity schedule")
        write_json(quantity_path, quantity_schedule(project.scene))
        write_json(tree_path, model_tree(project.scene))
        result = export_scene(
            project,
            output,
            request.format,
            request.include_furniture,
            request.unit_system,
            progress,
        )
        metadata = {
            **result,
            "quantity_schedule_url": f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/{quantity_path.name}",
            "model_tree_url": f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/{tree_path.name}",
            "freecad_version": freecad_status().get("version"),
            "parametric": True,
            "brep_kernel": "Open CASCADE",
        }
        return output, output_url, metadata

    return submit(job, task)


@router.post("/api/v1/projects/{project_id}/freecad/import", response_model=Job)
async def create_import(project_id: str, file: UploadFile = File(...)) -> Job:
    project = _project_or_404(project_id)
    _require_freecad()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_IMPORT_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported CAD/BIM file. Supported extensions: {', '.join(sorted(SUPPORTED_IMPORT_SUFFIXES))}",
        )
    source = await save_upload(project_id, file, "uploads/freecad", "cad-")
    job = create_job(project_id, "freecad_import")
    output_dir = project_dir(project_id) / "outputs" / f"freecad-import-{job.id[:8]}"
    fcstd_url = f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/imported-model.FCStd"

    def task(progress):
        result = import_model(source, output_dir, progress)
        obj = Path(str(result["obj"]))
        current = load_project(project_id)
        current.building_model = BuildingModelFile(
            filename=obj.name,
            path=str(obj),
            url=f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/{obj.name}",
            format="obj",
            size_bytes=obj.stat().st_size,
        )
        current.status = "freecad_model_imported"
        save_project(current)
        metadata = {
            **result,
            "fcstd_url": fcstd_url,
            "converted_model_url": current.building_model.url,
            "source_filename": source.name,
        }
        return Path(str(result["fcstd"])), fcstd_url, metadata

    return submit(job, task)


@router.post("/api/v1/projects/{project_id}/freecad/open", response_model=Job)
def open_in_freecad(project_id: str) -> Job:
    project = _project_or_404(project_id)
    _require_scene(project)
    _require_freecad()
    if not find_freecad_gui():
        raise HTTPException(status_code=409, detail="FreeCAD.exe was not found. Select it in Settings.")
    job = create_job(project_id, "freecad_open")
    output_dir = project_dir(project_id) / "outputs" / f"freecad-open-{job.id[:8]}"
    output = output_dir / f"{project.name.replace(' ', '-')}.FCStd"
    output_url = f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}/{output.name}"

    def task(progress):
        output_dir.mkdir(parents=True, exist_ok=True)
        result = export_scene(project, output, "fcstd", True, "metric", progress)
        progress(96, "Opening the editable parametric document in FreeCAD")
        launch_freecad(output)
        return output, output_url, result

    return submit(job, task)
