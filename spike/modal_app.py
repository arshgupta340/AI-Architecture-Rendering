"""
Spike: Photoshop-for-Architects pipeline
Four stages running on Modal GPU:
  1. generate()       — Gemini 2.0 Flash Image (native image output)
  2. segment()        — SAM 2 click-to-mask  (facebook/sam2-hiera-large)
  3. apply_material() — SD Inpainting v1.5   (1.7 GB, fast cold-start)
  4. composite()      — paste tile back (CPU, local)

SD Inpainting is used for the spike. FLUX.1 Fill + IP-Adapter swap in for v1.
Image definition is FROZEN — do not edit the pip_install lists or Modal
will rebuild the entire container (~10 min penalty per change).

Run:  modal run modal_app.py
      modal run modal_app.py --prompt "..." --click-x 400 --click-y 300
"""

import io
import os
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# FROZEN container image — edit app logic below this block, not above
# ---------------------------------------------------------------------------

cuda_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        extra_index_url="https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "diffusers==0.30.3",
        "transformers==4.44.2",
        "accelerate==0.33.0",
        "safetensors==0.4.3",
        "google-genai>=1.0",
        "Pillow>=10.0",
        "numpy>=1.26",
        "opencv-python-headless>=4.9",
        "huggingface_hub>=0.23",
        "omegaconf>=2.3",
    )
    .apt_install("git")
    .pip_install("git+https://github.com/facebookresearch/sam2.git@main")
)

app = modal.App("arch-rendering-spike", image=cuda_image)

volume = modal.Volume.from_name("arch-rendering-weights", create_if_missing=True)
WEIGHTS_DIR = Path("/weights")

secret = modal.Secret.from_name("arch-spike", required_keys=["GOOGLE_API_KEY"])


# ---------------------------------------------------------------------------
# Stage 1 — Generate via HuggingFace Serverless Inference (SDXL)
# NOTE: Gemini 2.0 Flash image-gen API requires preview access not yet active
# on this key. Swap back to Gemini once access is granted — just replace the
# function body; no other code changes needed.
# ---------------------------------------------------------------------------

