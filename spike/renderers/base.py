from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class Renderer(ABC):
    """Abstract base for every Spike 2.5/B3 candidate renderer.

    Subclasses implement `render()` against their provider's API. All renderers
    read credentials from environment variables at call time (not import time)
    so that this module can be imported without any keys present.
    """

    name: ClassVar[str]
    provider: ClassVar[str]
    cost_per_call_usd: ClassVar[float]
    env_var: ClassVar[str]

    @abstractmethod
    def render(
        self,
        screenshot_path: Path | str,
        prompt: str,
        *,
        seed: int | None = None,
        **kwargs,
    ) -> bytes:
        """Render `screenshot_path` per `prompt`, return PNG bytes.

        Raises:
            RuntimeError: if `cls.env_var` is not set in os.environ.
        """
        raise NotImplementedError
