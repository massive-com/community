import { describe, it, expect } from "vitest";
import { placeTooltip } from "../src/Tooltip.js";

// viewport 1000x800, tooltip 200x100 unless noted
describe("placeTooltip", () => {
  it("sits below-right of the cursor when there is room", () => {
    expect(placeTooltip(100, 100, 200, 100, 1000, 800)).toEqual({ left: 114, top: 114 });
  });

  it("flips to the left of the cursor near the right edge", () => {
    // 950+14+200 = 1164 > 1000 -> flip: 950-14-200 = 736
    expect(placeTooltip(950, 100, 200, 100, 1000, 800).left).toBe(736);
  });

  it("flips above the cursor near the bottom edge", () => {
    // 760+14+100 = 874 > 800 -> flip: 760-14-100 = 646
    expect(placeTooltip(100, 760, 200, 100, 1000, 800).top).toBe(646);
  });

  it("never lets the tooltip exceed the right/bottom margin", () => {
    const { left, top } = placeTooltip(995, 795, 200, 100, 1000, 800);
    expect(left).toBeLessThanOrEqual(1000 - 200 - 8);
    expect(top).toBeLessThanOrEqual(800 - 100 - 8);
  });

  it("clamps to the top-left margin when the tooltip is larger than the space both ways", () => {
    // tiny viewport, big tooltip -> pinned to the margin, never negative
    expect(placeTooltip(10, 10, 400, 300, 200, 150)).toEqual({ left: 8, top: 8 });
  });
});