@app.function(secrets=[secret], timeout=120)
def generate(prompt: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    full_prompt = (
        f"{prompt}. "
        "Architectural visualization, photorealistic interior perspective, "
        "natural light, clean composition, sharp detail, high resolution."
    )

    # nano-banana-pro-preview uses generate_content + IMAGE modality
    # (imagen-4.0-fast-generate-001 uses generate_images — swap model name below if preferred)
    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            data = part.inline_data.data
            print(f"[generate] Nano Banana Pro: {len(data):,} bytes")
            return data

    raise RuntimeError("No image returned by Nano Banana Pro")


# ---------------------------------------------------------------------------
# Stage 2 (new path) — Render from 3D-model viewport screenshot (image-to-image)
# Nano Banana Pro takes a shaded model screenshot + prompt and produces a
# photorealistic render that PRESERVES the geometry while replacing the
# cartoon shading with photoreal materials.
#
# Principle: color discontinuities in the input mark region BOUNDARIES (a
# different color means a different form / material) but the model must NOT
# assume specific colors map to specific architectural elements — different
# model setups use different color schemes. Reason from geometry and context.
# ---------------------------------------------------------------------------

@app.function(secrets=[secret], timeout=180)
def render_from_model_view(
    image_bytes: bytes,
    style_prompt: str = "modern materials, natural daylight, professional architectural render",
    mime_type: str = "image/png",
    seed: int | None = None,
    extra_constraints: str = "",
) -> bytes:
    """
    Input: 3D-model viewport screenshot (PNG) from Rhino / SketchUp / Revit /
    Forma in default shaded display mode — solid color fills plus visible edges.
    Output: photorealistic render preserving every edge, opening, and form.

    seed: optional RNG seed for reproducible output. Different seeds produce
          different renders; useful for distinguishing deterministic vs
          stochastic failures.
    extra_constraints: optional extra natural-language constraints injected
          into the prompt (e.g., "the right facade has no windows").
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    instruction = (
        "This is a 3D-model viewport screenshot exported from architectural "
        "modeling software (Rhino, SketchUp, Revit, or similar). It shows a "
        "shaded perspective view with solid color fills and visible edges.\n\n"
        "Render it as a photorealistic architectural visualization. RULES:\n"
        "1. PRESERVE GEOMETRY EXACTLY. Every edge, corner, opening, building "
        "form, window placement, and structural detail must remain in the "
        "same position, scale, and proportion as shown. Do not move, rotate, "
        "reshape, add, or delete any architectural element. Treat the input "
        "geometry as binding, not as a suggestion.\n"
        "2. COLOR INTERPRETATION. Different colors in the input indicate "
        "distinct forms or materials — treat color discontinuities as region "
        "boundaries. However, DO NOT assume specific colors map to specific "
        "architectural elements (different model setups use different color "
        "schemes). Reason from geometry, scale, and context to decide what "
        "each region represents.\n"
        "3. REPLACE CARTOON SHADING with photoreal materials, lighting, "
        "shadows, atmosphere, and surface texture appropriate to each region. "
        "Add realistic sky, surroundings, and environmental context where "
        "the input shows empty/background space.\n"
        f"4. STYLE: {style_prompt}.\n"
        "5. MATERIAL & CONTEXT BASELINE. Unless the caller's extra constraints "
        "or style prompt say otherwise, use a NEUTRAL architectural palette as "
        "the default: light gray concrete or stucco for walls, neutral-tinted "
        "glazing, dark anodized aluminum or steel mullions and frames, gray "
        "concrete or asphalt for ground. Keep the same palette across all "
        "facades of the same building. Do NOT invent water features, swimming "
        "pools, rooftop amenities, distant skylines, large planting beds, or "
        "significant vegetation that are not present in the input geometry. "
        "Treat the scene context (sky, ground plane, immediate surroundings) "
        "as a minimal neutral backdrop unless the input clearly shows urban "
        "fabric.\n"
    )
    if extra_constraints:
        instruction += f"6. EXTRA CONSTRAINTS: {extra_constraints}\n"
    instruction += "\nOutput a single high-quality architectural render."

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    config_kwargs = {"response_modalities": ["IMAGE", "TEXT"]}
    if seed is not None:
        config_kwargs["seed"] = seed

    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[image_part, instruction],
        config=types.GenerateContentConfig(**config_kwargs),
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            data = part.inline_data.data
            seed_str = f" seed={seed}" if seed is not None else ""
            print(f"[render_from_model_view] Nano Banana Pro{seed_str}: {len(data):,} bytes")
            return data

    raise RuntimeError("No image returned by Nano Banana Pro from model-view input")


# Back-compat alias for the v1.1 line-work mode (same function for now;
# the line-work-specific prompt path will be re-introduced when that mode ships).
render_from_linework = render_from_model_view


# ---------------------------------------------------------------------------
# Stage 1b — VLM region tagging (Gemini 3 Pro structured output)
# Takes the original viewport screenshot + the photoreal render and returns
# a list of labeled bounding boxes (wall, window, door, …) in render-pixel
# coordinates. The render is the authoritative coordinate space because
# downstream tools (SAM2, inpainting) operate on the render, not the model
# screenshot. The screenshot is provided as additional context so the VLM
# can disambiguate regions whose geometric identity is clearer in the
# source 3D view than in the photoreal output.
# ---------------------------------------------------------------------------

@app.function(secrets=[secret], timeout=120)
def tag_regions(
    screenshot_bytes: bytes,
    render_bytes: bytes,
    screenshot_mime: str = "image/png",
    render_mime: str = "image/png",
):
    """
    Inputs:
      screenshot_bytes: the original 3D-model viewport screenshot (PNG bytes).
      render_bytes:     the photoreal render produced by render_from_model_view.
    Returns: a JSON string (TagRegionsResponse schema) — parsed by the local
    caller so pydantic and spike.schemas need not be installed in the container.

    Bounding boxes are in pixel coordinates of the RENDER image (not the
    screenshot).
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    allowed = (
        "wall, floor, ceiling, window, door, mullion, roof, "
        "ground, sky, vegetation, furniture, person, vehicle"
    )
    instruction = (
        "You are tagging architectural regions for a Photoshop-style editor. "
        "You are given two images of the SAME scene:\n"
        "  IMAGE 1: the 3D-model viewport screenshot (solid color fills, "
        "visible edges) — use this to disambiguate geometry.\n"
        "  IMAGE 2: the photoreal render produced from that screenshot — "
        "ALL bounding boxes MUST be in pixel coordinates of IMAGE 2.\n\n"
        "Return a JSON object with a single key 'regions' whose value is a "
        "list of region objects. Each region object has:\n"
        "  - id: a short unique string (e.g., 'r1', 'r2', ...)\n"
        "  - label: ONE of [" + allowed + "]\n"
        "  - bbox: {x, y, w, h} in IMAGE 2 pixel coordinates "
        "(x, y is top-left; w, h are width and height)\n"
        "  - confidence: float in [0, 1]\n"
        "  - parent_id: optional id of an enclosing region "
        "(e.g., a 'mullion' inside a 'window'), or null\n\n"
        "Cover every visually distinct architectural region. Prefer tight "
        "bounding boxes. If a region does not fit any allowed label, omit it."
    )

    screenshot_part = types.Part.from_bytes(
        data=screenshot_bytes, mime_type=screenshot_mime
    )
    render_part = types.Part.from_bytes(
        data=render_bytes, mime_type=render_mime
    )

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=[screenshot_part, render_part, instruction],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    text = getattr(response, "text", None) or response.candidates[0].content.parts[0].text
    print(f"[tag_regions] raw response length={len(text)} chars")
    return text


# ---------------------------------------------------------------------------
# Stage 2 — SAM 2 segmentation (A10G)
# ---------------------------------------------------------------------------

@app.function(
    gpu="A10G",
    volumes={str(WEIGHTS_DIR): volume},
    timeout=300,
)
def segment(
    image_bytes: bytes,
    click_x: int | None = None,
    click_y: int | None = None,
    prompt: dict | None = None,
) -> bytes:
    """
    SAM 2 segmentation accepting either a click point OR a bounding box.

    Preferred call shape (new):
      segment(image_bytes, prompt={"type": "point", "x": 400, "y": 300})
      segment(image_bytes, prompt={"type": "bbox", "x": 100, "y": 50, "w": 200, "h": 150})

    Legacy call shape (deprecated, kept for back-compat with existing callers
    in run_*.py and modal_app.main()):
      segment(image_bytes, click_x, click_y)
    A DeprecationWarning is emitted when the legacy shape is used; the call
    is internally translated to a point prompt.

    The bbox shape lets the VLM tagging output (TagRegionsResponse.regions[*].bbox)
    flow directly into SAM2 without picking a point inside each region.
    """
    import warnings

    import numpy as np
    import torch
    from PIL import Image
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    # ---- Normalize legacy (click_x, click_y) -> prompt dict ----
    if prompt is None:
        if click_x is None or click_y is None:
            raise ValueError(
                "segment() requires either prompt={'type': 'point'|'bbox', ...} "
                "or the legacy (click_x, click_y) positional arguments."
            )
        warnings.warn(
            "segment(image_bytes, click_x, click_y) is deprecated; pass "
            "prompt={'type': 'point', 'x': ..., 'y': ...} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        prompt = {"type": "point", "x": click_x, "y": click_y}
    elif click_x is not None or click_y is not None:
        raise ValueError(
            "segment(): pass either prompt=... or (click_x, click_y), not both."
        )

    ptype = prompt.get("type")
    if ptype not in ("point", "bbox"):
        raise ValueError(
            f"segment(): prompt['type'] must be 'point' or 'bbox', got {ptype!r}"
        )

    device = "cuda" if torch.cuda.is_available() else "cpu"

    predictor = SAM2ImagePredictor.from_pretrained(
        "facebook/sam2-hiera-large",
        cache_dir=str(WEIGHTS_DIR / "sam2"),
    )

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size

    point_coords = None
    point_labels = None
    box = None

    if ptype == "point":
        try:
            px = int(prompt["x"])
            py = int(prompt["y"])
        except KeyError as e:
            raise ValueError(f"segment(): point prompt missing key {e}") from e
        cx = max(0, min(px, w - 1))
        cy = max(0, min(py, h - 1))
        point_coords = np.array([[cx, cy]])
        point_labels = np.array([1])
        print(f"[segment] {w}x{h} image, point=({cx},{cy})")
    else:  # bbox
        try:
            bx = int(prompt["x"])
            by = int(prompt["y"])
            bw = int(prompt["w"])
            bh = int(prompt["h"])
        except KeyError as e:
            raise ValueError(f"segment(): bbox prompt missing key {e}") from e
        # Clip to image; SAM2 expects [x1, y1, x2, y2] in pixel coords.
        x1 = max(0, min(bx, w - 1))
        y1 = max(0, min(by, h - 1))
        x2 = max(0, min(bx + bw, w - 1))
        y2 = max(0, min(by + bh, h - 1))
        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"segment(): bbox has zero area after clipping to image "
                f"({w}x{h}): got x1={x1} y1={y1} x2={x2} y2={y2}."
            )
        box = np.array([x1, y1, x2, y2])
        print(f"[segment] {w}x{h} image, bbox=({x1},{y1},{x2},{y2})")

    with torch.inference_mode(), torch.autocast(device, dtype=torch.bfloat16):
        predictor.set_image(np.array(img))
        masks, scores, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=box,
            multimask_output=True,
        )

    best = masks[scores.argmax()]
    print(f"[segment] coverage={best.mean()*100:.1f}%")

    mask_img = Image.fromarray((best * 255).astype("uint8"))
    buf = io.BytesIO()
    mask_img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Stage 3 — SD Inpainting (A10G, 1.7 GB weights)
