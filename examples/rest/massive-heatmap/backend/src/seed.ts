import { restClient } from "@massive.com/client-js";
import type { Universe, Constituent, Segment } from "../../shared/universe.js";
import { constituentSegment } from "../../shared/universe.js";
import { apiKey } from "./env.js";
import { windowStartCandidates } from "./lookback.js";
import { fetchSnapshot, snapshotSymbol } from "./snapshot.js";

export interface Baseline { priorClose: number; price: number; }

export function groupBySegment(universe: Universe): Map<Segment, Constituent[]> {
  const groups = new Map<Segment, Constituent[]>();
  for (const c of universe.constituents) {
    const seg = constituentSegment(universe, c);
    const arr = groups.get(seg);
    if (arr) arr.push(c); else groups.set(seg, [c]);
  }
  return groups;
}

// Fetch grouped daily bars for one date, returns ticker -> close map.
// locale: "us" for stocks/etfs, "global" for crypto/forex.
// market: "stocks", "crypto", or "fx".
async function fetchGroupedBaselines(
  locale: string,
  market: string,
  date: string,
): Promise<Map<string, number>> {
  const url = `https://api.massive.com/v2/aggs/grouped/locale/${locale}/market/${market}/${date}?adjusted=true`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${apiKey()}` } });
  const d: any = await r.json();
  const map = new Map<string, number>();
  for (const row of d?.results ?? []) {
    if (row?.T && typeof row.c === "number") map.set(row.T as string, row.c as number);
  }
  return map;
}

// Walk candidates until we find a non-empty grouped result.
async function findGroupedBaselines(
  locale: string,
  market: string,
  candidates: string[],
): Promise<Map<string, number>> {
  for (const date of candidates) {
    try {
      const map = await fetchGroupedBaselines(locale, market, date);
      if (map.size > 0) return map;
    } catch (e) {
      console.error(`[seed] grouped ${locale}/${market}/${date} failed:`, e);
    }
  }
  return new Map();
}

async function seedSegment(
  rest: ReturnType<typeof restClient>,
  segment: Segment,
  constituents: Constituent[],
  lookback: number,
  now: () => number,
): Promise<Record<string, Baseline>> {
  const out: Record<string, Baseline> = {};

  if (segment === "futures") {
    // Front-month contract + current session open/close per display ticker.
    const snap = await fetchSnapshot(rest, "futures", constituents);

    if (lookback === 1) {
      // Intraday open->close (futures lack a reliable prior settlement). priorClose is
      // the session open, already gated to >0 by the snapshot helper.
      for (const [disp, row] of snap) {
        if (row.priorClose > 0) out[disp] = { priorClose: row.priorClose, price: row.price };
      }
      return out;
    }

    // lookback > 1: session close at the window start for the front-month contract.
    // Long windows (1Y/5Y) often return nothing because the current contract did not
    // trade then; those tiles are left unseeded (neutral) rather than faked.
    const candidates = windowStartCandidates(now(), lookback);
    const from = candidates[candidates.length - 1];
    const to = candidates[0];
    for (const [disp, row] of snap) {
      const wsSym = row.wsSymbol;
      if (!wsSym) continue;
      try {
        const url = `https://api.massive.com/futures/v1/aggs/${encodeURIComponent(wsSym)}`
          + `?resolution=1session&window_start.gte=${from}&window_start.lte=${to}`
          + `&sort=window_start.desc&limit=1`;
        const r = await fetch(url, { headers: { Authorization: `Bearer ${apiKey()}` } });
        const d: any = await r.json();
        const bar = d?.results?.[0];
        if (bar && typeof bar.close === "number" && bar.close > 0) {
          out[disp] = { priorClose: bar.close, price: row.price };
        }
      } catch (e) { console.error("[seed] futures aggs failed for", wsSym, e); }
    }
    return out;
  }

  // Current snapshot: price for every lookback, prior close for the lookback=1 baseline.
  const snap = await fetchSnapshot(rest, segment, constituents);
  const currentPrice = new Map<string, number>();
  const priorCloseFromSnapshot = new Map<string, number>();
  for (const [ticker, row] of snap) {
    currentPrice.set(ticker, row.price);
    if (row.priorClose > 0) priorCloseFromSnapshot.set(ticker, row.priorClose);
  }

  if (lookback === 1) {
    // Use prior close from snapshot as the baseline.
    for (const ticker of currentPrice.keys()) {
      const priorClose = priorCloseFromSnapshot.get(ticker);
      const price = currentPrice.get(ticker)!;
      if (priorClose && priorClose > 0) out[ticker] = { priorClose, price };
    }
    return out;
  }

  // lookback > 1: fetch historical grouped bars for the window-start date.
  const candidates = windowStartCandidates(now(), lookback);

  if (segment === "indices") {
    // Per-ticker daily agg for small universes.
    for (const c of constituents) {
      const ticker = c.ticker;
      const price = currentPrice.get(ticker);
      if (price === undefined) continue;
      const from = candidates[0];
      // to = from + 5 days to ensure a bar is returned even for weekend starts.
      const toMs = new Date(from).getTime() + 5 * 86_400_000;
      const to = new Date(toMs).toISOString().slice(0, 10);
      try {
        const url = `https://api.massive.com/v2/aggs/ticker/${encodeURIComponent(c.wsSymbol)}/range/1/day/${from}/${to}?adjusted=true&sort=asc&limit=1`;
        const r = await fetch(url, { headers: { Authorization: `Bearer ${apiKey()}` } });
        const d: any = await r.json();
        const bar = d?.results?.[0];
        if (bar && typeof bar.c === "number") {
          out[ticker] = { priorClose: bar.c, price };
        }
      } catch (e) {
        console.error(`[seed] per-ticker agg failed for ${c.wsSymbol}:`, e);
      }
    }
    return out;
  }

  // stocks, etfs, crypto, forex: use grouped daily (one call, all tickers).
  let locale: string;
  let market: string;

  if (segment === "stocks" || segment === "etfs") {
    locale = "us";
    market = "stocks";
  } else if (segment === "crypto") {
    locale = "global";
    market = "crypto";
  } else {
    // forex
    locale = "global";
    market = "fx";
  }

  const groupedMap = await findGroupedBaselines(locale, market, candidates);

  // Map each grouped bar (keyed by snapshot symbol form) back to its display ticker.
  const symToTicker = new Map<string, string>();
  for (const c of constituents) symToTicker.set(snapshotSymbol(segment, c), c.ticker);

  for (const [symKey, ticker] of symToTicker) {
    const price = currentPrice.get(ticker);
    if (price === undefined) continue;
    // grouped bar T field uses the same snapshot symbol form (plain ticker for stocks/etfs,
    // X:... for crypto, C:... for forex).
    const historicalClose = groupedMap.get(symKey);
    if (historicalClose !== undefined && historicalClose > 0) {
      out[ticker] = { priorClose: historicalClose, price };
    }
    // Tickers with no historical close are left unseeded (they start neutral).
  }

  return out;
}

export async function seedBaselines(
  universe: Universe,
  lookback = 1,
  now = () => Date.now(),
): Promise<Record<string, Baseline>> {
  const rest = restClient(apiKey(), "https://api.massive.com");
  const out: Record<string, Baseline> = {};
  for (const [segment, constituents] of groupBySegment(universe)) {
    Object.assign(out, await seedSegment(rest, segment, constituents, lookback, now));
  }
  return out;
}
