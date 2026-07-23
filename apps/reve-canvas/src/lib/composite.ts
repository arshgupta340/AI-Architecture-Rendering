/**
 * Masked-delta composite-back — the product invariant made concrete
 * (PRD §2 / spike 2026-07-16: "reframing is a registration detail").
 *
 * Reve's render canvas is NEVER the final image. `compositeMaskedDelta`
 * lifts the delta of an edit through a mask and composites it back onto
 * the untouched source, at the source's resolution:
 *
 *     out = source                            where mask == 0   (bit-exact)
 *     out = edited                            where mask == 255 (bit-exact)
 *     out = source + (m/255)·(edited−source)  on soft mask edges
 *
 * Every pixel outside the mask is preserved exactly — all four channels,
 * and the default PNG output keeps that guarantee lossless into the Blob.
 *
 * Registration: `edited` and `mask` are drawn scaled onto the source's
 * pixel grid. The render's layout is aspect-pinned to the source
 * (`pinAspect` in `./model`), so scaling the render back is the
 * registration step; building the mask itself (from region bboxes, with
 * any soft edging) is the caller's job, not this module's.
 *
 * Mask semantics (same convention as the spike's `composite.paste_tile`):
 * a grayscale image where white = take the edited pixel, black = keep the
 * source pixel. The mask value is computed as luminance weighted by
 * alpha, so both opaque grayscale masks and alpha-encoded masks behave.
 *
 * Browser-side only (canvas 2D): the source pixels live in the client, so
 * the composite runs here at zero API cost. Importing this module is
 * SSR-safe; calling `compositeMaskedDelta` without a DOM throws.
 * A cross-origin URL passed without CORS will taint the canvas and reject
 * — in-app usage (data URLs / Blobs / canvases) is always safe.
 */

export type CompositeImageSource =
  | string // data URL, or same-origin / CORS-enabled URL
  | Blob // includes File
  | HTMLImageElement
  | HTMLCanvasElement
  | ImageBitmap;

export interface CompositeOptions {
  /** Output MIME type. Default "image/png" — lossless, which the
   * outside-mask bit-exactness guarantee requires. A lossy type
   * re-encodes the whole frame and breaks it. */
  type?: string;
  /** Encoder quality 0..1 for lossy types. Ignored for PNG. */
  quality?: number;
}

/**
 * Pure per-pixel core of the composite, DOM-free so it can be unit-tested
 * in Node. `source`, `edited`, `mask` are straight (non-premultiplied)
 * RGBA byte buffers of identical length, as produced by
 * `ctx.getImageData(...).data`. Writes into `out` (allocated by default)
 * and returns it.
 */
export function blendMaskedDelta(
  source: Uint8ClampedArray,
  edited: Uint8ClampedArray,
  mask: Uint8ClampedArray,
  out: Uint8ClampedArray<ArrayBuffer> = new Uint8ClampedArray(source.length),
): Uint8ClampedArray<ArrayBuffer> {
  if (
    source.length !== edited.length ||
    source.length !== mask.length ||
    source.length !== out.length ||
    source.length % 4 !== 0
  ) {
    throw new Error(
      "blendMaskedDelta: source, edited, mask and out must be same-length RGBA buffers",
    );
  }
  for (let i = 0; i < source.length; i += 4) {
    // Mask value: integer Rec.601 luma weighted by alpha. Exact for opaque
    // grayscale masks (v,v,v,255) → v; fully transparent → 0 (keep source).
    const luma = Math.floor(
      (mask[i] * 299 + mask[i + 1] * 587 + mask[i + 2] * 114 + 500) / 1000,
    );
    const m = Math.floor((luma * mask[i + 3] + 127) / 255);
    if (m <= 0) {
      out[i] = source[i];
      out[i + 1] = source[i + 1];
      out[i + 2] = source[i + 2];
      out[i + 3] = source[i + 3];
    } else if (m >= 255) {
      out[i] = edited[i];
      out[i + 1] = edited[i + 1];
      out[i + 2] = edited[i + 2];
      out[i + 3] = edited[i + 3];
    } else {
      const inv = 255 - m;
      out[i] = Math.round((edited[i] * m + source[i] * inv) / 255);
      out[i + 1] = Math.round((edited[i + 1] * m + source[i + 1] * inv) / 255);
      out[i + 2] = Math.round((edited[i + 2] * m + source[i + 2] * inv) / 255);
      out[i + 3] = Math.round((edited[i + 3] * m + source[i + 3] * inv) / 255);
    }
  }
  return out;
}

type Drawable = HTMLImageElement | HTMLCanvasElement | ImageBitmap;

async function loadDrawable(src: CompositeImageSource): Promise<Drawable> {
  if (typeof src === "string") {
    const img = new Image();
    const loaded = new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () =>
        reject(new Error("compositeMaskedDelta: failed to load image from URL"));
    });
    img.src = src;
    await loaded;
    return img;
  }
  if (src instanceof Blob) return createImageBitmap(src);
  if (src instanceof HTMLImageElement) {
    if (!src.complete || src.naturalWidth === 0) {
      await new Promise<void>((resolve, reject) => {
        src.addEventListener("load", () => resolve(), { once: true });
        src.addEventListener(
          "error",
          () => reject(new Error("compositeMaskedDelta: HTMLImageElement failed to load")),
          { once: true },
        );
      });
    }
    return src;
  }
  return src; // HTMLCanvasElement | ImageBitmap
}

function intrinsicSize(d: Drawable): { w: number; h: number } {
  return d instanceof HTMLImageElement
    ? { w: d.naturalWidth, h: d.naturalHeight }
    : { w: d.width, h: d.height };
}

function toRgba(d: Drawable, w: number, h: number): Uint8ClampedArray {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("compositeMaskedDelta: 2d canvas context unavailable");
  ctx.drawImage(d, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h).data;
}

/**
 * Composite the masked delta of a Reve edit back onto the untouched source.
 *
 * @param source  The original, unedited image. Defines the output size;
 *                its pixels outside the mask survive bit-exactly.
 * @param edited  The Reve render (aspect-pinned to the source). Scaled to
 *                the source grid; only its in-mask pixels are used.
 * @param mask    Grayscale mask — white takes `edited`, black keeps
 *                `source`, gray blends. Scaled to the source grid.
 * @returns A Blob of the composited image at the source's resolution
 *          (PNG by default).
 */
export async function compositeMaskedDelta(
  source: CompositeImageSource,
  edited: CompositeImageSource,
  mask: CompositeImageSource,
  opts: CompositeOptions = {},
): Promise<Blob> {
  if (typeof document === "undefined") {
    throw new Error(
      "compositeMaskedDelta runs in the browser (canvas 2D) — the source's pixels never leave the client",
    );
  }
  const [srcD, edtD, mskD] = await Promise.all([
    loadDrawable(source),
    loadDrawable(edited),
    loadDrawable(mask),
  ]);
  const { w, h } = intrinsicSize(srcD);
  if (!w || !h) throw new Error("compositeMaskedDelta: source has zero size");

  const rgba = blendMaskedDelta(
    toRgba(srcD, w, h),
    toRgba(edtD, w, h),
    toRgba(mskD, w, h),
  );

  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("compositeMaskedDelta: 2d canvas context unavailable");
  ctx.putImageData(new ImageData(rgba, w, h), 0, 0);

  return new Promise<Blob>((resolve, reject) => {
    c.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("compositeMaskedDelta: canvas.toBlob returned null")),
      opts.type ?? "image/png",
      opts.quality,
    );
  });
}
