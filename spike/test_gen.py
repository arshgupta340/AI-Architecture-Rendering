import os, pathlib
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
prompt = (
    "Modern minimalist interior, large concrete wall, oak floor, "
    "floor-to-ceiling windows, afternoon light, photorealistic architectural visualization"
)

pathlib.Path("outputs").mkdir(exist_ok=True)

print("Testing nano-banana-pro-preview via generate_content + IMAGE modality...")
try:
    r = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    got_image = False
    for part in r.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            pathlib.Path("outputs/nanbanana_test.png").write_bytes(part.inline_data.data)
            print(f"  SUCCESS: {len(part.inline_data.data):,} bytes -> outputs/nanbanana_test.png")
            got_image = True
            break
    if not got_image:
        print(f"  No image part found.")
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {e}")

print("Testing imagen-4.0-fast-generate-001...")
try:
    r2 = client.models.generate_images(
        model="imagen-4.0-fast-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(number_of_images=1),
    )
    data = r2.generated_images[0].image.image_bytes
    pathlib.Path("outputs/imagen4_test.png").write_bytes(data)
    print(f"  SUCCESS: {len(data):,} bytes -> outputs/imagen4_test.png")
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {e}")
