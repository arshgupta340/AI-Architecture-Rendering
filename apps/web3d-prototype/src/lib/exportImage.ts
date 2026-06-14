import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import { useStore, type ExportCfg } from "../state/store";

/**
 * High-res "client-ready" still export. The capture supersamples the LIVE
 * post-processed frame by temporarily raising the renderer pixel-ratio (R3F's
 * setDpr resizes the EffectComposer / WebGPU pipeline with it), reads the canvas
 * to a Blob, then centre-crops to the chosen aspect. The WebGL2 stages set
 * `preserveDrawingBuffer:true` so `toBlob` returns the rendered pixels (not black);
 * the WebGPU stage is best-effort (see ExportCapture).
 */

const ASPECTS: Record<string, number | null> = {
  "16:9": 16 / 9,
  "3:2": 3 / 2,
  "4:3": 4 / 3,
  "1:1": 1,
  free: null,
};

const raf = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

/** Centre-crop an image Blob to the target aspect and re-encode. */
async function cropToAspect(src: Blob, cfg: ExportCfg): Promise<Blob> {
  const target = ASPECTS[cfg.aspect] ?? null;
  const mime = cfg.format === "png" ? "image/png" : "image/jpeg";
  const bmp = await createImageBitmap(src);
  let sx = 0;
  let sy = 0;
  let sw = bmp.width;
  let sh = bmp.height;
  if (target) {
    const cur = bmp.width / bmp.height;
    if (cur > target) {
      sw = Math.round(bmp.height * target);
      sx = Math.round((bmp.width - sw) / 2);
    } else {
      sh = Math.round(bmp.width / target);
      sy = Math.round((bmp.height - sh) / 2);
    }
  }
  const canvas = document.createElement("canvas");
  canvas.width = sw;
  canvas.height = sh;
  const ctx = canvas.getContext("2d")!;
  // White matte under JPG (no alpha) so any transparent margin isn't black.
  if (cfg.format !== "png") {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, sw, sh);
  }
  ctx.drawImage(bmp, sx, sy, sw, sh, 0, 0, sw, sh);
  bmp.close();
  return await new Promise<Blob>((res, rej) =>
    canvas.toBlob((b) => (b ? res(b) : rej(new Error("toBlob failed"))), mime, 0.92),
  );
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function exportFilename(cfg: ExportCfg): string {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
  return `architect3d_${stamp}.${cfg.format}`;
}

/**
 * Mounted INSIDE each Stage's <Canvas>. Registers a capture fn (closing over this
 * stage's renderer) into the store; the NavBar export button calls it. Supersamples
 * to cfg.scale× the current backing resolution, reads the canvas, crops to aspect.
 */
export function ExportCapture() {
  const gl = useThree((s) => s.gl);
  const setDpr = useThree((s) => s.setDpr);
  const invalidate = useThree((s) => s.invalidate);
  const setCaptureFn = useStore((s) => s.setCaptureFn);

  useEffect(() => {
    const fn = async (cfg: ExportCfg): Promise<Blob | null> => {
      const oldDpr = gl.getPixelRatio();
      // Supersample: bump pixel ratio (clamped) so the post pipeline re-renders the
      // full frame at higher resolution. setDpr drives the EffectComposer/pipeline resize.
      const targetDpr = Math.max(1, Math.min(4, oldDpr * cfg.scale));
      try {
        setDpr(targetDpr);
        invalidate();
        // Let R3F + the post pipeline render at least one frame at the new size.
        await raf();
        await raf();
        invalidate();
        await raf();
        const mime = cfg.format === "png" ? "image/png" : "image/jpeg";
        const full = await new Promise<Blob | null>((res) =>
          gl.domElement.toBlob((b) => res(b), mime, 0.92),
        );
        if (!full || full.size < 256) return null; // empty/black capture
        return await cropToAspect(full, cfg);
      } catch {
        return null;
      } finally {
        setDpr(oldDpr);
        invalidate();
      }
    };
    setCaptureFn(fn);
    return () => setCaptureFn(null);
  }, [gl, setDpr, invalidate, setCaptureFn]);

  return null;
}
