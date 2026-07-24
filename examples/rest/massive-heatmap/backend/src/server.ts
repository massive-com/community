import http from "node:http";
import { loadUniverse } from "./universeLoader.js";
import { UniverseState } from "./state.js";
import { sessionPhase } from "./session.js";
import { seedBaselines, type Baseline } from "./seed.js";
import { fetchCurrentPrices } from "./prices.js";
import { isLookback } from "./lookback.js";
import { constituentSegment, type Universe, type Segment } from "../../shared/universe.js";

export interface ServerDeps {
  port: number;
  now?: () => number;
  // Seed baselines for a universe+lookback. Defaults to the real REST seed; tests inject a fake.
  seed?: (u: Universe, lookback: number) => Promise<Record<string, Baseline>>;
  // Current price per ticker. Defaults to the real REST snapshot fetch; tests inject a fake.
  fetchPrices?: (u: Universe) => Promise<Map<string, number>>;
  baselineTtlMs?: number; // prior-close cache lifetime (default 10 min)
  priceTtlMs?: number;    // current-price cache lifetime (default 1 s)
}

// Effective session for a (possibly mixed) universe: equity phase if any equities are
// present, else 24/7 for crypto/forex/etc.
function universeSession(universe: Universe, nowMs: number): ReturnType<typeof sessionPhase> {
  const segs = new Set<Segment>(universe.constituents.map((c) => constituentSegment(universe, c)));
  if (segs.has("stocks") || segs.has("etfs")) return sessionPhase("stocks", nowMs);
  if (segs.size === 1) return sessionPhase([...segs][0], nowMs);
  return "open24";
}

export async function startServer(deps: ServerDeps) {
  const now = deps.now ?? (() => Date.now());
  const seed = deps.seed ?? seedBaselines;
  const fetchPrices = deps.fetchPrices ?? fetchCurrentPrices;
  const baselineTtlMs = deps.baselineTtlMs ?? 10 * 60_000;
  const priceTtlMs = deps.priceTtlMs ?? 1_000;

  // Cache baselines per universe+lookback: prior-close is stable through the trading
  // day, and re-seeding on every prices poll would be wasteful. The TTL refreshes it
  // across a day boundary. The price cache collapses bursts/multiple tabs into at most
  // one upstream call per universe per second.
  // A rare double-fetch on a cold-cache miss is acceptable here; the 1s price cache and the client's interval keep real duplication negligible.
  const baselineCache = new Map<string, { baselines: Record<string, Baseline>; at: number }>();
  const priceCache = new Map<string, { prices: Map<string, number>; at: number }>();

  const getBaselines = async (u: Universe, lookback: number) => {
    const key = `${u.id}:${lookback}`;
    const hit = baselineCache.get(key);
    if (hit && now() - hit.at < baselineTtlMs) return hit.baselines;
    const baselines = await seed(u, lookback);
    baselineCache.set(key, { baselines, at: now() });
    return baselines;
  };
  const getPrices = async (u: Universe) => {
    const hit = priceCache.get(u.id);
    if (hit && now() - hit.at < priceTtlMs) return hit.prices;
    const prices = await fetchPrices(u);
    priceCache.set(u.id, { prices, at: now() });
    return prices;
  };

  const json = (res: http.ServerResponse, status: number, body: unknown) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };

  // Resolve and validate the universe + lookback from the query string.
  const parse = (url: URL): { u: Universe; lb: number } | { error: number; message: string } => {
    const id = url.searchParams.get("universe");
    if (!id) return { error: 400, message: "universe is required" };
    let u: Universe;
    try { u = loadUniverse(id); }
    catch (e) { return { error: 404, message: String(e) }; }
    const raw = Number(url.searchParams.get("lookback") ?? "1");
    // Futures roll across contracts, so a fixed lookback is meaningless: force intraday.
    // universes are single-segment, so the universe segment is authoritative here.
    const lb = u.segment === "futures" ? 1 : isLookback(raw) ? raw : 1;
    return { u, lb };
  };

  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", "http://localhost");

      if (req.method === "GET" && url.pathname === "/api/snapshot") {
        const p = parse(url);
        if ("error" in p) return json(res, p.error, { error: p.message });
        const baselines = await getBaselines(p.u, p.lb);
        const state = new UniverseState(p.u.constituents);
        state.seed(baselines);
        return json(res, 200, {
          universeId: p.u.id, label: p.u.label, segment: p.u.segment,
          session: universeSession(p.u, now()), tiles: state.tiles(),
        });
      }

      if (req.method === "GET" && url.pathname === "/api/prices") {
        const p = parse(url);
        if ("error" in p) return json(res, p.error, { error: p.message });
        const baselines = await getBaselines(p.u, p.lb); // uses the cached baseline; seeds only on a miss
        const prices = await getPrices(p.u);
        const state = new UniverseState(p.u.constituents);
        state.seed(baselines);
        for (const [t, price] of prices) state.applyPrice(t, price);
        return json(res, 200, { session: universeSession(p.u, now()), updates: state.updates() });
      }

      return json(res, 404, { error: "not found" });
    } catch (e) {
      return json(res, 500, { error: String(e) });
    }
  });

  await new Promise<void>((r) => server.listen(deps.port, () => r()));
  return {
    address: () => server.address() as { port: number },
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}
