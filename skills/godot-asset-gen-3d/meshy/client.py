"""Meshy provider client for image-to-3D, humanoid rigging, and animation.

Official docs:
  https://docs.meshy.ai/en/api/image-to-3d
  https://docs.meshy.ai/en/api/rigging
  https://docs.meshy.ai/en/api/animation
"""

import base64
import os
import time
from pathlib import Path

import requests


API_BASE = "https://api.meshy.ai/openapi/v1"

TASK_ENDPOINTS = {
    "image-to-3d": "image-to-3d",
    "rigging": "rigging",
    "animation": "animations",
}


class SubmissionUnknownError(RuntimeError):
    """The POST may have been accepted, but no task ID was received."""


def get_api_key() -> str:
    key = os.environ.get("MESHY_API_KEY")
    if not key:
        raise ValueError("MESHY_API_KEY environment variable not set")
    return key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }


def image_data_uri(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    if suffix not in mime_types:
        raise ValueError("Meshy image input must be .png, .jpg, or .jpeg")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_types[suffix]};base64,{encoded}"


def _submit_task(endpoint: str, payload: dict) -> str:
    try:
        resp = requests.post(
            f"{API_BASE}/{endpoint}",
            headers=_headers(),
            json=payload,
            timeout=60,
        )
    except requests.exceptions.Timeout as exc:
        raise SubmissionUnknownError(
            f"Meshy {endpoint} submission timed out before a task ID was received"
        ) from exc
    if not resp.ok:
        raise RuntimeError(
            f"Meshy task submit failed: HTTP {resp.status_code}: {resp.text}"
        )
    return resp.json()["result"]


def create_image_to_3d_task(
    image_path: Path,
    *,
    pbr: bool = True,
    model_type: str = "standard",
    should_remesh: bool = True,
    target_polycount: int | None = 30000,
    hd_texture: bool = False,
    pose_mode: str = "",
) -> str:
    payload = {
        "image_url": image_data_uri(image_path),
        "model_type": model_type,
        "ai_model": "latest",
        "should_texture": True,
        "enable_pbr": pbr,
        "hd_texture": hd_texture,
        "should_remesh": should_remesh,
        "image_enhancement": True,
        "remove_lighting": True,
        "target_formats": ["glb"],
    }
    if should_remesh and model_type != "lowpoly" and target_polycount is not None:
        payload["topology"] = "triangle"
        payload["target_polycount"] = target_polycount
    if pose_mode:
        payload["pose_mode"] = pose_mode
    return _submit_task("image-to-3d", payload)


def create_rigging_task(model_task_id: str, *, height_meters: float = 1.7) -> str:
    return _submit_task(
        "rigging",
        {
            "input_task_id": model_task_id,
            "height_meters": height_meters,
        },
    )


def create_animation_task(rig_task_id: str, action_id: int) -> str:
    return _submit_task(
        "animations",
        {
            "rig_task_id": rig_task_id,
            "action_id": action_id,
        },
    )


def poll_task(
    task_id: str,
    task_type: str,
    *,
    timeout: int = 600,
    interval: int = 5,
) -> dict:
    try:
        endpoint = TASK_ENDPOINTS[task_type]
    except KeyError as exc:
        raise ValueError(f"Unknown Meshy task type: {task_type}") from exc

    start = time.time()
    url = f"{API_BASE}/{endpoint}/{task_id}"
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, headers=_headers(), timeout=60)
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(f"Meshy task {task_id} poll request timed out") from exc
        if not resp.ok:
            raise RuntimeError(
                f"Meshy task poll failed: HTTP {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        status = data.get("status")
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "CANCELED"):
            error = data.get("task_error", {}).get("message") or data
            raise RuntimeError(f"Meshy task {task_id} {status}: {error}")
        time.sleep(interval)
    raise TimeoutError(f"Meshy task {task_id} timed out after {timeout}s")


def consumed_credits(task_result: dict) -> int:
    return int(task_result.get("consumed_credits") or 0)


def download_model(task_result: dict, output_path: Path, task_type: str) -> Path:
    if task_type == "image-to-3d":
        url = task_result.get("model_urls", {}).get("glb")
    elif task_type == "rigging":
        url = task_result.get("result", {}).get("rigged_character_glb_url")
    elif task_type == "animation":
        url = task_result.get("result", {}).get("animation_glb_url")
    else:
        raise ValueError(f"Unknown Meshy task type: {task_type}")

    if not url:
        raise ValueError(f"No GLB URL in Meshy {task_type} result")
    try:
        resp = requests.get(url, timeout=120)
    except requests.exceptions.Timeout as exc:
        raise TimeoutError(f"Meshy {task_type} GLB download timed out") from exc
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    return output_path
