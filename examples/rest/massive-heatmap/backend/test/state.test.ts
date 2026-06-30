import { describe, it, expect } from "vitest";
import { UniverseState } from "../src/state.js";
import type { Constituent } from "../../shared/universe.js";

const cons: Constituent[] = [
  { ticker: "AAPL", wsSymbol: "AAPL", name: "Apple", group: "Tech", marketCap: 3000 },
  { ticker: "XOM",  wsSymbol: "XOM",  name: "Exxon", group: "Energy", marketCap: 500 },
];

describe("UniverseState", () => {
  it("seeds baselines and computes pct", () => {
    const s = new UniverseState(cons);
    s.seed({ AAPL: { priorClose: 100, price: 100 }, XOM: { priorClose: 50, price: 50 } });
    expect(s.tiles().find((t) => t.ticker === "AAPL")!.pct).toBe(0);
  });

  it("applyPrice updates price and pct", () => {
    const s = new UniverseState(cons);
    s.seed({ AAPL: { priorClose: 100, price: 100 }, XOM: { priorClose: 50, price: 50 } });
    s.applyPrice("AAPL", 110);
    expect(s.updates()).toContainEqual({ ticker: "AAPL", price: 110, pct: 0.1 });
  });

  it("updates() returns one entry per tile", () => {
    const s = new UniverseState(cons);
    s.seed({ AAPL: { priorClose: 100, price: 100 }, XOM: { priorClose: 50, price: 50 } });
    expect(s.updates()).toHaveLength(2);
  });

  it("ignores unknown tickers and never grows", () => {
    const s = new UniverseState(cons);
    s.seed({ AAPL: { priorClose: 100, price: 100 }, XOM: { priorClose: 50, price: 50 } });
    s.applyPrice("ZZZZ", 5);
    expect(s.tiles()).toHaveLength(2);
  });
});
