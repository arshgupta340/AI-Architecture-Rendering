/**
 * encode_ktx2.mjs — OPTIONAL, FOLLOW-UP. Encode the /public/materials/<id>/*.jpg
 * maps to GPU-native KTX2 (Basis Universal) so the configurator uploads
 * compressed textures and stays small in VRAM. The shipping default is .jpg
 * (see src/lib/swatches.ts) and works at $0 today; this script is NOT required
 * to run the app.
 *
 * STATUS in this environment: NOT WIRED.
 *   - `ktx` (KhronosGroup KTX-Software CLI) is NOT on PATH here.
 *   - `sharp` is NOT installed (we avoid npm installs; $0 / no new deps).
 * So no .ktx2 assets are produced and swatches.ts keeps loading .jpg. When a
 * machine has `ktx` available, run this to populate /public/materials/<id>/*.ktx2;
 * swatches.ts will prefer them once the KTX2 load path is enabled behind
 * setKTX2Renderer(renderer) (a Stage hands over its initialized renderer).
 *
 * Prereqs to actually encode:
 *   1. KhronosGroup KTX-Software ("ktx" CLI):
 *        https://github.com/KhronosGroup/KTX-Software/releases
 *      Verify with:  ktx --version
 *   2. A jpg->png decoder. Easiest is `sharp` (npm i -D sharp) since `ktx
 *      create` ingests PNG/EXR, not JPG. Alternatively pre-convert with any
 *      tool that outputs PNG.
 *
 * Encoding rules (match three.js KTX2Loader expectations):
 *   - albedo  -> ETC1S, sRGB, mipmaps.  Color data tolerates ETC1S; smallest.
 *       ktx create --format R8G8B8A8_SRGB --encode etc1s --assign-oetf srgb \
 *                  --generate-mipmap albedo.png albedo.ktx2
 *   - normal/roughness/ao -> UASTC + zstd, LINEAR, mipmaps. Data maps need the
 *     higher-quality UASTC to avoid block artifacts; zstd 18 supercompresses.
 *       ktx create --format R8G8B8A8_UNORM --encode uastc --uastc-quality 2 \
 *                  --zstd 18 --assign-oetf linear --generate-mipmap \
 *                  normal.png normal.ktx2
 *
 * Run (when prereqs exist):  node scripts/encode_ktx2.mjs
 * It is idempotent: skips a map whose .ktx2 is newer than its .jpg.
 */
import { existsSync, readdirSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const MATERIALS = join(HERE, "..", "public", "materials");

// map file -> { srgb, encode args } per the rules above.
const MAP_RULES = {
  "albedo.jpg": {
    out: "albedo.ktx2",
    args: ["--format", "R8G8B8A8_SRGB", "--encode", "etc1s", "--assign-oetf", "srgb", "--generate-mipmap"],
  },
  "normal.jpg": {
    out: "normal.ktx2",
    args: ["--format", "R8G8B8A8_UNORM", "--encode", "uastc", "--uastc-quality", "2", "--zstd", "18", "--assign-oetf", "linear", "--generate-mipmap"],
  },
  "roughness.jpg": {
    out: "roughness.ktx2",
    args: ["--format", "R8G8B8A8_UNORM", "--encode", "uastc", "--uastc-quality", "2", "--zstd", "18", "--assign-oetf", "linear", "--generate-mipmap"],
  },
  "ao.jpg": {
    out: "ao.ktx2",
    args: ["--format", "R8G8B8A8_UNORM", "--encode", "uastc", "--uastc-quality", "2", "--zstd", "18", "--assign-oetf", "linear", "--generate-mipmap"],
  },
};

function ktxAvailable() {
  const r = spawnSync("ktx", ["--version"], { encoding: "utf8" });
  return r.status === 0;
}

let sharp = null;
async function loadSharp() {
  try {
    ({ default: sharp } = await import("sharp"));
    return true;
  } catch {
    return false;
  }
}

async function main() {
  if (!existsSync(MATERIALS)) {
    console.error(`No materials dir at ${MATERIALS}. Run fetch_materials.py first.`);
    process.exit(0);
  }
  if (!ktxAvailable()) {
    console.log("`ktx` CLI not on PATH — KTX2 encoding skipped. App keeps using .jpg (default).");
    console.log("Install KhronosGroup KTX-Software, then re-run: node scripts/encode_ktx2.mjs");
    process.exit(0);
  }
  if (!(await loadSharp())) {
    console.log("`sharp` not installed — needed to convert .jpg -> .png for `ktx create`.");
    console.log("Install with `npm i -D sharp`, then re-run. App keeps using .jpg (default).");
    process.exit(0);
  }

  const ids = readdirSync(MATERIALS, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  let encoded = 0;
  for (const id of ids) {
    const dir = join(MATERIALS, id);
    for (const [jpg, rule] of Object.entries(MAP_RULES)) {
      const jpgPath = join(dir, jpg);
      if (!existsSync(jpgPath)) continue;
      const ktx2Path = join(dir, rule.out);
      if (existsSync(ktx2Path) && statSync(ktx2Path).mtimeMs >= statSync(jpgPath).mtimeMs) continue;

      const pngPath = join(dir, jpg.replace(/\.jpg$/, ".png"));
      await sharp(jpgPath).png().toFile(pngPath);
      const r = spawnSync("ktx", ["create", ...rule.args, pngPath, ktx2Path], { stdio: "inherit" });
      try {
        const { unlinkSync } = await import("node:fs");
        unlinkSync(pngPath);
      } catch {
        /* leave the temp png if removal fails */
      }
      if (r.status === 0) {
        encoded++;
        console.log(`  ${id}/${rule.out}`);
      } else {
        console.error(`  FAILED ${id}/${jpg}`);
      }
    }
  }
  console.log(`\nEncoded ${encoded} KTX2 maps.`);
}

main();
