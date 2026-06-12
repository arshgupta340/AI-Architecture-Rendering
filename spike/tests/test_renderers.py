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

from spike.renderers.nano_banana import NanoBananaProRenderer
from spike.renderers.recraft import RecraftV3Renderer
from spike.renderers.replicate_models import (
    Flux2ProRenderer,
    FluxCannyProRenderer,
    FluxDepthProRenderer,
    FluxFillProRenderer,
    HiDreamE1Renderer,
    QwenImageEditRenderer,
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
# FLUX 2 Pro on Replicate — array-shaped input_images field                   #
# --------------------------------------------------------------------------- #


def test_flux_2_pro_wraps_image_in_input_images_array(
    tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch
):
    """FLUX 2 Pro's Replicate schema expects an `input_images` array, not a
    single image string. Verify the subclass override wraps correctly."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr("spike.renderers.replicate_models.time.sleep", lambda *_: None)

    submit_resp = _fake_response(
        json_body={
            "id": "pred-flux2",
            "urls": {"get": "https://api.replicate.com/v1/predictions/pred-flux2"},
        }
    )
    ready_resp = _fake_response(
        json_body={
            "status": "succeeded",
            "output": "https://signed.example/flux2.png",
        }
    )
    download_resp = _fake_response(content=another_tiny_png)

    fake_requests = MagicMock()
    fake_requests.post.return_value = submit_resp
    fake_requests.get.side_effect = [ready_resp, download_resp]

    with patch.dict(sys.modules, {"requests": fake_requests}):
        out = Flux2ProRenderer().render(tiny_png, "studio render", seed=42)

    assert out == another_tiny_png

    submit_args, submit_kwargs = fake_requests.post.call_args
    assert submit_args[0] == (
        "https://api.replicate.com/v1/models/black-forest-labs/flux-2-pro/predictions"
    )
    body = submit_kwargs["json"]
    input_block = body["input"]
    assert input_block["prompt"] == "studio render"
    assert input_block["seed"] == 42
    # Image lives inside a list, not as a bare string
    assert isinstance(input_block["input_images"], list)
    assert len(input_block["input_images"]) == 1
    encoded = input_block["input_images"][0].split(",", 1)[1]
    assert base64.b64decode(encoded) == tiny_png_bytes


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
    "renderer_cls,owner,name,image_field",
    [
        (QwenImageEditRenderer, "qwen", "qwen-image-edit", "image"),
        (HiDreamE1Renderer, "prunaai", "hidream-e1.1", "image"),
        (FluxCannyProRenderer, "black-forest-labs", "flux-canny-pro", "control_image"),
        (FluxDepthProRenderer, "black-forest-labs", "flux-depth-pro", "control_image"),
        (FluxFillProRenderer, "black-forest-labs", "flux-fill-pro", "image"),
    ],
)
def test_replicate_missing_env_raises(
    renderer_cls, owner, name, image_field, tiny_png, monkeypatch
):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="REPLICATE_API_TOKEN not set"):
        renderer_cls().render(tiny_png, "anything")


@pytest.mark.parametrize(
    "renderer_cls,owner,name,image_field",
    [
        (QwenImageEditRenderer, "qwen", "qwen-image-edit", "image"),
        (HiDreamE1Renderer, "prunaai", "hidream-e1.1", "image"),
        (FluxCannyProRenderer, "black-forest-labs", "flux-canny-pro", "control_image"),
        (FluxDepthProRenderer, "black-forest-labs", "flux-depth-pro", "control_image"),
        (FluxFillProRenderer, "black-forest-labs", "flux-fill-pro", "image"),
    ],
)
def test_replicate_request_shape_and_response(
    renderer_cls, owner, name, image_field,
    tiny_png, tiny_png_bytes, another_tiny_png, monkeypatch,
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
    # Renderers with a pinned version (e.g. HiDream e1.1 — its slug contains
    # a period that breaks the /models/<owner>/<name>/predictions route) hit
    # /v1/predictions with a "version" body field. Others use the model path.
    body = submit_kwargs["json"]
    if renderer_cls.model_version is not None:
        assert submit_args[0] == "https://api.replicate.com/v1/predictions"
        assert body["version"] == renderer_cls.model_version
    else:
        assert submit_args[0] == (
            f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
        )
    assert submit_kwargs["headers"]["Authorization"] == "Token test-token"

    assert "input" in body
    input_block = body["input"]
    assert input_block["prompt"] == "soft daylight"
    assert input_block["seed"] == 99
    # Image lives under whichever field the renderer class declared, as a data URL.
    assert isinstance(input_block[image_field], str)
    assert input_block[image_field].startswith("data:image/png;base64,")
    encoded = input_block[image_field].split(",", 1)[1]
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
