import { describe, it, expect, vi } from "vitest";

// Spy on renderRegion so we can assert what dimensions the export lays out at.
vi.mock("../src/render.js", () => ({
  renderRegion: vi.fn(() => ({ tiles: [], groups: [] })),
  FONT: "sans-serif",
}));

import { renderExport, fitRect, type ExportMeta } from "../src/capture.js";
import { renderRegion } from "../src/render.js";

// Canvas/ctx stub: every method is a no-op; the few that must return objects do.
function fakeCanvas(): HTMLCanvasElement {
  const ctx: any = new Proxy({}, {
    get(_t, p) {
      if (p === "measureText") return () => ({ width: 0 });
      if (p === "createLinearGradient") return () => ({ addColorStop() {} });
      return () => {};
    },
    set() { return true; },
  });
  return { getContext: () => ctx, width: 0, height: 0 } as unknown as HTMLCanvasElement;
}

const META: ExportMeta = {
  title: "Stocks S&P 500", sessionLabel: "Market open", dateStr: "June 30, 2026", lookbackLabel: "1 Day",
};

describe("fitRect", () => {
  it("returns the whole box when the aspect already matches", () => {
    expect(fitRect(300, 150, 2)).toEqual({ x: 0, y: 0, w: 300, h: 150 });
  });
  it("pillarboxes (centers horizontally) when content is taller than the box", () => {
    expect(fitRect(300, 150, 1)).toEqual({ x: 75, y: 0, w: 150, h: 150 });
  });
  it("letterboxes (centers vertically) when content is wider than the box", () => {
    expect(fitRect(300, 150, 3)).toEqual({ x: 0, y: 25, w: 300, h: 100 });
  });
  it("is defensive against zero/negative inputs", () => {
    expect(fitRect(300, 150, 0)).toEqual({ x: 0, y: 0, w: 300, h: 150 });
  });
});

describe("renderExport", () => {
  it("lays the heatmap out at the live viewport dims so the arrangement matches the screen", () => {
    (renderRegion as any).mockClear();
    renderExport(fakeCanvas(), [], META, undefined, 0.06, 1900, 950);
    expect(renderRegion).toHaveBeenCalledTimes(1);
    // renderRegion(ctx, tiles, x, y, w, h, clamp, layoutW, layoutH)
    const [, , , , w, h, , layoutW, layoutH] = (renderRegion as any).mock.calls[0];
    expect(layoutW).toBe(1900);
    expect(layoutH).toBe(950);
    // placed region keeps the viewport aspect -> uniform scale, no skew
    expect(w / h).toBeCloseTo(1900 / 950, 5);
  });

  it("falls back to filling the region when no viewport dims are given", () => {
    (renderRegion as any).mockClear();
    renderExport(fakeCanvas(), [], META, undefined, 0.06);
    const call = (renderRegion as any).mock.calls[0];
    // region is 1512 x 716 (1600/900 frame less padding), no layout dims passed
    expect(call[4]).toBe(1512);
    expect(call[5]).toBe(716);
    expect(call[7]).toBeUndefined();
  });
});
