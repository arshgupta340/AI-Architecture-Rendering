"""Magnific Mystic renderer client.

`MagnificMysticRenderer` posts a screenshot + text prompt to Magnific's
Mystic image-generation API. Per the May 2026 docs (Freepik-owned Magnific):

1. `POST https://api.magnific.com/v1/ai/mystic` with JSON body
   `{"prompt": "...", "structure_reference": "<base64 png>", ...}` and header
   `x-magnific-api-key: <MAGNIFIC_API_KEY>`. Returns
   `{"data": {"task_id": "<uuid>", "status": "CREATED", "generated": []}}`.
2. `GET https://api.magnific.com/v1/ai/mystic/<task_id>` until
   `data.status == "COMPLETED"`. `data.generated[0]` is then a signed URL.
3. GET that URL and return the raw bytes.

The screenshot is sent in `structure_reference` (shape-conditioning input);
we do not populate `style_reference`. References are base64 strings only —
the docs explicitly do not accept URLs.

No network at import time. Module load depends only on stdlib + base class.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

_MAGNIFIC_BASE = "https://api.magnific.com/v1"
_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 240.0


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
    """Poll Magnific until COMPLETED, return the first generated URL."""
    import requests  # lazy

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data") or {}
        status = data.get("status")
        if status == "COMPLETED":
            generated = data.get("generated") or []
            if not generated:
                raise RuntimeError(
                    f"Magnific COMPLETED but no generated URLs: {body!r}"
                )
            first = generated[0] if isinstance(generated, list) else generated
            if not first:
                raise RuntimeError(f"Magnific COMPLETED but empty URL: {body!r}")
            return first
        if status in {"FAILED", "CANCELED"}:
            raise RuntimeError(f"Magnific task failed: status={status!r} body={body!r}")
        time.sleep(interval_s)
    raise RuntimeError(f"Magnific polling timed out after {timeout_s}s for {poll_url!r}")


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


class MagnificMysticRenderer(Renderer):
    """Magnific Mystic — image-conditioned generation via structure_reference."""

    name: ClassVar[str] = "magnific_mystic"
    provider: ClassVar[str] = "magnific"
    cost_per_call_usd: ClassVar[float] = 0.10
    env_var: ClassVar[str] = "MAGNIFIC_API_KEY"
    endpoint_path: ClassVar[str] = "ai/mystic"

    # Magnific does not accept a `seed` field — reproducibility is via
    # `fixed_generation: true` instead. We translate seed=<any int> into
    # fixed_generation=True so callers can use the same kwarg shape as other
    # renderers; the seed value itself is discarded.

    def _build_payload(
        self,
        structure_reference_b64: str,
        prompt: str,
        *,
        seed: int | None,
        **kwargs,
    ) -> dict:
        payload: dict = {
            "prompt": prompt,
            "structure_reference": structure_reference_b64,
        }
        if seed is not None:
            payload["fixed_generation"] = True
        for key in (
            "structure_strength",
            "style_reference",
            "adherence",
            "hdr",
            "resolution",
            "aspect_ratio",
            "model",
            "creative_detailing",
            "engine",
            "filter_nsfw",
            "styling",
            "webhook_url",
            "fixed_generation",
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
        structure_b64 = _encode_image_b64(path)
        payload = self._build_payload(structure_b64, prompt, seed=seed, **kwargs)

        headers = {
            "x-magnific-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        submit_url = f"{_MAGNIFIC_BASE}/{self.endpoint_path}"
        submit = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        submit.raise_for_status()
        submit_body = submit.json()
        data = submit_body.get("data") or {}
        task_id = data.get("task_id") or submit_body.get("task_id") or submit_body.get("id")
        if not task_id:
            raise RuntimeError(f"Magnific submit missing task_id: {submit_body!r}")
        poll_url = f"{_MAGNIFIC_BASE}/{self.endpoint_path}/{task_id}"

        sample_url = _poll_for_result(poll_url, headers)
        return _download_bytes(sample_url)
