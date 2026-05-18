"""Recraft V3 renderer client — Recraft native HTTP API.

`RecraftV3Renderer` calls Recraft's `imageToImage` endpoint at
`https://external.api.recraft.ai/v1/images/imageToImage`. Recraft's API is
synchronous (no polling): one POST returns either a signed URL or a
base64-encoded image. We support both response shapes.

Request shape (multipart/form-data per Recraft docs):

- `image` — the source PNG as a file field
- `prompt` — text instruction
- `strength` — 0.0–1.0 (defaults to 0.2; the bake-off driver may sweep this)
- `model` — defaults to `recraftv3`
- `style` — optional style preset (`realistic_image`, `digital_illustration`, ...)
- `response_format` — `url` (default) or `b64_json`

Header: `Authorization: Bearer <RECRAFT_API_TOKEN>`.

No network at import time. `requests` is imported lazily inside `render()`.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

_RECRAFT_BASE = "https://external.api.recraft.ai/v1"
_DEFAULT_STRENGTH = 0.2


def _read_image_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"screenshot not found: {path}")
    return path.read_bytes()


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


class RecraftV3Renderer(Renderer):
    """Recraft V3 image-to-image via the native Recraft API."""

    name: ClassVar[str] = "recraft_v3"
    provider: ClassVar[str] = "recraft"
    cost_per_call_usd: ClassVar[float] = 0.04  # Recraft V3 listed rate ~$0.04/image
    env_var: ClassVar[str] = "RECRAFT_API_TOKEN"
    endpoint_path: ClassVar[str] = "images/imageToImage"
    model_id: ClassVar[str] = "recraftv3"

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
        image_bytes = _read_image_bytes(path)

        # Recraft expects multipart/form-data with the image as a file field.
        strength = float(kwargs.get("strength", _DEFAULT_STRENGTH))
        data: dict[str, str] = {
            "prompt": prompt,
            "strength": str(strength),
            "model": self.model_id,
            "response_format": kwargs.get("response_format", "url"),
        }
        if seed is not None:
            data["random_seed"] = str(int(seed))
        for key in ("style", "substyle", "n", "negative_prompt"):
            if key in kwargs:
                data[key] = str(kwargs[key])

        files = {"image": ("screenshot.png", image_bytes, "image/png")}
        headers = {"Authorization": f"Bearer {api_key}"}
        submit_url = f"{_RECRAFT_BASE}/{self.endpoint_path}"

        resp = requests.post(
            submit_url, headers=headers, data=data, files=files, timeout=60
        )
        resp.raise_for_status()
        body = resp.json()

        items = body.get("data") or []
        if not items:
            raise RuntimeError(f"Recraft response missing data array: {body!r}")
        first = items[0]

        # Either {"url": "..."} or {"b64_json": "..."} depending on response_format.
        if "b64_json" in first and first["b64_json"]:
            return base64.b64decode(first["b64_json"])
        url = first.get("url")
        if not url:
            raise RuntimeError(f"Recraft response missing url and b64_json: {body!r}")
        return _download_bytes(url)
