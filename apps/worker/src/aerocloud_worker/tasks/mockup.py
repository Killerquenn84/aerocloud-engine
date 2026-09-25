"""Celery task: mockup.render (Sprint P23, Phase B).

Open-source PSD-mockup compositor — calls MockupEngine from Phase A.

Pipeline:
    1. Download PSD via httpx (timeout, redirects disallowed)
    2. Download Design via httpx
    3. Compute SHA-256 over (psd_bytes || \x00 || design_bytes || \x00 || layer_name)
    4. Redis cache lookup at key "mockup:cache:<sha256>" — HIT returns immediately
    5. MockupEngine.render(psd_path, design_path, layer_name)
    6. Save output PNG to MOCKUP_OUTPUT_DIR/<sha256>.png — output_url is the
       absolute file path (file:// style) when no MOCKUP_PUBLIC_BASE_URL is set,
       otherwise '<MOCKUP_PUBLIC_BASE_URL>/<sha256>.png'.
    7. Write Redis cache with TTL 30 days
    8. Publish progress to mockup:progress:{task_id} (10/30/70/100)

Design decisions:
    - Synchronous Celery task (matches existing render.render_task pattern).
    - httpx imported at module level for monkeypatch in tests.
    - redis_lib imported at module level for monkeypatch in tests.
    - MockupEngine imported at module level so tests can patch the symbol.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import redis as redis_lib

from aerocloud.models.api import MockupRenderRequest
from aerocloud_worker.celery_app import app
from aerocloud_worker.mockup import MockupEngine

log = logging.getLogger(__name__)

# 30 days TTL for the idempotency cache (Scenario 10)
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


def _cache_key(psd_bytes: bytes, design_bytes: bytes, layer_name: str) -> str:
    h = hashlib.sha256()
    h.update(psd_bytes)
    h.update(b"\x00")
    h.update(design_bytes)
    h.update(b"\x00")
    h.update(layer_name.encode("utf-8"))
    return h.hexdigest()


def _publish(
    redis_client: Any,
    channel: str,
    status: str,
    progress: int,
    *,
    output_url: str | None = None,
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status, "progress": progress}
    if output_url is not None:
        payload["output_url"] = output_url
    if error is not None:
        payload["error"] = error
    redis_client.publish(channel, json.dumps(payload))


def _download(url: str) -> bytes:
    with httpx.Client(timeout=30.0, follow_redirects=False) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def _output_url_for(sha: str, file_path: Path) -> str:
    base = os.environ.get("MOCKUP_PUBLIC_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/{sha}.png"
    # Local-volume fallback — return absolute path as file URI for client consumption.
    return file_path.resolve().as_uri()


@app.task(
    bind=True,
    name="mockup.render",
)
def mockup_render_task(self: Any, request_dict: dict[str, Any]) -> dict[str, Any]:
    """Render a mockup from a PSD template + wordcloud design.

    Args:
        request_dict: Dict matching MockupRenderRequest schema.

    Returns:
        Dict with at least 'output_url' and 'task_id'.
    """
    task_id: str = self.request.id or "unknown"
    channel = f"mockup:progress:{task_id}"
    t0 = time.monotonic()

    request = MockupRenderRequest.model_validate(request_dict)

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis_lib.Redis.from_url(redis_url, decode_responses=False)

    _publish(redis_client, channel, "started", 0)

    # 1+2. Download both inputs
    _publish(redis_client, channel, "downloading", 10)
    psd_bytes = _download(request.psd_url)
    design_bytes = _download(request.design_url)

    # 3+4. Compute cache key, check Redis
    sha = _cache_key(psd_bytes, design_bytes, request.layer_name)
    cache_key = f"mockup:cache:{sha}"
    cached = redis_client.get(cache_key)
    if cached:
        cached_url = cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
        _publish(
            redis_client, channel, "success", 100, output_url=cached_url
        )
        log.info(
            "mockup_render cache hit",
            extra={"task_id": task_id, "sha": sha},
        )
        return {"task_id": task_id, "output_url": cached_url, "cached": True}

    # 5. Run MockupEngine on tempfile copies of the downloaded inputs
    _publish(redis_client, channel, "rendering", 30)
    with tempfile.TemporaryDirectory(prefix="mockup-") as tmp:
        tmp_path = Path(tmp)
        psd_path = tmp_path / "input.psd"
        design_path = tmp_path / "design.png"
        psd_path.write_bytes(psd_bytes)
        design_path.write_bytes(design_bytes)

        engine = MockupEngine()
        rendered = engine.render(psd_path, design_path, layer_name=request.layer_name)

        _publish(redis_client, channel, "compositing", 70)

        # 6. Persist output
        output_dir = Path(
            os.environ.get("MOCKUP_OUTPUT_DIR", "/var/cache/aerocloud/mockups")
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{sha}.png"
        rendered.save(output_path, format="PNG")

    output_url = _output_url_for(sha, output_path)

    # 7. Write cache (TTL 30d)
    redis_client.set(cache_key, output_url.encode("utf-8"), ex=_CACHE_TTL_SECONDS)

    # 8. Final success event
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    _publish(redis_client, channel, "success", 100, output_url=output_url)
    log.info(
        "mockup_render done",
        extra={"task_id": task_id, "sha": sha, "elapsed_ms": elapsed_ms},
    )

    return {
        "task_id": task_id,
        "output_url": output_url,
        "cached": False,
        "elapsed_ms": elapsed_ms,
    }
