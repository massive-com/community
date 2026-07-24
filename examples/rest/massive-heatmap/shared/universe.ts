export type Segment = "stocks" | "etfs" | "crypto" | "forex" | "futures" | "indices";

export interface Constituent {
  ticker: string;     // display symbol, e.g. "AAPL"
  wsSymbol: string;   // subscription symbol, e.g. "AAPL", "BTC-USD", "EUR/USD"
  name: string;
  group: string;      // GICS sector (stocks/etfs) or category (others)
  marketCap: number;  // sizing weight; arbitrary positive units for non-equities
  segment?: Segment;  // per-constituent asset class; defaults to Universe.segment
}

export interface Universe {
  id: string;
  segment: Segment;   // default segment for constituents that omit their own
  label: string;
  constituents: Constituent[];
}

// Effective asset class for a constituent: its own segment, else the universe default.
export function constituentSegment(universe: Universe, c: Constituent): Segment {
  return c.segment ?? universe.segment;
}
