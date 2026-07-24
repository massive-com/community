import { describe, it, expect } from "vitest";
import { groupBySegment } from "../src/seed.js";
import type { Universe } from "../../shared/universe.js";

const mixed: Universe = {
  id: "custom", segment: "stocks", label: "Mix",
  constituents: [
    { ticker: "AAPL", wsSymbol: "AAPL", name: "Apple", group: "Stocks", marketCap: 1, segment: "stocks" },
    { ticker: "BTC", wsSymbol: "BTC-USD", name: "Bitcoin", group: "Crypto", marketCap: 1, segment: "crypto" },
    { ticker: "MSFT", wsSymbol: "MSFT", name: "Microsoft", group: "Stocks", marketCap: 1, segment: "stocks" },
  ],
};

describe("groupBySegment", () => {
  it("buckets constituents by effective segment", () => {
    const g = groupBySegment(mixed);
    expect([...g.keys()].sort()).toEqual(["crypto", "stocks"]);
    expect(g.get("stocks")!.map(c => c.ticker)).toEqual(["AAPL", "MSFT"]);
    expect(g.get("crypto")!.map(c => c.ticker)).toEqual(["BTC"]);
  });
  it("falls back to universe.segment when constituent omits it", () => {
    const single: Universe = { id: "sp500", segment: "stocks", label: "S&P",
      constituents: [{ ticker: "AAPL", wsSymbol: "AAPL", name: "Apple", group: "Tech", marketCap: 1 }] };
    expect([...groupBySegment(single).keys()]).toEqual(["stocks"]);
  });
});
