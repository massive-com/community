import { describe, it, expect, vi, beforeEach } from "vitest";

// Spy on the treemap layout to capture the dimensions it is called with.
vi.mock("../src/treemap.js", () => ({
  layout: vi.fn(() => ({ tiles: [], groups: [] })),
}));

import { renderRegion } from "../src/render.js";
import { layout } from "../src/treemap.js";

// Minimal canvas ctx stub: records scale/translate, ignores everything else.
function fakeCtx() {
  const calls: { scale?: [number, number]; translate?: [number, number] } = {};
  const ctx: any = new Proxy({}, {
    get(_t, prop) {
      if (prop === "scale") return (sx: number, sy: number) => { calls.scale = [sx, sy]; };
      if (prop === "translate") return (x: number, y: number) => { calls.translate = [x, y]; };
      if (prop === "measureText") return () => ({ width: 0 });
      return () => {};
    },
    set() { return true; },
  });
  return { ctx, calls };
}

describe("renderRegion", () => {
  beforeEach(() => { (layout as any).mockClear(); });

  it("lays out at the region size by default", () => {
    const { ctx, calls } = fakeCtx();
    renderRegion(ctx, [], 0, 0, 300, 150);
    expect(layout).toHaveBeenCalledWith([], 300, 150);
    expect(calls.scale).toEqual([1, 1]);
  });

  it("lays out at the supplied layout dims and scales to the region", () => {
    const { ctx, calls } = fakeCtx();
    // region 300x150, but lay out at the live viewport dims 600x300
    renderRegion(ctx, [], 10, 20, 300, 150, 0.06, 600, 300);
    expect(layout).toHaveBeenCalledWith([], 600, 300); // arrangement matches live, not the region
    expect(calls.translate).toEqual([10, 20]);
    expect(calls.scale).toEqual([300 / 600, 150 / 300]); // scaled to fit
  });
});
