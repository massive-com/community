import type { Tile } from "../../shared/protocol.js";
import { renderRegion, FONT } from "./render.js";

export interface ExportMeta { title: string; sessionLabel: string; dateStr: string; lookbackLabel: string; }

// Largest sub-rect of (boxW x boxH) with the given aspect (w/h), centered inside the box.
// Used to letterbox the heatmap so it keeps the live viewport's shape (no skew) within
// the fixed 16:9 frame. Exported for tests.
export function fitRect(boxW: number, boxH: number, aspect: number): { x: number; y: number; w: number; h: number } {
  if (!(aspect > 0) || !(boxW > 0) || !(boxH > 0)) return { x: 0, y: 0, w: boxW, h: boxH };
  let w = boxW, h = boxW / aspect;
  if (h > boxH) { h = boxH; w = boxH * aspect; }
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h };
}

// Render the branded 16:9 composition (logical 1600x900, 2x device pixels) into `canvas`.
// `logo` (the white MASSIVE wordmark) is drawn top-right when provided; falls back to text.
// `layoutW`/`layoutH` are the live viewport dimensions: passing them lays the treemap out at
// the on-screen aspect (so the arrangement and which labels show are identical to the screen)
// and letterboxes it centered in the frame. Without them the heatmap fills the region.
export function renderExport(
  canvas: HTMLCanvasElement, tiles: Tile[], meta: ExportMeta, logo?: HTMLImageElement,
  clamp = 0.06, layoutW?: number, layoutH?: number,
): void {
  const W = 1600, H = 900, dpr = 2;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#0A0D11"; ctx.fillRect(0, 0, W, H);
  const padX = 44;

  // header: eyebrow + headline (left), MASSIVE wordmark (right)
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#7D8794"; ctx.font = `600 13px ${FONT}`;
  try { (ctx as any).letterSpacing = "0.16em"; } catch { /* ignore */ }
  ctx.fillText(`REAL-TIME  ·  ${meta.lookbackLabel.toUpperCase()}  ·  SIZED BY MARKET CAP`, padX, 50);
  try { (ctx as any).letterSpacing = "0px"; } catch { /* ignore */ }
  ctx.fillStyle = "#fff"; ctx.font = `800 32px ${FONT}`;
  ctx.fillText(`${meta.title} Heatmap`, padX, 88);
  if (logo && logo.complete && logo.naturalWidth > 0) {
    const lh = 26, lw = (lh * logo.naturalWidth) / logo.naturalHeight;
    ctx.drawImage(logo, W - padX - lw, 58, lw, lh);
  } else {
    ctx.font = `800 34px ${FONT}`;
    const wm = "MASSIVE"; const ww = ctx.measureText(wm).width;
    ctx.fillStyle = "#fff"; ctx.fillText(wm, W - padX - ww, 82);
  }

  // heatmap region. Lay the treemap out at the live viewport aspect and letterbox it
  // (centered, uniform scale) so the arrangement matches the screen and tiles are not
  // skewed. Without viewport dims, fall back to filling the region.
  const top = 120, bottom = 64;
  const regionW = W - 2 * padX, regionH = H - top - bottom;
  if (layoutW && layoutH) {
    const fit = fitRect(regionW, regionH, layoutW / layoutH);
    renderRegion(ctx, tiles, padX + fit.x, top + fit.y, fit.w, fit.h, clamp, layoutW, layoutH);
  } else {
    renderRegion(ctx, tiles, padX, top, regionW, regionH, clamp);
  }

  // footer
  const pct = Math.round(clamp * 100);
  const fy = H - 32;
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#7D8794"; ctx.font = `500 13px ${FONT}`;
  ctx.fillText(`Data via Massive.com    ·    ${meta.sessionLabel}`, padX, fy);
  const lgW = 160, dateReserve = 240;
  const lgX = W - padX - dateReserve - lgW;
  ctx.textAlign = "right"; ctx.fillStyle = "#7D8794"; ctx.fillText(`-${pct}%`, lgX - 8, fy); ctx.textAlign = "left";
  const grad = ctx.createLinearGradient(lgX, 0, lgX + lgW, 0);
  grad.addColorStop(0, "#DC2626"); grad.addColorStop(0.5, "#2A313A"); grad.addColorStop(1, "#16A34A");
  ctx.fillStyle = grad; ctx.fillRect(lgX, fy - 5, lgW, 10);
  ctx.fillStyle = "#7D8794"; ctx.fillText(`+${pct}%`, lgX + lgW + 8, fy);
  ctx.textAlign = "right"; ctx.fillStyle = "#fff"; ctx.font = `600 14px ${FONT}`;
  ctx.fillText(meta.dateStr, W - padX, fy); ctx.textAlign = "left";
}

export function downloadCanvasPng(canvas: HTMLCanvasElement, filename: string): void {
  canvas.toBlob((b) => {
    if (!b) return;
    const url = URL.createObjectURL(b);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  }, "image/png");
}
