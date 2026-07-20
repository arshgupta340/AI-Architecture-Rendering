// Browser-only image compositing. Keep this module free of server imports so the
// editor can use it directly after an edit response arrives.

export interface CompositeResult {
  dataUrl: string;
  driftScore: number;
  maskDataUrl: string;
}

export interface BBox { x0: number; y0: number; x1: number; y1: number }

type BoxPixels = { x0: number; y0: number; x1: number; y1: number };

const DEFAULT_FEATHER_PX = 24;
const DEFAULT_PAD_PCT = 0.02;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function option(value: number | undefined, fallback: number): number {
  return Number.isFinite(value) && value! >= 0 ? value! : fallback;
}

function canvas(width: number, height: number): HTMLCanvasElement {
  const element = document.createElement("canvas");
  element.width = width;
  element.height = height;
  return element;
}

function context(element: HTMLCanvasElement): CanvasRenderingContext2D {
  const value = element.getContext("2d", { willReadFrequently: true });
  if (!value) throw new Error("2D canvas is unavailable in this browser");
  return value;
}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to decode image data URL"));
    image.src = dataUrl;
  });
}

function coverFit(ctx: CanvasRenderingContext2D, image: CanvasImageSource, width: number, height: number): void {
  const source = image as HTMLImageElement;
  const scale = Math.max(width / source.naturalWidth, height / source.naturalHeight);
  const drawWidth = source.naturalWidth * scale;
  const drawHeight = source.naturalHeight * scale;
  ctx.drawImage(image, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight);
}

function pixelBoxes(boxes: BBox[], width: number, height: number, padPx: number): BoxPixels[] {
  return boxes.flatMap((box) => {
    if (![box.x0, box.y0, box.x1, box.y1].every(Number.isFinite)) return [];
    const x0 = clamp(Math.min(box.x0, box.x1) * width - padPx, 0, width);
    const y0 = clamp(Math.min(box.y0, box.y1) * height - padPx, 0, height);
    const x1 = clamp(Math.max(box.x0, box.x1) * width + padPx, 0, width);
    const y1 = clamp(Math.max(box.y0, box.y1) * height + padPx, 0, height);
    return x1 > x0 && y1 > y0 ? [{ x0, y0, x1, y1 }] : [];
  });
}

function boxAlpha(x: number, y: number, box: BoxPixels, width: number, height: number, featherPx: number): number {
  const left = box.x0 === 0 ? Number.POSITIVE_INFINITY : x - box.x0;
  const right = box.x1 === width ? Number.POSITIVE_INFINITY : box.x1 - x;
  const top = box.y0 === 0 ? Number.POSITIVE_INFINITY : y - box.y0;
  const bottom = box.y1 === height ? Number.POSITIVE_INFINITY : box.y1 - y;
  const signedDistance = Math.min(left, right, top, bottom);
  if (featherPx === 0) return signedDistance >= 0 ? 1 : 0;
  return clamp((signedDistance + featherPx) / (2 * featherPx), 0, 1);
}

function createMask(width: number, height: number, boxes: BoxPixels[], featherPx: number): HTMLCanvasElement {
  const maskCanvas = canvas(width, height);
  const mask = context(maskCanvas).createImageData(width, height);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let alpha = 0;
      for (const box of boxes) {
        alpha = Math.max(alpha, boxAlpha(x + 0.5, y + 0.5, box, width, height, featherPx));
        if (alpha === 1) break;
      }
      const offset = (y * width + x) * 4;
      mask.data[offset] = 255;
      mask.data[offset + 1] = 255;
      mask.data[offset + 2] = 255;
      mask.data[offset + 3] = Math.round(alpha * 255);
    }
  }

  context(maskCanvas).putImageData(mask, 0, 0);
  return maskCanvas;
}

