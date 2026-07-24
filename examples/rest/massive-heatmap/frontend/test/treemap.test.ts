import { describe, it, expect } from "vitest";
import { layout } from "../src/treemap.js";
import type { Tile } from "../../shared/protocol.js";

const tiles: Tile[] = [
  { ticker: "A", name: "A", group: "Tech",   marketCap: 300, priorClose: 1, price: 1, pct: 0 },
  { ticker: "B", name: "B", group: "Tech",   marketCap: 100, priorClose: 1, price: 1, pct: 0 },
  { ticker: "C", name: "C", group: "Energy", marketCap: 200, priorClose: 1, price: 1, pct: 0 },
];

describe("layout", () => {
  it("returns one rect per tile within bounds", () => {
    const { tiles: rects, groups } = layout(tiles, 800, 600);
    expect(rects).toHaveLength(3);
    for (const r of rects) {
      expect(r.x0).toBeGreaterThanOrEqual(0);
      expect(r.x1).toBeLessThanOrEqual(800);
      expect(r.y1).toBeLessThanOrEqual(600);
      expect(r.ticker).toBeTypeOf("string");
    }
    expect(groups.map(g => g.name).sort()).toEqual(["Energy", "Tech"]);
  });
  it("bigger market cap gets bigger area", () => {
    const { tiles: rects } = layout(tiles, 800, 600);
    const area = (t: string) => { const r = rects.find(x => x.ticker === t)!; return (r.x1-r.x0)*(r.y1-r.y0); };
    expect(area("A")).toBeGreaterThan(area("B"));
  });

});
