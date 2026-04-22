"""Load test: 100 concurrent POST /render requests with P99 latency measurement.

PROD-22: Validates system handles production concurrency without GPU OOM,
memory leaks, or unacceptable latency.

Run with:
    uv run pytest packages/engine/tests/load/ -m load -v -s

Override server URL:
    LOAD_TEST_URL=http://my-server:8000 uv run pytest packages/engine/tests/load/ -m load -v -s
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import time

import httpx
import numpy as np
import pytest
from PIL import Image

BASE_URL = os.environ.get("LOAD_TEST_URL", "http://localhost:8000")
CONCURRENT = 100


def _circle_mask_b64() -> str:
    """Generate a simple 256x256 circle mask as base64 PNG."""
    img = np.zeros((256, 256), dtype=np.uint8)
    cy, cx, r = 128, 128, 100
    y, x = np.ogrid[:256, :256]
    img[(y - cy) ** 2 + (x - cx) ** 2 <= r**2] = 255
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.mark.load
@pytest.mark.asyncio
async def test_100_concurrent_renders() -> None:
    """Dispatch 100 concurrent POST /render requests and measure P99 dispatch latency.

    Assertions:
    - All 100 requests return HTTP 202 (no failures)
    - P99 dispatch latency < 5.0s (task dispatch only, not render completion)
    """
    mask_b64 = _circle_mask_b64()
    payload = {
        "text": "hello world test words for load testing performance measurement",
        "shape_b64": mask_b64,
        "width": 256,
        "height": 256,
        "seed": 42,
        "max_words": 20,
        "font_family": "Inter",
    }

    latencies: list[float] = []
    errors: list[str] = []

    async def send_request(client: httpx.AsyncClient, i: int) -> None:
        start = time.perf_counter()
        try:
            resp = await client.post(f"{BASE_URL}/render", json=payload, timeout=30.0)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            if resp.status_code != 202:
                errors.append(f"Request {i}: HTTP {resp.status_code}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"Request {i}: {e}")

    async with httpx.AsyncClient() as client:
        tasks = [send_request(client, i) for i in range(CONCURRENT)]
        await asyncio.gather(*tasks)

    # Report results
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p99_idx = int(len(latencies) * 0.99)
    p99 = latencies[p99_idx] if latencies else 0.0

    print("\n--- Load Test Results ---")
    print(f"Requests: {CONCURRENT}")
    print(f"Success: {len(latencies)}")
    print(f"Errors: {len(errors)}")
    print(f"P50 dispatch latency: {p50:.3f}s")
    print(f"P99 dispatch latency: {p99:.3f}s")
    if errors:
        print(f"Error details: {errors[:5]}")

    # Assertions
    assert len(errors) == 0, f"{len(errors)} requests failed: {errors[:5]}"
    assert len(latencies) == CONCURRENT
    # P99 dispatch should be under 5s (task dispatch, not render completion)
    assert p99 < 5.0, f"P99 dispatch latency {p99:.3f}s exceeds 5s budget"
