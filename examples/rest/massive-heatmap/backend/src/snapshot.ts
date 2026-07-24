import { restClient } from "@massive.com/client-js";
import type { Constituent, Segment } from "../../shared/universe.js";
import { apiKey } from "./env.js";

export interface SnapRow {
  price: number;
  priorClose: number;
  wsSymbol?: string; // front-month contract symbol (futures only), for historical aggs
}

// Snapshot symbol form per segment (matches how the snapshot endpoints key rows).
export function snapshotSymbol(segment: Segment, c: Constituent): string {
  switch (segment) {
    case "crypto": return "X:" + c.wsSymbol.replace(/-/g, "");
    case "forex": return "C:" + c.wsSymbol.replace(/\//g, "");
    case "indices": return c.wsSymbol;
    default: return c.ticker; // stocks, etfs, futures
  }
}

function chunk<T>(arr: T[], n: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}

// Current price + prior close per display ticker, from one asset class's REST snapshot.
// Shared by seed (which also reads priorClose) and the poller (which reads price). For
// futures it resolves the front-month contract and returns its symbol for historical aggs.
export async function fetchSnapshot(
  rest: ReturnType<typeof restClient>,
  segment: Segment,
  constituents: Constituent[],
): Promise<Map<string, SnapRow>> {
  const out = new Map<string, SnapRow>();

  if (segment === "futures") {
    const symToDisplay = new Map(constituents.map((c) => [c.wsSymbol, c.ticker] as const));
    for (const product of [...new Set(constituents.map((c) => c.ticker))]) {
      try {
        const r = await fetch(
          `https://api.massive.com/futures/v1/snapshot?product_code=${encodeURIComponent(product)}&limit=1000`,
          { headers: { Authorization: `Bearer ${apiKey()}` } },
        );
        const d: any = await r.json();
        for (const row of d?.results ?? []) {
          const wsSymbol: string | undefined = row?.details?.ticker;
          const disp = wsSymbol && symToDisplay.get(wsSymbol);
          if (!disp || !wsSymbol) continue;
          const open = row?.session?.open, close = row?.session?.close;
          if (typeof close === "number") {
            out.set(disp, { price: close, priorClose: open > 0 ? open : 0, wsSymbol });
          }
        }
      } catch (e) { console.error("[snapshot] futures failed for", product, e); }
    }
    return out;
  }

  const symToTicker = new Map<string, string>();
  for (const c of constituents) symToTicker.set(snapshotSymbol(segment, c), c.ticker);
  const record = (rows: any[] | undefined, getSym: (r: any) => string) => {
    for (const r of rows ?? []) {
      const ticker = symToTicker.get(getSym(r));
      if (!ticker) continue;
      const priorClose = r?.prevDay?.c ?? r?.session?.previous_close ?? 0;
      const price = r?.lastTrade?.p ?? r?.day?.c ?? r?.value ?? r?.session?.close ?? priorClose;
      out.set(ticker, { price, priorClose });
    }
  };

  for (const part of chunk([...symToTicker.keys()], 100)) {
    try {
      if (segment === "stocks" || segment === "etfs") {
        const res: any = await rest.getStocksSnapshotTickers({ tickers: part.join(",") } as any);
        record(res?.tickers, (r) => r.ticker);
      } else if (segment === "crypto") {
        const res: any = await rest.getCryptoSnapshotTickers({ tickers: part.join(",") } as any);
        record(res?.tickers, (r) => r.ticker);
      } else if (segment === "forex") {
        const res: any = await rest.getForexSnapshotTickers({ tickers: part.join(",") } as any);
        record(res?.tickers, (r) => r.ticker);
      } else if (segment === "indices") {
        const res: any = await rest.getIndicesSnapshot({ tickerAnyOf: part.join(",") });
        record(res?.results, (r) => r.ticker);
      }
    } catch (e) {
      console.error(`[snapshot] failed for ${segment} chunk`, e);
    }
  }

  return out;
}
