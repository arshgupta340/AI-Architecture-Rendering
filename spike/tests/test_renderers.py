"""Renderer-client tests.

Every renderer subclass is covered for:

1. env-var missing -> clean RuntimeError
2. request shape (URL, headers, body fields) matches provider docs
3. response parsing returns bytes
4. HTTP error -> propagates as an exception

The renderer modules use `requests` (lazy-imported inside `render()`) rather
than `httpx`, so `respx` (which only patches `httpx`) is not applicable here.
We mock `requests.post` / `requests.get` directly via `unittest.mock.patch`
on the module under test. This is the same coverage shape `respx` would give
us — assert on submitted URL + body, return fake responses — just expressed
against the actual transport library.

NanoBananaProRenderer does not hit HTTP at all; it calls a Modal Function via
`modal.Function.from_name`. We monkeypatch that and `modal` module-level access.
"""

from __future__ import annotations

import base64
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spike.renderers.flux_bfl import FluxCannyProRenderer, FluxKontextProRenderer
from spike.renderers.magnific import MagnificMysticRenderer
from spike.renderers.nano_banana import NanoBananaProRenderer
from spike.renderers.recraft import RecraftV3Renderer
from spike.renderers.replicate_models import (
    HiDreamE1Renderer,
    QwenImageEditRenderer,
    RecraftV3ReplicateRenderer,
)


# --------------------------------------------------------------------------- #
# Small helpers                                                               #
# --------------------------------------------------------------------------- #


