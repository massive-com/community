import { useLayoutEffect, useRef, useState } from "react";
import type { Tile } from "../../shared/protocol.js";
import { pctTextColor } from "./color.js";

const fmt = (n: number) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

// Keep the tooltip fully on screen: offset from the cursor, but flip to the other
// side when it would overflow the right/bottom edge, then clamp within a margin so
// it can never run off the viewport. Pure for testing.
export function placeTooltip(
  x: number, y: number, w: number, h: number, vw: number, vh: number, gap = 14, margin = 8,
): { left: number; top: number } {
  let left = x + gap;
  if (left + w > vw - margin) left = x - gap - w;
  left = Math.max(margin, Math.min(left, vw - w - margin));
  let top = y + gap;
  if (top + h > vh - margin) top = y - gap - h;
  top = Math.max(margin, Math.min(top, vh - h - margin));
  return { left, top };
}

export function Tooltip(
  { tile, x, y, periodLabel }:
  { tile: Tile; x: number; y: number; periodLabel: string },
) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x + 14, top: y + 14 });
  // Measure the rendered tooltip and reposition before paint (no flash) so it stays
  // on screen near the right/bottom edges. Recomputes as the cursor or content moves.
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    setPos(placeTooltip(x, y, width, height, window.innerWidth, window.innerHeight));
  }, [x, y, tile.ticker]);

  return (
    <div ref={ref} className="tooltip" style={{ left: pos.left, top: pos.top }}>
      <div className="tt-ticker">{tile.ticker}</div>
      <div className="tt-name">{tile.name}</div>
      <div className="tt-row"><span className="tt-label">Price</span><span>{tile.price ? fmt(tile.price) : "—"}</span></div>
      <div className="tt-row"><span className="tt-label">{periodLabel}</span><span>{tile.priorClose ? fmt(tile.priorClose) : "—"}</span></div>
      <div className="tt-row" style={{ color: pctTextColor(tile.pct), fontWeight: 600 }}>
        <span className="tt-label">Change</span><span>{(tile.pct * 100).toFixed(2)}%</span>
      </div>
    </div>
  );
}
