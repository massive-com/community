import { describe, it, expect } from "vitest";
import { isLookback, windowStartCandidates } from "../src/lookback.js";

describe("isLookback", () => {
  it("accepts valid lookback values", () => {
    expect(isLookback(1)).toBe(true);
    expect(isLookback(30)).toBe(true);
    expect(isLookback(1825)).toBe(true);
  });
  it("rejects invalid lookback values", () => {
    expect(isLookback(2)).toBe(false);
    expect(isLookback("30")).toBe(false);
    expect(isLookback(null)).toBe(false);
    expect(isLookback(undefined)).toBe(false);
    expect(isLookback(0)).toBe(false);
  });
});

describe("windowStartCandidates", () => {
  // Date.UTC(2026, 4, 26) = 2026-05-26T00:00:00Z
  const now = Date.UTC(2026, 4, 26); // 2026-05-26

  it("returns 7 descending consecutive dates starting at (now - 1 day)", () => {
    const candidates = windowStartCandidates(now, 1);
    expect(candidates).toHaveLength(7);
    expect(candidates[0]).toBe("2026-05-25");
    // Each subsequent date should be one day earlier
    for (let i = 1; i < candidates.length; i++) {
      const prev = new Date(candidates[i - 1]).getTime();
      const curr = new Date(candidates[i]).getTime();
      expect(prev - curr).toBe(86_400_000);
    }
  });

  it("the 7 dates are descending from 2026-05-25", () => {
    const candidates = windowStartCandidates(now, 1);
    expect(candidates).toEqual([
      "2026-05-25",
      "2026-05-24",
      "2026-05-23",
      "2026-05-22",
      "2026-05-21",
      "2026-05-20",
      "2026-05-19",
    ]);
  });

  it("365-day lookback yields a date ~1 year earlier", () => {
    const candidates = windowStartCandidates(now, 365);
    // now is 2026-05-26, minus 365 days = 2025-05-26
    expect(candidates[0]).toBe("2025-05-26");
  });

  it("respects custom back parameter", () => {
    const candidates = windowStartCandidates(now, 1, 2);
    expect(candidates).toHaveLength(3); // 0..back inclusive
  });
});