function calculateDrift(
  original: CanvasImageSource,
  render: CanvasImageSource,
  mask: CanvasImageSource,
  originalWidth: number,
  originalHeight: number,
): number {
  const width = Math.max(1, Math.min(512, originalWidth));
  const height = Math.max(1, Math.round((originalHeight / originalWidth) * width));
  const originalCanvas = canvas(width, height);
  const renderCanvas = canvas(width, height);
  const maskCanvas = canvas(width, height);
  const originalCtx = context(originalCanvas);
  const renderCtx = context(renderCanvas);
  const maskCtx = context(maskCanvas);

  originalCtx.drawImage(original, 0, 0, width, height);
  coverFit(renderCtx, render, width, height);
  maskCtx.drawImage(mask, 0, 0, width, height);

  const originalData = originalCtx.getImageData(0, 0, width, height).data;
  const renderData = renderCtx.getImageData(0, 0, width, height).data;
  const maskData = maskCtx.getImageData(0, 0, width, height).data;
  let difference = 0;
  let samples = 0;

  for (let offset = 0; offset < originalData.length; offset += 4) {
    if (maskData[offset + 3] >= 13) continue;
    difference += Math.abs(originalData[offset] - renderData[offset]);
    difference += Math.abs(originalData[offset + 1] - renderData[offset + 1]);
    difference += Math.abs(originalData[offset + 2] - renderData[offset + 2]);
    samples += 1;
  }

  return samples === 0 ? 0 : difference / (samples * 3 * 255);
}

/**
 * Lifts the changed pixels from a full-frame Reve render and places them over the
 * original upload. The render is cover-fit when its aspect is slightly different;
 * drift is measured against that fitted render outside the feathered mask.
 */
export async function applyMaskedDelta(
  originalDataUrl: string,
  renderDataUrl: string,
  editedBboxes: BBox[],
  opts?: { featherPx?: number; padPct?: number },
): Promise<CompositeResult> {
  const [originalImage, renderImage] = await Promise.all([loadImage(originalDataUrl), loadImage(renderDataUrl)]);
  const width = originalImage.naturalWidth;
  const height = originalImage.naturalHeight;
  if (width === 0 || height === 0) throw new Error("Original image has no pixel dimensions");

  const featherPx = option(opts?.featherPx, DEFAULT_FEATHER_PX);
  const padPct = option(opts?.padPct, DEFAULT_PAD_PCT);
  const boxes = pixelBoxes(editedBboxes, width, height, padPct * Math.hypot(width, height));
  const maskCanvas = createMask(width, height, boxes, featherPx);
  const originalCanvas = canvas(width, height);
  const renderCanvas = canvas(width, height);
  const outputCanvas = canvas(width, height);
  const originalCtx = context(originalCanvas);
  const renderCtx = context(renderCanvas);
  const outputCtx = context(outputCanvas);

  originalCtx.drawImage(originalImage, 0, 0);
  coverFit(renderCtx, renderImage, width, height);

  const originalData = originalCtx.getImageData(0, 0, width, height);
  const renderData = renderCtx.getImageData(0, 0, width, height);
  const maskData = context(maskCanvas).getImageData(0, 0, width, height).data;
  const output = outputCtx.createImageData(width, height);

  for (let offset = 0; offset < output.data.length; offset += 4) {
    const alpha = maskData[offset + 3] / 255;
    output.data[offset] = Math.round(originalData.data[offset] * (1 - alpha) + renderData.data[offset] * alpha);
    output.data[offset + 1] = Math.round(originalData.data[offset + 1] * (1 - alpha) + renderData.data[offset + 1] * alpha);
    output.data[offset + 2] = Math.round(originalData.data[offset + 2] * (1 - alpha) + renderData.data[offset + 2] * alpha);
    output.data[offset + 3] = Math.round(originalData.data[offset + 3] * (1 - alpha) + renderData.data[offset + 3] * alpha);
  }

  outputCtx.putImageData(output, 0, 0);
  return {
    dataUrl: outputCanvas.toDataURL("image/png"),
    driftScore: calculateDrift(originalImage, renderImage, maskCanvas, width, height),
    maskDataUrl: maskCanvas.toDataURL("image/png"),
  };
}
