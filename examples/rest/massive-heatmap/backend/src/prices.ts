import { restClient } from "@massive.com/client-js";
import type { Universe } from "../../shared/universe.js";
import { groupBySegment } from "./seed.js";
import { fetchSnapshot } from "./snapshot.js";
import { apiKey } from "./env.js";

// Current price per display ticker across every asset class in the universe, via REST
// snapshots. No historical work: the prior-close baseline was set once at seed time.
// One REST snapshot call per asset class (per product code for futures) returns
// every current price.
export async function fetchCurrentPrices(
  universe: Universe,
  rest = restClient(apiKey(), "https://api.massive.com"),
): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  for (const [segment, cons] of groupBySegment(universe)) {
    const snap = await fetchSnapshot(rest, segment, cons);
    for (const [ticker, row] of snap) out.set(ticker, row.price);
  }
  return out;
}
