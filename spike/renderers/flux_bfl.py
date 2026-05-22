"""FLUX renderers via Black Forest Labs' BFL API.

As of the May 2026 docs rev, BFL's older Canny / Kontext Pro endpoints are
deprecated and the canonical image-edit path is FLUX 2 Pro. We expose two
renderer classes:

- `Flux2ProRenderer` — `POST https://api.bfl.ai/v1/flux-2-pro`. General
  image-edit; takes an `input_image` (base64) plus a `prompt` and produces a
  re-rendered image. Replaces the legacy Kontext Pro / Canny Pro entries that
  used to live here.
- `FluxFillProRenderer` — `POST https://api.bfl.ai/v1/flux-pro-1.0-fill`.
  Mask-based inpainting endpoint. B3 does not have a mask flow, so this
  renderer is fired with image + prompt only and no `mask` field. BFL's
  behavior on an absent `mask` is undocumented — included in the bake-off
  per explicit user request to see what it produces.

Both endpoints use a submit-then-poll flow. Submit response includes a
`polling_url` we GET repeatedly until status `"Ready"`; the result PNG lives
at `result.sample` (convention preserved from the older `get_result`
endpoint, which both new endpoints still route through).

No network at import time. `requests` is lazy-imported inside `render()`.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

_BFL_BASE = "https://api.bfl.ai/v1"
_POLL_INTERVAL_S = 1.5
_POLL_TIMEOUT_S = 180.0


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
    """Poll BFL until ready, return the signed sample URL."""
    import requests  # lazy

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
        if status in {"Error", "Failed", "Content Moderated", "Request Moderated", "Task not found"}:
            raise RuntimeError(f"BFL task failed: status={status!r} body={body!r}")
        time.sleep(interval_s)
    raise RuntimeError(f"BFL polling timed out after {timeout_s}s for {poll_url!r}")


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


class _BflRendererBase(Renderer):
    """Shared HTTP plumbing for BFL endpoints (submit-then-poll)."""

    env_var: ClassVar[str] = "BFL_API_KEY"
    provider: ClassVar[str] = "bfl"

    endpoint_path: ClassVar[str]
    image_field: ClassVar[str]

    # Subset of provider knobs that can pass through from **kwargs. Each
    # subclass overrides this to whitelist its own legal fields.
    passthrough_keys: ClassVar[tuple[str, ...]] = ()

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
        for key in self.passthrough_keys:
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
        poll_url = submit_body.get("polling_url")
        if not poll_url:
            if not task_id:
                raise RuntimeError(
                    f"BFL submit missing both id and polling_url: {submit_body!r}"
                )
            poll_url = f"{_BFL_BASE}/get_result?id={task_id}"

        sample_url = _poll_for_result(poll_url, headers)
        return _download_bytes(sample_url)


class Flux2ProRenderer(_BflRendererBase):
    """FLUX 2 Pro — general image-edit. Replaces the legacy Kontext Pro path."""

    name: ClassVar[str] = "flux_2_pro"
    cost_per_call_usd: ClassVar[float] = 0.03
    endpoint_path: ClassVar[str] = "flux-2-pro"
    image_field: ClassVar[str] = "input_image"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "width",
        "height",
        "safety_tolerance",
        "output_format",
    )


class FluxFillProRenderer(_BflRendererBase):
    """FLUX Fill Pro — mask-based inpainting endpoint, fired with no mask.

    BFL's docs declare `mask` optional; behavior on omission is undocumented.
    Included in the B3 bake-off at user request to characterize what the
    endpoint produces in this configuration.
    """

    name: ClassVar[str] = "flux_fill_pro"
    cost_per_call_usd: ClassVar[float] = 0.05
    endpoint_path: ClassVar[str] = "flux-pro-1.0-fill"
    image_field: ClassVar[str] = "image"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "mask",
        "steps",
        "prompt_upsampling",
        "guidance",
        "output_format",
        "safety_tolerance",
    )
