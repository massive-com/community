import { hierarchy, treemap as d3treemap } from "d3-hierarchy";
import type { Tile } from "../../shared/protocol.js";

export interface Rect { ticker: string; x0: number; y0: number; x1: number; y1: number; }
export interface GroupRect { name: string; x0: number; y0: number; x1: number; y1: number; }
export interface Layout { tiles: Rect[]; groups: GroupRect[]; }

export function layout(tiles: Tile[], width: number, height: number): Layout {
  const groups = new Map<string, Tile[]>();
  for (const t of tiles) {
    const arr = groups.get(t.group) ?? [];
    if (!groups.has(t.group)) groups.set(t.group, arr);
    arr.push(t);
  }
  const root = {
    name: "root",
    children: [...groups.entries()].map(([name, items]) => ({
      // Compress the size range (sqrt) so the mega-caps don't dwarf everything;
      // this gives the smallest tiles enough area to show their labels.
      name, children: items.map((t) => ({
        name: t.ticker,
        value: Math.sqrt(Math.max(t.marketCap, 0)) + 0.01,
      })),
    })),
  };
  const h = hierarchy(root).sum((d: any) => d.value ?? 0).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  d3treemap<typeof root>().size([width, height]).paddingInner(2).paddingTop(18).round(true)(h as any);
  const tileRects: Rect[] = (h.leaves() as any[]).map((l) => ({ ticker: l.data.name, x0: l.x0, y0: l.y0, x1: l.x1, y1: l.y1 }));
  const groupRects: GroupRect[] = ((h.children ?? []) as any[]).map((c) => ({ name: c.data.name, x0: c.x0, y0: c.y0, x1: c.x1, y1: c.y1 }));
  return { tiles: tileRects, groups: groupRects };
}