# ---------------------------------------------------------------------------

@app.function(
    gpu="A10G",
    volumes={str(WEIGHTS_DIR): volume},
    timeout=300,
)
def apply_material(
    base_image_bytes: bytes,
    mask_bytes: bytes,
    material_name: str = "travertine",
    num_steps: int = 25,
) -> bytes:
    import torch
    from PIL import Image
    from diffusers import StableDiffusionInpaintPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_cache = WEIGHTS_DIR / "hf-cache"
    hf_cache.mkdir(parents=True, exist_ok=True)

    print("[apply_material] Loading SD Inpainting pipeline (~1.7 GB on first run)...")
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        "runwayml/stable-diffusion-inpainting",
        torch_dtype=torch.float16,
        safety_checker=None,
        requires_safety_checker=False,
        cache_dir=str(hf_cache),
    ).to(device)
    volume.commit()
    pipe.enable_attention_slicing()

    TARGET = 512  # SD inpaint native resolution
    base = Image.open(io.BytesIO(base_image_bytes)).convert("RGB").resize((TARGET, TARGET))
    mask = Image.open(io.BytesIO(mask_bytes)).convert("L").resize((TARGET, TARGET))

    prompt = (
        f"photorealistic {material_name} wall surface, architectural interior, "
        "natural light, sharp texture detail, professional photography"
    )
    neg = "blurry, distorted, artifacts, low quality, cartoon, painting"

    print(f"[apply_material] Inpainting as '{material_name}'…")
    result = pipe(
        prompt=prompt,
        negative_prompt=neg,
        image=base,
        mask_image=mask,
        num_inference_steps=num_steps,
        guidance_scale=8.5,
        generator=torch.Generator(device).manual_seed(42),
    ).images[0]

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    print("[apply_material] Done.")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Stage 4 — Composite (local CPU)
# ---------------------------------------------------------------------------

