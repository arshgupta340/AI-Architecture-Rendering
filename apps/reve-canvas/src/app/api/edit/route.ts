import { editRegion, resolveMode } from "@/lib/reve/client";
import { buildChangeDescription, pinAspect, type CanvasLayer, type EnvelopeFacet } from "@/lib/model";
import { getMaterial } from "@/lib/taxonomy";
import type { ReveLayout } from "@/lib/reve/types";

export const runtime = "nodejs";
export const maxDuration = 120;

function stripDataUrl(s: string): string {
  const i = s.indexOf("base64,");
  return i >= 0 ? s.slice(i + 7) : s;
}

interface EditBody {
  imageDataUrl: string;
  layout: ReveLayout;
  layer: CanvasLayer;
  materialId: string;
  facet?: EnvelopeFacet;
  srcWidth: number;
  srcHeight: number;
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Partial<EditBody>;
    const { imageDataUrl, layout, layer, materialId, facet, srcWidth, srcHeight } = body;
    if (!imageDataUrl || !layout || !layer || !materialId) {
      return Response.json({ error: "imageDataUrl, layout, layer, materialId required" }, { status: 400 });
    }
    const material = getMaterial(materialId);
    if (!material) return Response.json({ error: `unknown material ${materialId}` }, { status: 400 });

    const newDescription = buildChangeDescription(layer, material, facet);
    const aspect = srcWidth && srcHeight ? pinAspect(srcWidth, srcHeight) : undefined;

    const result = await editRegion({
      imageB64: stripDataUrl(imageDataUrl),
      layout,
      command: { op: "change", label: layer.reveLabel, new_description: newDescription },
      aspect,
    });

    return Response.json({
      imageDataUrl: `data:image/png;base64,${result.imageB64}`,
      meta: result.meta,
      mode: resolveMode(),
      appliedMaterial: material.label,
      editedLayer: layer.name,
    });
  } catch (err) {
    return Response.json({ error: (err as Error).message }, { status: 500 });
  }
}
