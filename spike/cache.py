"""
Disk-backed cache for expensive intermediate artifacts in the Photoshop-for-
Architects pipeline. Used by the end-to-end edit driver (T19) to avoid
re-running renders, region-tagging, and segmentation calls during iterative
development.

Layout on disk:
  spike/.cache/<scope>/<key>.bin

The key is treated opaquely — callers are expected to hash their own inputs
(image bytes, prompt, model name, etc.) into a stable string. We sanitize
the key for filesystem safety but do NOT hash it ourselves; that keeps
debugging easier (you can `ls` the cache directory and see what's in it).

Pure local — no network, no Modal. The cached values are always raw bytes
so this works for PNGs, JSON-encoded responses, pickled tensors, whatever.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

# Cache root lives next to this file so the cache travels with the spike
# package and is easy to nuke (rm -rf spike/.cache).
_CACHE_ROOT = Path(__file__).resolve().parent / ".cache"

# Keys can be anything; we only allow a conservative filename charset on disk
# so Windows + POSIX both behave. Everything else collapses to '_'.
_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_key(key: str) -> str:
    if not key:
        raise ValueError("cache key must be a non-empty string")
    cleaned = _SAFE_KEY_RE.sub("_", key)
    # Filesystems generally cap at 255 chars; leave room for ".bin".
    return cleaned[:240]


def _scope_dir(scope: str) -> Path:
    if not scope:
        raise ValueError("cache scope must be a non-empty string")
    safe = _SAFE_KEY_RE.sub("_", scope)
    d = _CACHE_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(key: str, scope: str = "default") -> Path:
    """Return the on-disk path where this (scope, key) would be stored."""
    return _scope_dir(scope) / f"{_safe_key(key)}.bin"


def get_or_compute(
    key: str,
    fn: Callable[[], bytes],
    scope: str = "default",
) -> bytes:
    """
    Return cached bytes for (scope, key) if present; otherwise call fn(),
    persist its result, and return it.

    fn() must return bytes. If it returns anything else we raise — silent
    type coercion here would hide bugs in the pipeline.
    """
    path = cache_path(key, scope)
    if path.exists():
        return path.read_bytes()

    value = fn()
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(
            f"cache fn() for scope={scope!r} key={key!r} must return bytes; "
            f"got {type(value).__name__}"
        )

    # Write atomically: write to .tmp then rename so a crashed run never
    # leaves a half-written cache entry that looks valid on the next call.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(bytes(value))
    tmp.replace(path)
    return bytes(value)
