"""Replicate-hosted renderers for the Spike 2.5 bake-off.

All FLUX variants + Qwen + HiDream route through Replicate. Consolidating
behind one auth path (`REPLICATE_API_TOKEN`) simplifies billing — top up
one account and every Replicate-hosted renderer in the field becomes live.

Models in this module:

- `Flux2ProRenderer` — `black-forest-labs/flux-2-pro`. General image-edit;
  accepts an `input_images` array (Replicate quirk — the field is plural and
  takes a list even when conditioning on one image). Schema: required is
  just `prompt`; image is optional but we always send it.
- `FluxFillProRenderer` — `black-forest-labs/flux-fill-pro`. Mask-based
  inpainting, fired here without a mask to characterize default behavior.
  Field: `image` (single URI), `prompt` required.
- `FluxCannyProRenderer` — `black-forest-labs/flux-canny-pro`. Server-side
  Canny edge conditioning. Field: `control_image` + `prompt` required.
- `FluxDepthProRenderer` — `black-forest-labs/flux-depth-pro`. Depth-map
  conditioning. Same schema as Canny Pro.
- `QwenImageEditRenderer` — `qwen/qwen-image-edit`. Instruction-edit.
- `HiDreamE1Renderer` — `prunaai/hidream-e1.1`. Natural-language prompt
  instruction-edit (supersedes the older `hidream-e1`).

Removed previously: `RecraftV3ReplicateRenderer` (Replicate's Recraft V3
endpoint is text-to-image only). Use `spike/renderers/recraft.py:RecraftV3Renderer`
against the native Recraft API for image-to-image.

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
    """HiDream-E1.1 on Replicate — instruction-edit diffusion model.

    Model slug uses a literal period (`hidream-e1.1`), not a hyphen.
    Replicate's metadata endpoint resolves the slug fine, but the
    `/v1/models/<owner>/<name>/predictions` path returns 404 — the period
    breaks routing for the prediction endpoint specifically. We work around
    this by using version-pinned predictions (`/v1/predictions` with the
    `version` field), which the base class enables when `model_version` is
    set.

    Version hash captured 2026-05-22 from
    https://api.replicate.com/v1/models/prunaai/hidream-e1.1 → latest_version.id.
    Re-fetch if predictions start failing — Replicate retires old versions.
    """

    name: ClassVar[str] = "hidream_e1_1"
    cost_per_call_usd: ClassVar[float] = 0.04  # Replicate listed rate, approximate
    model_owner: ClassVar[str] = "prunaai"
    model_name: ClassVar[str] = "hidream-e1.1"
    model_version: ClassVar[str] = (
        "433436facdc1172b6efcb801eb6f345d7858a32200d24e5febaccfb4b44ad66f"
    )
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


class FluxCannyProRenderer(_ReplicateRendererBase):
    """FLUX Canny Pro via Replicate — geometry preservation via server-side Canny.

    Sole hosted path after BFL's direct API dropped Canny endpoints in 2026.
    Input image lives in `control_image`; the existing base class encodes it
    as a data URL automatically.
    """

    name: ClassVar[str] = "flux_canny_pro"
    cost_per_call_usd: ClassVar[float] = 0.05
    model_owner: ClassVar[str] = "black-forest-labs"
    model_name: ClassVar[str] = "flux-canny-pro"
    image_field: ClassVar[str] = "control_image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "steps",
        "guidance",
        "output_format",
        "safety_tolerance",
        "prompt_upsampling",
    )


class FluxDepthProRenderer(_ReplicateRendererBase):
    """FLUX Depth Pro via Replicate — geometry preservation via depth conditioning.

    Same situation as Canny Pro: only available through Replicate post-2026.
    """

    name: ClassVar[str] = "flux_depth_pro"
    cost_per_call_usd: ClassVar[float] = 0.05
    model_owner: ClassVar[str] = "black-forest-labs"
    model_name: ClassVar[str] = "flux-depth-pro"
    image_field: ClassVar[str] = "control_image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "steps",
        "guidance",
        "output_format",
        "safety_tolerance",
        "prompt_upsampling",
    )


class FluxFillProRenderer(_ReplicateRendererBase):
    """FLUX Fill Pro via Replicate — mask-based inpainting, fired with no mask.

    Replicate's schema makes `image` and `prompt` the only required fields;
    `mask` is optional. Routed through Replicate for billing consolidation
    (BFL direct also offers this endpoint but at separate auth).
    """

    name: ClassVar[str] = "flux_fill_pro"
    cost_per_call_usd: ClassVar[float] = 0.05
    model_owner: ClassVar[str] = "black-forest-labs"
    model_name: ClassVar[str] = "flux-fill-pro"
    image_field: ClassVar[str] = "image"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "mask",
        "steps",
        "guidance",
        "outpaint",
        "output_format",
        "safety_tolerance",
        "prompt_upsampling",
    )


class Flux2ProRenderer(_ReplicateRendererBase):
    """FLUX 2 Pro via Replicate — general image-edit.

    Replicate's flux-2-pro accepts a plural `input_images` ARRAY (max 8)
    rather than a single image field, so this subclass overrides
    `_build_input` to wrap the encoded data URL in a list. All other
    request/response handling is inherited from the base.
    """

    name: ClassVar[str] = "flux_2_pro"
    cost_per_call_usd: ClassVar[float] = 0.03
    model_owner: ClassVar[str] = "black-forest-labs"
    model_name: ClassVar[str] = "flux-2-pro"
    # image_field is bypassed for this renderer; we use input_images (array).
    image_field: ClassVar[str] = "input_images"
    prompt_field: ClassVar[str] = "prompt"
    passthrough_keys: ClassVar[tuple[str, ...]] = (
        "width",
        "height",
        "aspect_ratio",
        "resolution",
        "output_format",
        "output_quality",
        "safety_tolerance",
    )

    def _build_input(
        self,
        image_data_url: str,
        prompt: str,
        *,
        seed: int | None,
        **kwargs,
    ) -> dict:
        payload: dict = {
            self.prompt_field: prompt,
            self.image_field: [image_data_url],
        }
        if seed is not None:
            payload["seed"] = int(seed)
        for key in self.passthrough_keys:
            if key in kwargs:
                payload[key] = kwargs[key]
        return payload
