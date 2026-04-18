"""Google Veo video generation client.

Implements the Vertex AI workflow the way the official docs describe it:
- Vertex auth via ADC
- first/last frame inputs from GCS URIs
- output written to GCS
- local download from GCS after generation completes
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import time
import uuid
from typing import Any
from urllib.parse import quote

import requests
import structlog
from dotenv import load_dotenv
from google import genai
from google.auth import default as google_auth_default
from google.auth.transport.requests import AuthorizedSession, Request
from google.genai import types

load_dotenv(override=True)

logger = structlog.get_logger()

_CLOUD_PLATFORM_SCOPE = ["https://www.googleapis.com/auth/cloud-platform"]


def _bool_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _use_vertex() -> bool:
    return _bool_env("GOOGLE_GENAI_USE_VERTEXAI") or _bool_env("VERTEX_AI")


def _vertex_project() -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT/GCLOUD_PROJECT is not set for Vertex Veo.")
    return project


def _vertex_location() -> str:
    return os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION") or "global"


def _gcs_bucket_name() -> str:
    return os.getenv("VEO_GCS_BUCKET") or f"{_vertex_project()}-veo-artifacts"


def _adc_session() -> AuthorizedSession:
    creds, _ = google_auth_default(scopes=_CLOUD_PLATFORM_SCOPE)
    if not creds.valid:
        creds.refresh(Request())
    return AuthorizedSession(creds)


def _gcs_json_url(path: str) -> str:
    return f"https://storage.googleapis.com/storage/v1/{path.lstrip('/')}"


def _ensure_bucket(bucket: str) -> None:
    project = _vertex_project()
    session = _adc_session()
    resp = session.get(_gcs_json_url(f"/b/{bucket}"), timeout=30)
    if resp.status_code == 200:
        return
    if resp.status_code not in (404,):
        raise RuntimeError(f"Failed checking GCS bucket {bucket}: {resp.status_code} {resp.text[:300]}")

    body = {
        "name": bucket,
        "location": "US",
        "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}},
    }
    create = session.post(
        f"https://storage.googleapis.com/storage/v1/b?project={project}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=60,
    )
    if create.status_code not in (200, 201, 409):
        raise RuntimeError(f"Failed creating GCS bucket {bucket}: {create.status_code} {create.text[:300]}")


def _upload_file_to_gcs(local_path: str, bucket: str, object_name: str) -> str:
    session = _adc_session()
    mime_type, _ = mimetypes.guess_type(local_path)
    with open(local_path, "rb") as f:
        data = f.read()
    url = (
        f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
        f"?uploadType=media&name={quote(object_name, safe='')}"
    )
    resp = session.post(
        url,
        headers={"Content-Type": mime_type or "application/octet-stream"},
        data=data,
        timeout=120,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed uploading {local_path} to gs://{bucket}/{object_name}: {resp.status_code} {resp.text[:300]}")
    return f"gs://{bucket}/{object_name}"


def _list_gcs_objects(bucket: str, prefix: str) -> list[str]:
    session = _adc_session()
    resp = session.get(
        _gcs_json_url(f"/b/{bucket}/o?prefix={quote(prefix, safe='')}"),
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed listing gs://{bucket}/{prefix}: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    return [item["name"] for item in data.get("items", [])]


def _download_gcs_object(bucket: str, object_name: str, output_path: str) -> str:
    session = _adc_session()
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(object_name, safe='')}?alt=media"
    resp = session.get(url, stream=True, timeout=300)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed downloading gs://{bucket}/{object_name}: {resp.status_code} {resp.text[:300]}")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    return output_path


def _image_for_vertex(local_path: str, bucket: str, object_name: str) -> types.Image:
    gs_uri = _upload_file_to_gcs(local_path, bucket, object_name)
    mime_type, _ = mimetypes.guess_type(local_path)
    return types.Image(gcs_uri=gs_uri, mime_type=mime_type or "image/png")


def _video_for_vertex(local_path: str, bucket: str, object_name: str) -> types.Video:
    gs_uri = _upload_file_to_gcs(local_path, bucket, object_name)
    mime_type, _ = mimetypes.guess_type(local_path)
    return types.Video(uri=gs_uri, mime_type=mime_type or "video/mp4")


def _build_client() -> genai.Client:
    if _use_vertex():
        return genai.Client(
            vertexai=True,
            project=_vertex_project(),
            location=_vertex_location(),
        )

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set.")
    return genai.Client(api_key=api_key)


def _vertex_output_prefix(bucket: str) -> tuple[str, str]:
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    prefix = f"veo/manual/{run_id}/"
    return prefix, f"gs://{bucket}/{prefix}"


def _download_result_video(client: genai.Client, op: Any, output_path: str, output_gcs_uri: str | None) -> str:
    if _use_vertex():
        result_dump = {}
        if getattr(op, "result", None) is not None:
            if hasattr(op.result, "model_dump"):
                result_dump = op.result.model_dump(exclude_none=True)
            elif isinstance(op.result, dict):
                result_dump = op.result
        if not output_gcs_uri:
            raise RuntimeError("Vertex Veo requires output_gcs_uri to download results.")
        bucket_and_prefix = output_gcs_uri.removeprefix("gs://")
        bucket, prefix = bucket_and_prefix.split("/", 1)
        objects = _list_gcs_objects(bucket, prefix)
        mp4s = [name for name in objects if name.endswith(".mp4")]
        if not mp4s:
            filtered_count = result_dump.get("rai_media_filtered_count") or result_dump.get("raiMediaFilteredCount")
            filtered_reasons = result_dump.get("rai_media_filtered_reasons") or result_dump.get("raiMediaFilteredReasons")
            if filtered_count:
                raise RuntimeError(
                    f"Veo filtered the request and produced no video. "
                    f"filtered_count={filtered_count} reasons={filtered_reasons}"
                )
            raise RuntimeError(f"No MP4 found under {output_gcs_uri}. Objects: {objects} result={result_dump}")
        mp4s.sort()
        return _download_gcs_object(bucket, mp4s[0], output_path)

    if not op.result or not op.result.generated_videos:
        raise RuntimeError(f"Veo returned no generated videos. error={getattr(op, 'error', None)}")
    video = op.result.generated_videos[0]
    data = client.files.download(file=video.video)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def generate_video(
    *,
    prompt: str,
    output_path: str,
    model: str = "veo-3.1-generate-001",
    duration_seconds: int = 4,
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
    image_path: str | None = None,
    video_path: str | None = None,
    last_frame_path: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    generate_audio: bool = False,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Generate a Veo clip and save it locally."""

    client = _build_client()
    log = logger.bind(model=model, duration_seconds=duration_seconds, aspect_ratio=aspect_ratio, vertex=_use_vertex())
    log.info(
        "submitting veo generation",
        image=bool(image_path),
        video=bool(video_path),
        last_frame=bool(last_frame_path),
    )

    output_gcs_uri: str | None = None
    source_image: types.Image | None = None
    source_video: types.Video | None = None
    last_frame_image: types.Image | None = None

    if _use_vertex():
        bucket = _gcs_bucket_name()
        _ensure_bucket(bucket)
        prefix, output_gcs_uri = _vertex_output_prefix(bucket)
        if image_path:
            source_image = _image_for_vertex(image_path, bucket, f"{prefix}inputs/start{os.path.splitext(image_path)[1] or '.png'}")
        if video_path:
            source_video = _video_for_vertex(video_path, bucket, f"{prefix}inputs/source{os.path.splitext(video_path)[1] or '.mp4'}")
        if last_frame_path:
            last_frame_image = _image_for_vertex(last_frame_path, bucket, f"{prefix}inputs/end{os.path.splitext(last_frame_path)[1] or '.png'}")
    else:
        if image_path:
            mime_type, _ = mimetypes.guess_type(image_path)
            source_image = types.Image.from_file(location=image_path, mime_type=mime_type or "image/png")
        if video_path:
            mime_type, _ = mimetypes.guess_type(video_path)
            source_video = types.Video.from_file(location=video_path, mime_type=mime_type or "video/mp4")
        if last_frame_path:
            mime_type, _ = mimetypes.guess_type(last_frame_path)
            last_frame_image = types.Image.from_file(location=last_frame_path, mime_type=mime_type or "image/png")

    if image_path and video_path:
        raise ValueError("Pass either image_path or video_path to Veo, not both.")

    source = types.GenerateVideosSource(
        prompt=prompt,
        image=source_image,
        video=source_video,
    )
    config_kwargs: dict[str, Any] = {
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "duration_seconds": duration_seconds,
        "number_of_videos": 1,
        "output_gcs_uri": output_gcs_uri,
    }
    if negative_prompt:
        config_kwargs["negative_prompt"] = negative_prompt
    if seed is not None:
        config_kwargs["seed"] = seed
    if last_frame_image:
        config_kwargs["last_frame"] = last_frame_image
    if generate_audio:
        config_kwargs["generate_audio"] = True

    config = types.GenerateVideosConfig(**config_kwargs)

    try:
        op = client.models.generate_videos(
            model=model,
            source=source,
            config=config,
        )
    except Exception as e:
        msg = str(e)
        if last_frame_path and not _use_vertex() and "currently not supported" in msg.lower():
            raise RuntimeError(
                "Veo start/end-frame interpolation is not supported on the Gemini API path. "
                "Use Vertex AI credentials plus GCS-backed inputs."
            ) from e
        raise

    start = time.time()
    log.info("veo submitted", operation=getattr(op, "name", None), output_gcs_uri=output_gcs_uri)

    while not op.done:
        time.sleep(10)
        op = client.operations.get(op)
        elapsed = time.time() - start
        log.info("veo polling", operation=getattr(op, "name", None), elapsed=int(elapsed))
        if elapsed > timeout_seconds:
            raise RuntimeError(f"Veo generation timed out after {timeout_seconds}s")

    if getattr(op, "error", None):
        raise RuntimeError(f"Veo failed: {op.error}")

    path = _download_result_video(client, op, output_path, output_gcs_uri)
    elapsed = time.time() - start
    log.info("veo saved", path=path, elapsed=f"{elapsed:.1f}s")
    return {
        "path": path,
        "operation": getattr(op, "name", None),
        "elapsed_seconds": elapsed,
        "model": model,
        "image_path": image_path,
        "video_path": video_path,
        "last_frame_path": last_frame_path,
        "output_gcs_uri": output_gcs_uri,
    }


async def generate_video_async(**kwargs: Any) -> dict[str, Any]:
    """Async wrapper for Veo generation."""

    return await asyncio.to_thread(generate_video, **kwargs)
