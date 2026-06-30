import { useEffect, useMemo, useRef } from "react";
import type { Tile } from "../../shared/protocol.js";
import { layout, type Layout, type Rect } from "./treemap.js";
import { drawHeatmap, sectorAggregates } from "./render.js";

export function Heatmap({ tiles, width, height, clamp = 0.06, onHover }:
  { tiles: Tile[]; width: number; height: number; clamp?: number;
    onHover: (t: Tile | null, x?: number, y?: number) => void; }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Render the backing store at device pixels so text/edges stay sharp on HiDPI
  // displays; the canvas is still laid out (and hit-tested) in CSS pixels.
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  const tilesRef = useRef(tiles); tilesRef.current = tiles;
  const clampRef = useRef(clamp); clampRef.current = clamp;
  const key = tiles.map((t) => t.ticker).join(",");
  const lay = useMemo<Layout>(() => layout(tiles, width, height), [key, width, height]);
  const layRef = useRef(lay); layRef.current = lay;
  const byTickerRef = useRef<Map<string, Tile>>(new Map());
  const aggRef = useRef<Map<string, number>>(new Map());
  const lastTilesRef = useRef<Tile[] | null>(null);
  const dirtyRef = useRef(true);

  // Mark dirty whenever the layout (zoom/size/universe) or clamp changes.
  useEffect(() => { dirtyRef.current = true; }, [lay, width, height, clamp, dpr]);

  useEffect(() => {
    const ctx = canvasRef.current!.getContext("2d")!;
    let raf = 0;
    const draw = () => {
      if (tilesRef.current !== lastTilesRef.current) {
        byTickerRef.current = new Map(tilesRef.current.map((t) => [t.ticker, t]));
        aggRef.current = sectorAggregates(tilesRef.current);
        lastTilesRef.current = tilesRef.current;
        dirtyRef.current = true;
      }
      if (dirtyRef.current) {
        // Map CSS pixels to device pixels for this frame, then draw in CSS units.
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);
        drawHeatmap(ctx, layRef.current, byTickerRef.current, aggRef.current, clampRef.current);
        dirtyRef.current = false;
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [width, height, dpr]);

  return <canvas ref={canvasRef}
    width={Math.round(width * dpr)} height={Math.round(height * dpr)}
    style={{ display: "block", width: `${width}px`, height: `${height}px`, cursor: "default" }}
    onMouseMove={(e) => {
      const b = canvasRef.current!.getBoundingClientRect();
      const x = e.clientX - b.left, y = e.clientY - b.top;
      const hit = layRef.current.tiles.find((r: Rect) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1);
      onHover(hit ? tilesRef.current.find((t) => t.ticker === hit.ticker) ?? null : null, e.clientX, e.clientY);
    }}
    onMouseLeave={() => onHover(null)} />;
}
