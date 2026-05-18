"""Nano Banana Pro renderer — wraps the existing Modal `render_from_model_view`.

This is a thin adapter so the Spike 2.5 bake-off can treat Nano Banana Pro
uniformly alongside FLUX/Magnific/Recraft/Replicate clients. The heavy lifting
(prompt construction, geometry-preservation rules) already lives in
`spike/modal_app.py:render_from_model_view`; we just call it via
`modal.Function.lookup` so module import works without Modal CLI auth.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from spike.renderers.base import Renderer

# Modal app + function names must match `spike/modal_app.py`.
_MODAL_APP_NAME = "arch-rendering-spike"
_MODAL_FN_NAME = "render_from_model_view"


class NanoBananaProRenderer(Renderer):
    """Calls Google's Nano Banana Pro via the existing Modal function.

    Env-gated on `GOOGLE_API_KEY` because the underlying Modal function reads
    it from a Modal Secret; `compare_renderers.py` uses this to decide whether
    the renderer is live for a given run. Modal CLI auth is also required at
    call time but isn't checked here — Modal raises a clear error itself.
    """

    name: ClassVar[str] = "nano_banana_pro"
    provider: ClassVar[str] = "google"
    cost_per_call_usd: ClassVar[float] = 0.039
    env_var: ClassVar[str] = "GOOGLE_API_KEY"

    def render(
        self,
        screenshot_path: Path | str,
        prompt: str,
        *,
        seed: int | None = None,
        **kwargs,
    ) -> bytes:
        if not os.environ.get(self.env_var):
            raise RuntimeError(f"{self.env_var} not set")

        # Lazy import + lookup so module import works without modal auth.
        import modal

        path = Path(screenshot_path)
        if not path.is_file():
            raise FileNotFoundError(f"screenshot not found: {path}")
        image_bytes = path.read_bytes()

        mime_type = kwargs.pop("mime_type", "image/png")
        extra_constraints = kwargs.pop("extra_constraints", "")

        fn = modal.Function.lookup(_MODAL_APP_NAME, _MODAL_FN_NAME)
        result = fn.remote(
            image_bytes=image_bytes,
            style_prompt=prompt,
            mime_type=mime_type,
            seed=seed,
            extra_constraints=extra_constraints,
        )
        if not isinstance(result, (bytes, bytearray)):
            raise RuntimeError(
                f"render_from_model_view returned {type(result).__name__}, expected bytes"
            )
        return bytes(result)