def _fake_response(
    *,
    status_code: int = 200,
    json_body: dict | None = None,
    content: bytes | None = None,
) -> MagicMock:
    """Build a `requests.Response`-shaped mock."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.content = content if content is not None else b""

    if status_code >= 400:
        import requests as _requests

        err = _requests.HTTPError(f"{status_code} error")
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.return_value = None

    return resp


# --------------------------------------------------------------------------- #
# FLUX BFL — Canny + Kontext                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "renderer_cls,expected_endpoint,expected_image_field",
    [
        (FluxCannyProRenderer, "flux-pro-1.1-canny", "control_image"),
        (FluxKontextProRenderer, "flux-pro-1.1-kontext", "input_image"),
    ],
)
def test_flux_missing_env_raises(
    renderer_cls, expected_endpoint, expected_image_field, tiny_png, monkeypatch
):
    monkeypatch.delenv("BFL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BFL_API_KEY not set"):
        renderer_cls().render(tiny_png, "a cozy living room")


@pytest.mark.parametrize(
    "renderer_cls,expected_endpoint,expected_image_field",
    [
        (FluxCannyProRenderer, "flux-pro-1.1-canny", "control_image"),
        (FluxKontextProRenderer, "flux-pro-1.1-kontext", "input_image"),
    ],
)
def test_flux_request_shape_and_response(
    renderer_cls,
    expected_endpoint,
    expected_image_field,
    tiny_png,
    tiny_png_bytes,
    another_tiny_png,
    monkeypatch,
):
    monkeypatch.setenv("BFL_API_KEY", "test-key")

    submit_resp = _fake_response(
        json_body={
            "id": "task-123",
            "polling_url": "https://api.bfl.ml/v1/get_result?id=task-123",
        }
    )
    pending_resp = _fake_response(json_body={"status": "Processing"})
    ready_resp = _fake_response(
        json_body={
            "status": "Ready",
            "result": {"sample": "https://signed.example/out.png"},
        }
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    # Two polls: first pending, second ready, then a download GET.
    fake_requests.get.side_effect = [pending_resp, ready_resp, download_resp]

    # Patch sleep so the polling loop is instant.
    monkeypatch.setattr("spike.renderers.flux_bfl.time.sleep", lambda *_: None)

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = renderer_cls().render(tiny_png, "studio render", seed=42, steps=30)

    assert out == another_tiny_png

    # Submit URL + headers + body shape
    assert fake_requests.post.call_count == 1
    submit_args, submit_kwargs = fake_requests.post.call_args
    assert submit_args[0] == f"https://api.bfl.ml/v1/{expected_endpoint}"
    headers = submit_kwargs["headers"]
    assert headers["x-key"] == "test-key"
    assert headers["Content-Type"] == "application/json"

    payload = submit_kwargs["json"]
    assert payload["prompt"] == "studio render"
    assert payload["seed"] == 42
    assert payload["steps"] == 30
    # The image field must be base64-encoded image bytes
    assert payload[expected_image_field] == base64.b64encode(tiny_png_bytes).decode("ascii")

    # First poll URL came from the submit response
    first_get_url = fake_requests.get.call_args_list[0].args[0]
    assert first_get_url == "https://api.bfl.ml/v1/get_result?id=task-123"
    # Final GET was the signed sample URL
    last_get_url = fake_requests.get.call_args_list[-1].args[0]
    assert last_get_url == "https://signed.example/out.png"


def test_flux_http_error_propagates(tiny_png, monkeypatch):
    monkeypatch.setenv("BFL_API_KEY", "test-key")

    fake_requests = MagicMock()
    fake_requests.post.return_value = _fake_response(status_code=500, json_body={})

    import requests as _real_requests

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(_real_requests.HTTPError):
            FluxCannyProRenderer().render(tiny_png, "anything")


def test_flux_failure_status_raises(tiny_png, monkeypatch):
    monkeypatch.setenv("BFL_API_KEY", "test-key")
    monkeypatch.setattr("spike.renderers.flux_bfl.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={"id": "task-x", "polling_url": "https://api.bfl.ml/v1/get_result?id=task-x"}
    )
    failed_resp = _fake_response(json_body={"status": "Error"})

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.return_value = failed_resp

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(RuntimeError, match="BFL task failed"):
            FluxCannyProRenderer().render(tiny_png, "anything")


# --------------------------------------------------------------------------- #
# Magnific Mystic                                                             #
# --------------------------------------------------------------------------- #


def test_magnific_missing_env_raises(tiny_png, monkeypatch):
    monkeypatch.delenv("MAGNIFIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MAGNIFIC_API_KEY not set"):
        MagnificMysticRenderer().render(tiny_png, "warm light")


def test_magnific_request_shape_and_response(
    tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch
):
    monkeypatch.setenv("MAGNIFIC_API_KEY", "test-key")
    monkeypatch.setattr("spike.renderers.magnific.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={"id": "mg-abc", "status": "queued"}
    )
    ready_resp = _fake_response(
        json_body={
            "status": "succeeded",
            "output": ["https://signed.example/m.png"],
        }
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.side_effect = [ready_resp, download_resp]

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = MagnificMysticRenderer().render(
            tiny_png, "scandi interior", seed=7, creativity=3
        )

    assert out == another_tiny_png

    submit_args, submit_kwargs = fake_requests.post.call_args
    assert submit_args[0] == "https://api.magnific.ai/v1/mystic"
    assert submit_kwargs["headers"]["Authorization"] == "Bearer test-key"
    payload = submit_kwargs["json"]
    assert payload["prompt"] == "scandi interior"
    assert payload["seed"] == 7
    assert payload["creativity"] == 3
    assert payload["image"] == base64.b64encode(tiny_png_bytes).decode("ascii")

    # Default poll URL is /mystic/<id> since submit didn't return poll_url
    poll_url = fake_requests.get.call_args_list[0].args[0]
    assert poll_url == "https://api.magnific.ai/v1/mystic/mg-abc"


def test_magnific_http_error_propagates(tiny_png, monkeypatch):
    monkeypatch.setenv("MAGNIFIC_API_KEY", "test-key")

    fake_requests = MagicMock()
    fake_requests.post.return_value = _fake_response(status_code=401, json_body={})

    import requests as _real_requests

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(_real_requests.HTTPError):
            MagnificMysticRenderer().render(tiny_png, "x")


# --------------------------------------------------------------------------- #
# Recraft V3 (native)                                                         #
# --------------------------------------------------------------------------- #


def test_recraft_missing_env_raises(tiny_png, monkeypatch):
    monkeypatch.delenv("RECRAFT_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="RECRAFT_API_TOKEN not set"):
        RecraftV3Renderer().render(tiny_png, "wood facade")


def test_recraft_request_shape_url_response(
    tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch
):
    monkeypatch.setenv("RECRAFT_API_TOKEN", "test-token")

    submit_resp = _fake_response(
        json_body={"data": [{"url": "https://signed.example/r.png"}]}
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.return_value = download_resp

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = RecraftV3Renderer().render(
            tiny_png, "wood facade", seed=12, style="realistic_image"
        )

    assert out == another_tiny_png

    submit_args, submit_kwargs = fake_requests.post.call_args
    assert submit_args[0] == "https://external.api.recraft.ai/v1/images/imageToImage"
    assert submit_kwargs["headers"]["Authorization"] == "Bearer test-token"
    data = submit_kwargs["data"]
    assert data["prompt"] == "wood facade"
    assert data["model"] == "recraftv3"
    assert data["random_seed"] == "12"
    assert data["style"] == "realistic_image"
    # The image file field must contain the screenshot bytes
    files = submit_kwargs["files"]
    assert files["image"][1] == tiny_png_bytes
    assert files["image"][2] == "image/png"


def test_recraft_b64_response_decoded(tiny_png, another_tiny_png, monkeypatch):
    monkeypatch.setenv("RECRAFT_API_TOKEN", "test-token")

    b64 = base64.b64encode(another_tiny_png).decode("ascii")
    submit_resp = _fake_response(json_body={"data": [{"b64_json": b64}]})

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = RecraftV3Renderer().render(
            tiny_png, "x", response_format="b64_json"
        )

    assert out == another_tiny_png
    # No download GET should be needed in b64 mode
    fake_requests.get.assert_not_called()


def test_recraft_http_error_propagates(tiny_png, monkeypatch):
    monkeypatch.setenv("RECRAFT_API_TOKEN", "test-token")

    fake_requests = MagicMock()
    fake_requests.post.return_value = _fake_response(status_code=403, json_body={})

    import requests as _real_requests

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(_real_requests.HTTPError):
            RecraftV3Renderer().render(tiny_png, "x")


# --------------------------------------------------------------------------- #
# Replicate-hosted models                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "renderer_cls,owner,name",
    [
        (QwenImageEditRenderer, "qwen", "qwen-image-edit"),
        (HiDreamE1Renderer, "prunaai", "hidream-e1"),
        (RecraftV3ReplicateRenderer, "recraft-ai", "recraft-v3"),
    ],
)
def test_replicate_missing_env_raises(renderer_cls, owner, name, tiny_png, monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="REPLICATE_API_TOKEN not set"):
        renderer_cls().render(tiny_png, "anything")


@pytest.mark.parametrize(
    "renderer_cls,owner,name",
    [
        (QwenImageEditRenderer, "qwen", "qwen-image-edit"),
        (HiDreamE1Renderer, "prunaai", "hidream-e1"),
        (RecraftV3ReplicateRenderer, "recraft-ai", "recraft-v3"),
    ],
)
def test_replicate_request_shape_and_response(
    renderer_cls, owner, name, tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch
):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr("spike.renderers.replicate_models.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={
            "id": "pred-1",
            "status": "starting",
            "urls": {"get": "https://api.replicate.com/v1/predictions/pred-1"},
        }
    )
    pending_resp = _fake_response(json_body={"status": "processing"})
    ready_resp = _fake_response(
        json_body={
            "status": "succeeded",
            "output": ["https://signed.example/rep.png"],
        }
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.side_effect = [pending_resp, ready_resp, download_resp]

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = renderer_cls().render(tiny_png, "soft daylight", seed=99)

    assert out == another_tiny_png

    submit_args, submit_kwargs = fake_requests.post.call_args
    expected_submit_url = (
        f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
    )
    assert submit_args[0] == expected_submit_url
    assert submit_kwargs["headers"]["Authorization"] == "Token test-token"

    body = submit_kwargs["json"]
    assert "input" in body
    input_block = body["input"]
    assert input_block["prompt"] == "soft daylight"
    assert input_block["seed"] == 99
    # Image is a data URL
    assert isinstance(input_block["image"], str)
    assert input_block["image"].startswith("data:image/png;base64,")
    encoded = input_block["image"].split(",", 1)[1]
    assert base64.b64decode(encoded) == tiny_png_bytes

    # Poll URL came from submit's urls.get
    first_get_url = fake_requests.get.call_args_list[0].args[0]
    assert first_get_url == "https://api.replicate.com/v1/predictions/pred-1"


def test_replicate_string_output_parsed(
    tiny_png, another_tiny_png, monkeypatch
):
    """Replicate sometimes returns `output` as a plain URL string instead of a list."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr("spike.renderers.replicate_models.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={
            "id": "pred-2",
            "urls": {"get": "https://api.replicate.com/v1/predictions/pred-2"},
        }
    )
    ready_resp = _fake_response(
        json_body={
            "status": "succeeded",
            "output": "https://signed.example/just-a-string.png",
        }
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.side_effect = [ready_resp, download_resp]

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = QwenImageEditRenderer().render(tiny_png, "x")

    assert out == another_tiny_png


def test_replicate_http_error_propagates(tiny_png, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")

    fake_requests = MagicMock()
    fake_requests.post.return_value = _fake_response(status_code=429, json_body={})

    import requests as _real_requests

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(_real_requests.HTTPError):
            QwenImageEditRenderer().render(tiny_png, "x")


def test_replicate_failed_status_raises(tiny_png, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr("spike.renderers.replicate_models.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={
            "id": "pred-3",
            "urls": {"get": "https://api.replicate.com/v1/predictions/pred-3"},
        }
    )
    failed_resp = _fake_response(
        json_body={"status": "failed", "error": "oom"}
    )

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.return_value = failed_resp

    with patch.dict(sys.modules, {"requests": fake_requests}):
        with pytest.raises(RuntimeError, match="Replicate task failed"):
            QwenImageEditRenderer().render(tiny_png, "x")


# --------------------------------------------------------------------------- #
# Nano Banana Pro (Modal-backed, not HTTP)                                    #
# --------------------------------------------------------------------------- #


def test_nano_banana_missing_env_raises(tiny_png, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY not set"):
        NanoBananaProRenderer().render(tiny_png, "x")


def test_nano_banana_calls_modal_lookup_and_returns_bytes(
    tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch
):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    fake_fn = MagicMock()
    fake_fn.remote.return_value = another_tiny_png

    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(return_value=fake_fn)

    with patch.dict(sys.modules, {"modal": fake_modal}):
        out = NanoBananaProRenderer().render(
            tiny_png, "studio render", seed=5, extra_constraints="preserve windows"
        )

    assert out == another_tiny_png
    fake_modal.Function.from_name.assert_called_once_with(
        "arch-rendering-spike", "render_from_model_view"
    )
    fake_fn.remote.assert_called_once()
    call_kwargs = fake_fn.remote.call_args.kwargs
    assert call_kwargs["image_bytes"] == tiny_png_bytes
    assert call_kwargs["style_prompt"] == "studio render"
    assert call_kwargs["seed"] == 5
    assert call_kwargs["extra_constraints"] == "preserve windows"


def test_nano_banana_non_bytes_result_raises(tiny_png, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    fake_fn = MagicMock()
    fake_fn.remote.return_value = "not-bytes"

    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(return_value=fake_fn)

    with patch.dict(sys.modules, {"modal": fake_modal}):
        with pytest.raises(RuntimeError, match="expected bytes"):
            NanoBananaProRenderer().render(tiny_png, "x")


def test_nano_banana_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    bogus = tmp_path / "nope.png"

    fake_fn = MagicMock()
    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(return_value=fake_fn)

    with patch.dict(sys.modules, {"modal": fake_modal}):
        with pytest.raises(FileNotFoundError):
            NanoBananaProRenderer().render(bogus, "x")
