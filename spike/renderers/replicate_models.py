"""Replicate-hosted renderers for the Spike 2.5 bake-off.

Three image-to-image models accessed via Replicate's HTTP API:

- `QwenImageEditRenderer` — `qwen/qwen-image-edit` (instruction-based edit,
  diffusion variant of Qwen-VL with strong layout preservation).
- `HiDreamE1Renderer` — `prunaai/hidream-e1` (HiDream-E1 instruction-edit
  model, geometry-friendly).
- `RecraftV3ReplicateRenderer` — `recraft-ai/recraft-v3` exposed through
  Replicate (parallel path to the native Recraft client in `recraft.py`).

Replicate's API is a submit-then-poll flow:

1. `POST https://api.replicate.com/v1/models/<owner>/<name>/predictions` with
   `{"input": {...}}` (or `/v1/predictions` with `{"version": "<hash>"}`),
   header `Authorization: Token <REPLICATE_API_TOKEN>`. Returns
   `{"id": "...", "status": "starting", "urls": {"get": "..."}}`.
2. `GET urls.get` until `status == "succeeded"`. `output` is either a single
   URL string or a list of URL strings depending on the model.
3. GET the first output URL and return the raw image bytes.

No network at import time. `requests` is imported lazily inside `render()`
so the module loads cleanly when the package is missing.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, ClassVar

from spike.renderers.base import Renderer

_REPLICATE_BASE = "https://api.replicate.com/v1"
_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 180.0


def _read_image_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"screenshot not found: {path}")
    return path.read_bytes()


def _encode_image_data_url(path: Path) -> str:
    """Replicate accepts image inputs as either an HTTPS URL or a
    `data:image/png;base64,<...>` data URL. We use the latter so the caller
    doesn't have to upload anywhere first.
    """
    raw = _read_image_bytes(path)
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _poll_for_result(
    poll_url: str,
    headers: dict[str, str],
    *,
    timeout_s: float = _POLL_TIMEOUT_S,
    interval_s: float = _POLL_INTERVAL_S,
) -> Any:
    """Poll a Replicate prediction until terminal, return the `output` field."""
    import requests  # lazy

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = requests.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        if status == "succeeded":
            output = body.get("output")
            if output is None:
                raise RuntimeError(
                    f"Replicate succeeded but no output in response: {body!r}"
                )
            return output
        if status in {"failed", "canceled"}:
            raise RuntimeError(
                f"Replicate task {status}: error={body.get('error')!r} body={body!r}"
            )
        # starting / processing → keep polling
        time.sleep(interval_s)
    raise RuntimeError(
        f"Replicate polling timed out after {timeout_s}s for {poll_url!r}"
    )


def _download_bytes(url: str) -> bytes:
    import requests

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _first_output_url(output: Any) -> str:
    """Replicate `output` is either a string URL or a list of string URLs."""
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
    raise RuntimeError(f"Replicate output not a URL or list of URLs: {output!r}")


class _ReplicateRendererBase(Renderer):
    """Shared HTTP plumbing for Replicate-hosted image-to-image models."""

    env_var: ClassVar[str] = "REPLICATE_API_TOKEN"
    provider: ClassVar[str] = "replicate"

    # Subclasses set these:
    model_owner: ClassVar[str]
    model_name: ClassVar[str]
    image_field: ClassVar[str] = "image"  # input key for the source image
    prompt_field: ClassVar[str] = "prompt"
    # Optional version pin. If None, we hit `/v1/models/<owner>/<name>/predictions`
    # which uses the model's default version server-side. If set, we hit
    # `/v1/predictions` with `{"version": <hash>}`.
    model_version: ClassVar[str | None] = None
    # Extra knobs that pass through from `**kwargs` into the `input` block.
    passthrough_keys: ClassVar[tuple[str, ...]] = ()

    def _build_input(
        self,
        image_data_url: str,
        prompt: str,
        *,
        seed: int | None,
        **kwargs,
    ) -> dict:
        payload: dict = {
            self.image_field: image_data_url,
            self.prompt_field: prompt,
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
        image_data_url = _encode_image_data_url(path)
        input_block = self._build_input(image_data_url, prompt, seed=seed, **kwargs)

        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.model_version is not None:
            submit_url = f"{_REPLICATE_BASE}/predictions"
            body = {"version": self.model_version, "input": input_block}
        else:
            submit_url = (
                f"{_REPLICATE_BASE}/models/{self.model_owner}/{self.model_name}/predictions"
            )
            body = {"input": input_block}

        submit = requests.post(submit_url, json=body, headers=headers, timeout=30)
        submit.raise_for_status()
        submit_body = submit.json()
        poll_url = (submit_body.get("urls") or {}).get("get")
        if not poll_url:
            pred_id = submit_body.get("id")
            if not pred_id:
                raise RuntimeError(
                    f"Replicate submit missing prediction id and poll url: {submit_body!r}"
                )
            poll_url = f"{_REPLICATE_BASE}/predictions/{pred_id}"

        output = _poll_for_result(poll_url, headers)
        url = _first_output_url(output)
        return _download_bytes(url)


class QwenImageEditRenderer(_ReplicateRendererBase):
    """Qwen-Image-Edit on Replicate — instruction-based image edit."""

    name: ClassVar[str] = "qwen_image_edit"
    cost_per_call_usd: ClassVar[float] = 0.03  # Replicate listed rate, approximate
    model_owner: ClassVar[str] = "qwen"
    model_name: ClassVar[str] = "qwen-image-edit"
    image_field: ClassVar[str] = "image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "negative_prompt",
        "num_inference_steps",
        "guidance_scale",
        "output_format",
        "output_quality",
        "aspect_ratio",
    )


class HiDreamE1Renderer(_ReplicateRendererBase):
    """HiDream-E1 on Replicate — instruction-edit diffusion model."""

    name: ClassVar[str] = "hidream_e1"
    cost_per_call_usd: ClassVar[float] = 0.04  # Replicate listed rate, approximate
    model_owner: ClassVar[str] = "prunaai"
    model_name: ClassVar[str] = "hidream-e1"
    image_field: ClassVar[str] = "image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "negative_prompt",
        "num_inference_steps",
        "guidance_scale",
        "image_guidance_scale",
        "output_format",
        "output_quality",
    )


class RecraftV3ReplicateRenderer(_ReplicateRendererBase):
    """Recraft V3 on Replicate — same model as `recraft.py` but via Replicate."""

    name: ClassVar[str] = "recraft_v3_replicate"
    cost_per_call_usd: ClassVar[float] = 0.04  # Recraft V3 listed rate ~$0.04/image
    model_owner: ClassVar[str] = "recraft-ai"
    model_name: ClassVar[str] = "recraft-v3"
    # Recraft on Replicate is text-to-image; the screenshot is conditioning
    # only in style-reference mode. We still send it via `image` and let
    # callers override with kwargs if they need pure text-to-image.
    image_field: ClassVar[str] = "image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "style",
        "substyle",
        "size",
        "negative_prompt",
        "output_format",
    )
