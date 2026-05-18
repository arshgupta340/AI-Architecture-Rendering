"""Magnific renderer client — Relight / Mystic endpoint.

`MagnificMysticRenderer` posts a screenshot + text prompt to Magnific's
Mystic image-generation API (also referred to as Relight when conditioning
on an input image). Magnific's public API is a submit-then-poll flow very
similar to BFL's:

1. `POST https://api.magnific.ai/v1/mystic` with JSON body
   `{"image": <base64 png>, "prompt": "...", "seed"?: int, ...}` and header
   `Authorization: Bearer <MAGNIFIC_API_KEY>`. Returns `{"id": "...",
   "status": "queued"}`.
2. `GET https://api.magnific.ai/v1/mystic/<id>` until `status == "succeeded"`
   at which point `output[0]` is a signed URL to the generated PNG.
3. GET that URL and return the raw bytes.

No network at import time. Module load only depends on stdlib + the local
`Renderer` base class.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

_MAGNIFIC_BASE = "https://api.magnific.ai/v1"
_POLL_INTERVAL_S = 2.0
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
    """Poll Magnific until succeeded, return the signed output URL."""
    import requests  # lazy

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        if status == "succeeded":
            output = body.get("output") or []
            if not output:
                raise RuntimeError(
                    f"Magnific succeeded but no output URL in response: {body!r}"
                )
            # Magnific returns either a list of URLs or a single URL string.
            first = output[0] if isinstance(output, list) else output
            if not first:
                raise RuntimeError(
                    f"Magnific succeeded but empty output URL: {body!r}"
                )
            return first
        if status in {"failed", "canceled", "error"}:
            raise RuntimeError(f"Magnific task failed: status={status!r} body={body!r}")
        # queued / processing → keep polling
        time.sleep(interval_s)
    raise RuntimeError(f"Magnific polling timed out after {timeout_s}s for {poll_url!r}")


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


class MagnificMysticRenderer(Renderer):
    """Magnific Mystic — image-conditioned generation / relight."""

    name: ClassVar[str] = "magnific_mystic"
    provider: ClassVar[str] = "magnific"
    cost_per_call_usd: ClassVar[float] = 0.10  # Magnific listed Mystic rate ~$0.10/image
    env_var: ClassVar[str] = "MAGNIFIC_API_KEY"
    endpoint_path: ClassVar[str] = "mystic"

    def _build_payload(
        self,
        image_b64: str,
        prompt: str,
        *,
        seed: int | None,
        **kwargs,
    ) -> dict:
        payload: dict = {
            "image": image_b64,
            "prompt": prompt,
        }
        if seed is not None:
            payload["seed"] = int(seed)
        # Provider-specific knobs pass through when present.
        for key in (
            "creativity",
            "hdr",
            "resemblance",
            "fractality",
            "engine",
            "style",
            "output_format",
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        submit_url = f"{_MAGNIFIC_BASE}/{self.endpoint_path}"
        submit = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        submit.raise_for_status()
        submit_body = submit.json()
        task_id = submit_body.get("id")
        if not task_id:
            raise RuntimeError(f"Magnific submit missing task id: {submit_body!r}")
        poll_url = (
            submit_body.get("poll_url")
            or submit_body.get("status_url")
            or f"{_MAGNIFIC_BASE}/{self.endpoint_path}/{task_id}"
        )

        sample_url = _poll_for_result(poll_url, headers)
        return _download_bytes(sample_url)
