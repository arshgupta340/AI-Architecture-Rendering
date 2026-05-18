"""FLUX renderers via Black Forest Labs' BFL API.

Two endpoints, two renderer classes:

- `FluxCannyProRenderer` — `POST https://api.bfl.ml/v1/flux-pro-1.1-canny`. The
  screenshot is sent as a control image; BFL extracts Canny edges server-side
  and conditions generation on them. This is the geometry-preserving variant
  we expect to score well on `silhouette_iou` and `edge_density_delta` in the
  bake-off.
- `FluxKontextProRenderer` — `POST https://api.bfl.ml/v1/flux-pro-1.1-kontext`.
  Edit-style endpoint that takes an input image plus a text instruction; less
  geometry-rigid than Canny but better at semantic edits ("turn the wall into
  brick").

Both endpoints return `{"id": "...", "polling_url": "..."}`. We then poll
`https://api.bfl.ml/v1/get_result?id=<id>` until `status == "Ready"`, at which
point `result.sample` is a signed URL to the generated PNG. We GET that URL
and return the raw bytes.

No network at import time. The `requests` import is deferred to `render()`
so this module loads cleanly without `requests` on `sys.path` (it is, but the
discipline matches the rest of the package).
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

_BFL_BASE = "https://api.bfl.ml/v1"
_POLL_INTERVAL_S = 1.5
_POLL_TIMEOUT_S = 120.0


def _encode_image_b64(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"screenshot not found: {path}")
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _poll_for_result(
    poll_url: str,
    headers: dict[str, str],
    *,
    timeout_s: float = _POLL_TIMEOUT_S,
    interval_s: float = _POLL_INTERVAL_S,
) -> str:
    """Poll BFL's get_result endpoint until ready, return the signed sample URL.

    Raises RuntimeError on terminal failure states or timeout.
    """
    import requests  # lazy: keep module import cheap

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        if status == "Ready":
            sample = (body.get("result") or {}).get("sample")
            if not sample:
                raise RuntimeError(f"BFL ready but no sample URL in response: {body!r}")
            return sample
        if status in {"Error", "Failed", "Content Moderated", "Request Moderated"}:
            raise RuntimeError(f"BFL task failed: status={status!r} body={body!r}")
        # Pending / Queued / Processing → keep polling
        time.sleep(interval_s)
    raise RuntimeError(f"BFL polling timed out after {timeout_s}s for {poll_url!r}")


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


class _BflRendererBase(Renderer):
    """Shared HTTP plumbing for the two BFL FLUX endpoints."""

    env_var: ClassVar[str] = "BFL_API_KEY"
    provider: ClassVar[str] = "bfl"

    # Subclasses set these:
    endpoint_path: ClassVar[str]
    image_field: ClassVar[str]  # "control_image" for canny, "input_image" for kontext

    def _build_payload(
        self,
        image_b64: str,
        prompt: str,
        *,
        seed: int | None,
        **kwargs,
    ) -> dict:
        payload: dict = {
            "prompt": prompt,
            self.image_field: image_b64,
        }
        if seed is not None:
            payload["seed"] = int(seed)
        # Pass through any provider-specific knobs (steps, guidance, etc.).
        for key in (
            "steps",
            "guidance",
            "safety_tolerance",
            "output_format",
            "prompt_upsampling",
            "aspect_ratio",
        ):
            if key in kwargs:
                payload[key] = kwargs[key]
        return payload

    def render(
        self,
        screenshot_path: Path | str,
        prompt: str,
        *,
        seed: int | None = None,
        **kwargs,
    ) -> bytes:
        api_key = os.environ.get(self.env_var)
        if not api_key:
            raise RuntimeError(f"{self.env_var} not set")

        import requests  # lazy

        path = Path(screenshot_path)
        image_b64 = _encode_image_b64(path)
        payload = self._build_payload(image_b64, prompt, seed=seed, **kwargs)

        headers = {
            "x-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        submit_url = f"{_BFL_BASE}/{self.endpoint_path}"
        submit = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        submit.raise_for_status()
        submit_body = submit.json()
        task_id = submit_body.get("id")
        if not task_id:
            raise RuntimeError(f"BFL submit missing task id: {submit_body!r}")
        poll_url = submit_body.get("polling_url") or f"{_BFL_BASE}/get_result?id={task_id}"

        sample_url = _poll_for_result(poll_url, headers)
        return _download_bytes(sample_url)


class FluxCannyProRenderer(_BflRendererBase):
    """FLUX Pro 1.1 Canny — geometry-preserving image-to-image."""

    name: ClassVar[str] = "flux_canny_pro"
    cost_per_call_usd: ClassVar[float] = 0.05  # BFL listed price, ~$0.05/image
    endpoint_path: ClassVar[str] = "flux-pro-1.1-canny"
    image_field: ClassVar[str] = "control_image"


class FluxKontextProRenderer(_BflRendererBase):
    """FLUX Pro 1.1 Kontext — instruction-based image editing."""

    name: ClassVar[str] = "flux_kontext_pro"
    cost_per_call_usd: ClassVar[float] = 0.05  # BFL listed price, ~$0.05/image
    endpoint_path: ClassVar[str] = "flux-pro-1.1-kontext"
    image_field: ClassVar[str] = "input_image"
