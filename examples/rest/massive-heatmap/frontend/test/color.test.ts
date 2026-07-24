import { describe, it, expect } from "vitest";
import { pctColor, pctTextColor, clampForLookback } from "../src/color.js";

describe("pctColor", () => {
  it("zero is neutral grey", () => { expect(pctColor(0)).toBe("rgb(42, 49, 58)"); });
  it("strong positive clamps to full green", () => { expect(pctColor(0.10)).toBe(pctColor(0.06)); });
  it("strong negative clamps to full red", () => { expect(pctColor(-0.10)).toBe(pctColor(-0.06)); });
  it("positive is greener than neutral", () => { expect(pctColor(0.02)).not.toBe(pctColor(0)); });
  it("clamp parameter: same pct saturates at small clamp but is mid-scale at large clamp", () => {
    // 0.08 is beyond the default 0.06 clamp, so it saturates to full green.
    // With clamp=0.20 (30D), 0.08 is only 40% of the way to full green.
    const saturated = pctColor(0.08, 0.06);   // clamps to max green
    const midScale  = pctColor(0.08, 0.20);   // partial green
    expect(saturated).toBe(pctColor(0.06, 0.06)); // same as full-green boundary
    expect(saturated).not.toBe(midScale);          // different colors
    expect(midScale).not.toBe("rgb(42, 49, 58)"); // not neutral either
  });
});

describe("pctTextColor", () => {
  it("stays full-brightness for tiny moves (unlike the tile scale)", () => {
    // -0.41% is near-neutral on the tile scale but must read clearly as red text.
    expect(pctTextColor(-0.0041)).toBe("#F87171");
    expect(pctTextColor(0.0041)).toBe("#22C55E");
  });
  it("colors by sign regardless of magnitude", () => {
    expect(pctTextColor(0.5)).toBe(pctTextColor(0.0001));
    expect(pctTextColor(-0.5)).toBe(pctTextColor(-0.0001));
  });
  it("zero is muted, not green or red", () => {
    expect(pctTextColor(0)).toBe("#9AA4B2");
  });
});

describe("clampForLookback", () => {
  it("returns 0.06 for 1-day lookback", () => { expect(clampForLookback(1)).toBe(0.06); });
  it("returns 0.20 for 30-day lookback", () => { expect(clampForLookback(30)).toBe(0.20); });
  it("returns 3.0 for 5-year lookback", () => { expect(clampForLookback(1825)).toBe(3.0); });
  it("falls back to 0.06 for unknown lookback", () => { expect(clampForLookback(999)).toBe(0.06); });
});
