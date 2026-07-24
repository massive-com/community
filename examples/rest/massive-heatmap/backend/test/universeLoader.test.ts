import { describe, it, expect } from "vitest";
import { loadUniverse, listUniverseIds } from "../src/universeLoader.js";

describe("universeLoader", () => {
  it("lists shipped universes", () => { expect(listUniverseIds()).toContain("crypto"); });
  it("loads and validates crypto", () => {
    const u = loadUniverse("crypto");
    expect(u.segment).toBe("crypto");
    expect(u.constituents.length).toBeGreaterThan(0);
    expect(u.constituents[0]).toHaveProperty("wsSymbol");
  });
  it("throws on unknown id", () => { expect(() => loadUniverse("nope")).toThrow(); });
});
