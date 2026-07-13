from __future__ import annotations

import subprocess
from pathlib import Path

import httpx

from ..config import load_settings


def reconstruct_image_to_3d(input_path: Path, output_path: Path) -> Path | None:
    """Run an explicitly configured TRELLIS/Hunyuan command.

    The command must contain {input} and {output}. The application never invents a
    remote provider or silently uploads private home images.
    """
    settings = load_settings()
    command_template = str(settings.get("image_to_3d_command") or "").strip()
    if command_template:
        command = command_template.replace("{input}", str(input_path)).replace("{output}", str(output_path))
        completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60 * 60)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout)[-3000:])
        return output_path if output_path.exists() else None

    endpoint = str(settings.get("ai_endpoint") or "").strip()
    token = str(settings.get("ai_token") or "").strip()
    allowed = bool(settings.get("allow_remote_processing"))
    if endpoint and allowed:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with input_path.open("rb") as stream:
            response = httpx.post(endpoint, headers=headers, files={"file": (input_path.name, stream)}, timeout=60 * 30)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
    return None
