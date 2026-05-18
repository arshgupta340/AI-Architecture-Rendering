"""Renderer clients for the Spike 2.5 multi-renderer bake-off.

Each renderer is a subclass of `Renderer` (see `base.py`) that takes a
screenshot + prompt and returns image bytes. All renderers are env-gated:
instantiating one is fine, but `render()` raises if the required API key is
missing. The `compare_renderers.py` driver inspects env vars to decide which
renderers are live for a given run.
"""

from spike.renderers.base import Renderer

__all__ = ["Renderer"]