def composite(base_bytes: bytes, tile_bytes: bytes, mask_bytes: bytes) -> bytes:
    from PIL import Image

    base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    tile = Image.open(io.BytesIO(tile_bytes)).convert("RGBA").resize(base.size)
    mask = Image.open(io.BytesIO(mask_bytes)).convert("L").resize(base.size)

    result = Image.composite(tile, base, mask)
    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Local entrypoint
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(
    prompt: str = "Modern minimalist living room, concrete walls, large windows, evening light",
    click_x: int = 400,
    click_y: int = 300,
    material_name: str = "travertine",
    output: str = "outputs/result.png",
    base_image: str = "",  # skip generation and use this local file instead
):
    Path("outputs").mkdir(exist_ok=True)

    if base_image:
        print(f"\n=== Stage 1: Skipping generation — using {base_image} ===")
        base_bytes = Path(base_image).read_bytes()
        Path("outputs/base.png").write_bytes(base_bytes)
        print("  → outputs/base.png (copy)")
    else:
        print("\n=== Stage 1: Generate ===")
        base_bytes = generate.remote(prompt)
        Path("outputs/base.png").write_bytes(base_bytes)
        print("  → outputs/base.png")

    print(f"\n=== Stage 2: Segment @ ({click_x},{click_y}) ===")
    mask_bytes = segment.remote(base_bytes, click_x, click_y)
    Path("outputs/mask.png").write_bytes(mask_bytes)
    print("  → outputs/mask.png")

    print(f"\n=== Stage 3: Apply '{material_name}' ===")
    tile_bytes = apply_material.remote(base_bytes, mask_bytes, material_name)
    Path("outputs/tile.png").write_bytes(tile_bytes)
    print("  → outputs/tile.png")

    print("\n=== Stage 4: Composite ===")
    result_bytes = composite(base_bytes, tile_bytes, mask_bytes)
    Path(output).write_bytes(result_bytes)
    print(f"  → {output}")

    print("\n=== Spike complete — open outputs/result.png ===")
