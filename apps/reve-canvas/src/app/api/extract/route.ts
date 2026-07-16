import { extractLayout, resolveMode } from "@/lib/reve/client";
import { autoLayerize, relabelWithRegionKeys } from "@/lib/model";

export const runtime = "nodejs";
export const maxDuration = 120;

function stripDataUrl(s: string): string {
  const i = s.indexOf("base64,");
  return i >= 0 ? s.slice(i + 7) : s;
}

export async function POST(request: Request) {
  try {
    const { imageDataUrl } = (await request.json()) as { imageDataUrl?: string };
    if (!imageDataUrl) return Response.json({ error: "imageDataUrl required" }, { status: 400 });

    const { layout, meta } = await extractLayout(stripDataUrl(imageDataUrl));
    const { layout: keyed, idByOld } = relabelWithRegionKeys(layout);
    const layers = autoLayerize(keyed, idByOld);

    return Response.json({ layout: keyed, layers, meta, mode: resolveMode() });
  } catch (err) {
    return Response.json({ error: (err as Error).message }, { status: 500 });
  }
}
