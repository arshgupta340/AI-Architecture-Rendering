import type { CanvasLayer, EnvelopeFacet } from "@/lib/model";

/** Original render → light preview for on-canvas display (full-res kept for export). */
export function toPreview(dataUrl: string, maxW = 1600): Promise<string> {
  return new Promise((resolve) => {
    const img = new window.Image();
    img.onload = () => {
      if (img.naturalWidth <= maxW) return resolve(dataUrl);
      const scale = maxW / img.naturalWidth;
      const c = document.createElement("canvas");
      c.width = maxW;
      c.height = Math.round(img.naturalHeight * scale);
      c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
      resolve(c.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

/** Per-semantic color used for layer dots, bbox strokes, and selection tints. */
export const SEMANTIC_COLOR: Record<string, string> = {
  wall: "#e0794a",
  glazing: "#4aa3e0",
  roof: "#8a6bd6",
  floor: "#c9a24a",
  ceiling: "#7fb0d0",
  ground: "#6fae54",
  paving: "#9a8f7a",
  vegetation: "#4fb06a",
  furniture: "#d06fb0",
  fixture: "#e0c24a",
  sky: "#7cc4e8",
  water: "#3fb6c9",
  context: "#c0603a",
  door: "#d98a3a",
  person: "#e04a7a",
  vehicle: "#5a7fd0",
  text: "#aaaaaa",
};

export function semanticColor(layer: CanvasLayer): string {
  return SEMANTIC_COLOR[layer.semantic] ?? "#888";
}
