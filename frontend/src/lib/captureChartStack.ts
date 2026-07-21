/** Captura el Ticker Chart stack (canvases LWC) como PNG base64 para visión. */

const MAX_WIDTH = 1280;
const MAX_BYTES = 3_500_000; // ~3.5MB payload safety

export type ChartCaptureResult = {
  base64: string;
  mediaType: "image/png";
  width: number;
  height: number;
};

/**
 * Stitch visible chart canvases under `root` into one PNG (top → bottom).
 * Falls back to null if no canvas is ready yet.
 */
export async function captureChartStackPng(
  root: HTMLElement | null,
): Promise<ChartCaptureResult | null> {
  if (!root) return null;

  const canvases = Array.from(root.querySelectorAll("canvas")).filter(
    (canvas) => canvas.width > 0 && canvas.height > 0,
  );
  if (canvases.length === 0) return null;

  const sourceWidth = Math.max(...canvases.map((c) => c.width));
  const sourceHeight = canvases.reduce((sum, c) => sum + c.height, 0);
  if (sourceWidth <= 0 || sourceHeight <= 0) return null;

  const scale = sourceWidth > MAX_WIDTH ? MAX_WIDTH / sourceWidth : 1;
  const outW = Math.max(1, Math.round(sourceWidth * scale));
  const outH = Math.max(1, Math.round(sourceHeight * scale));

  const out = document.createElement("canvas");
  out.width = outW;
  out.height = outH;
  const ctx = out.getContext("2d");
  if (!ctx) return null;

  ctx.fillStyle = "#09090b";
  ctx.fillRect(0, 0, outW, outH);

  let y = 0;
  for (const canvas of canvases) {
    const drawH = Math.round(canvas.height * scale);
    const drawW = Math.round(canvas.width * scale);
    ctx.drawImage(canvas, 0, y, drawW, drawH);
    y += drawH;
  }

  let quality = 1;
  let dataUrl = out.toDataURL("image/png");
  let base64 = dataUrl.replace(/^data:image\/png;base64,/, "");

  // If huge, downscale once more.
  if (base64.length > MAX_BYTES && scale > 0.5) {
    const shrink = 0.7;
    const smaller = document.createElement("canvas");
    smaller.width = Math.max(1, Math.round(outW * shrink));
    smaller.height = Math.max(1, Math.round(outH * shrink));
    const sctx = smaller.getContext("2d");
    if (sctx) {
      sctx.fillStyle = "#09090b";
      sctx.fillRect(0, 0, smaller.width, smaller.height);
      sctx.drawImage(out, 0, 0, smaller.width, smaller.height);
      dataUrl = smaller.toDataURL("image/png");
      base64 = dataUrl.replace(/^data:image\/png;base64,/, "");
      return {
        base64,
        mediaType: "image/png",
        width: smaller.width,
        height: smaller.height,
      };
    }
  }

  void quality;
  return {
    base64,
    mediaType: "image/png",
    width: outW,
    height: outH,
  };
}
