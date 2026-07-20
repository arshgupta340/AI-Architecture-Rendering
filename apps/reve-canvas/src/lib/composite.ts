// STUB — replaced wholesale by wt/composite at merge. Do not extend.
//
// Exact contract provided by workstream B (masked-delta composite lib).
// Code against this signature blindly; the real implementation lands on merge.

export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface CompositeResult {
  dataUrl: string;
  driftScore: number;
  maskDataUrl: string;
}

export async function applyMaskedDelta(
  originalDataUrl: string,
  renderDataUrl: string,
  editedBboxes: BBox[],
  opts?: { featherPx?: number; padPct?: number },
): Promise<CompositeResult> {
  // STUB: pass the render straight through, zero drift, empty mask.
  void originalDataUrl;
  void editedBboxes;
  void opts;
  return { dataUrl: renderDataUrl, driftScore: 0, maskDataUrl: "" };
}
