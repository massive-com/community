import type { Tile } from "../../shared/protocol.js";
import { layout, type Layout } from "./treemap.js";
import { pctColor } from "./color.js";

export const FONT = `ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif`;
const INK = "rgba(255,255,255,0.96)";
const INK_DIM = "rgba(255,255,255,0.72)";
const MUTED = "#7D8794";
const GREEN = "#16A34A", RED = "#DC2626";

export function fmtPct(p: number): string { return `${p >= 0 ? "+" : ""}${(p * 100).toFixed(2)}%`; }

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Cap-weighted sector aggregate percent changes.
export function sectorAggregates(tiles: Tile[]): Map<string, number> {
  const acc = new Map<string, { p: number; c: number }>();
  for (const t of tiles) {
    const a = acc.get(t.group) ?? { p: 0, c: 0 };
    a.p += t.pct * t.marketCap; a.c += t.marketCap; acc.set(t.group, a);
  }
  const out = new Map<string, number>();
  for (const [g, a] of acc) out.set(g, a.c > 0 ? a.p / a.c : 0);
  return out;
}

// Draw the heatmap (sector headers + rounded tiles) using a precomputed layout.
// agg + byTicker are precomputed so per-frame redraws stay cheap.
export function drawHeatmap(
  ctx: CanvasRenderingContext2D, lay: Layout, byTicker: Map<string, Tile>, agg: Map<string, number>,
  clamp = 0.06,
) {
  for (const r of lay.tiles) {
    const t = byTicker.get(r.ticker); if (!t) continue;
    const w = r.x1 - r.x0, h = r.y1 - r.y0;
    ctx.fillStyle = pctColor(t.pct, clamp);
    roundRect(ctx, r.x0, r.y0, w, h, Math.min(3, w / 4, h / 4)); ctx.fill();
    // Label every tile that can fit any text at all; font scales to the tile.
    if (w >= 11 && h >= 7) {
      const fs = Math.max(5, Math.min(13, Math.floor(w / 3.8), Math.floor(h / 2.2)));
      ctx.textBaseline = "top"; ctx.textAlign = "left";
      ctx.fillStyle = "rgba(255,255,255,0.97)";
      ctx.font = `700 ${fs}px ${FONT}`;
      ctx.fillText(t.ticker, r.x0 + 2, r.y0 + 1);
      if (h >= fs * 2 + 4) {
        ctx.fillStyle = "rgba(255,255,255,0.82)";
        ctx.font = `500 ${Math.max(5, fs - 1)}px ${FONT}`;
        ctx.fillText(fmtPct(t.pct), r.x0 + 2, r.y0 + 1 + fs + 1);
      }
    }
  }
  ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  for (const g of lay.groups) {
    const label = g.name.toUpperCase();
    ctx.fillStyle = "#7D8794"; ctx.font = `600 10px ${FONT}`;
    try { (ctx as any).letterSpacing = "0.4px"; } catch { /* ignore */ }
    ctx.fillText(label, g.x0 + 1, g.y0 + 12);
    const lw = ctx.measureText(label).width;
    try { (ctx as any).letterSpacing = "0px"; } catch { /* ignore */ }
    const a = agg.get(g.name) ?? 0;
    ctx.fillStyle = a >= 0 ? "#16A34A" : "#DC2626";
    ctx.font = `700 10px ${FONT}`;
    ctx.fillText(fmtPct(a), g.x0 + 1 + lw + 7, g.y0 + 12);
  }
}

// Convenience for one-shot renders (export): computes layout+agg then draws into a region.
// The layout is computed at (layoutW, layoutH) and then scaled to fit (w, h). Passing the
// live viewport dimensions as (layoutW, layoutH) makes the export's tile arrangement and
// label decisions identical to what is shown on screen. Defaults to the region size.
export function renderRegion(
  ctx: CanvasRenderingContext2D, tiles: Tile[], x: number, y: number, w: number, h: number,
  clamp = 0.06, layoutW = w, layoutH = h,
) {
  const lay = layout(tiles, layoutW, layoutH);
  const byTicker = new Map(tiles.map((t) => [t.ticker, t] as const));
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(w / layoutW, h / layoutH);
  drawHeatmap(ctx, lay, byTicker, sectorAggregates(tiles), clamp);
  ctx.restore();
  return lay;
}
