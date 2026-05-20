"use client";

import useSWR from "swr";
import { fmtPrice, fmtInt, fmtNanos } from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";
import type { Quote, Trade } from "@/lib/types";
import type { WSTrade, WSQuote } from "@/lib/useFuturesWS";

interface TradesResponse {
  recent_trades: Trade[];
  recent_quotes: Quote[];
}

interface Props {
  ticker: string | null;
  wsTrades?: WSTrade[];
  wsQuotes?: WSQuote[];
  wsConnected?: boolean;
}

export function TimeAndSales({ ticker, wsTrades = [], wsQuotes = [], wsConnected }: Props) {
  const { data, error } = useSWR<TradesResponse>(
    ticker ? `/api/trades/${ticker}` : null,
    fetchJson,
    { refreshInterval: 5_000 }
  );
  const loading = !!ticker && !data && !error;

  const restQuotes = data?.recent_quotes ?? [];
  const fallbackQuote = restQuotes[0];

  // Use WS trades only when connected AND we have fresh trades in the buffer.
  // If WS is connected but hasn't delivered any fresh trades yet (e.g. staging
  // replay was filtered, or market is briefly quiet), fall back to REST snapshot.
  const usingWS = !!wsConnected && wsTrades.length > 0;
  const trades: Array<{ price: number; size: number; timestamp: number; sequence_number?: number }> =
    usingWS ? wsTrades : (data?.recent_trades ?? []);

  // Tape speed across the most recent batch.
  let tps: number | null = null;
  if (trades.length >= 2) {
    const first = trades[0].timestamp;
    const last = trades[trades.length - 1].timestamp;
    const spanSec = (first - last) / 1_000_000_000;
    if (spanSec > 0) tps = (trades.length - 1) / spanSec;
  }
  const tpsLabel =
    tps === null ? "N/A"
    : tps >= 10 ? `${tps.toFixed(0)}/s`
    : tps >= 1 ? `${tps.toFixed(1)}/s`
    : tps >= 0.1 ? `${tps.toFixed(2)}/s`
    : "<0.1/s";
  const tpsHeat =
    tps === null ? "text-zinc-500"
    : tps >= 5 ? "text-emerald-300"
    : tps >= 1 ? "text-amber-300"
    : "text-zinc-400";

  return (
    <section className="terminal-panel rounded-lg overflow-hidden flex flex-col h-full">
      <div className="terminal-panel-header px-3 py-2 border-b border-bg-border flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
          Time & Sales
        </h3>
        <span
          className="text-[10px] font-mono text-zinc-500"
          title="Aggressor color uses the nearest quote at or before each trade timestamp."
        >
          {ticker ?? ""}
        </span>
        {/* Live indicator dot — green when WS active, dim when on REST fallback */}
        {wsConnected !== undefined && ticker && (
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${
              wsConnected ? "bg-accent-green" : "bg-zinc-600"
            }`}
            title={wsConnected ? "Live via WebSocket." : "WebSocket disconnected — REST fallback."}
          />
        )}
        {tps !== null && (
          <span
            className={`ml-auto text-[10px] font-mono tnum ${tpsHeat}`}
            title={`Tape speed: ${trades.length} trades over ${(((trades[0]?.timestamp ?? 0) - (trades[trades.length - 1]?.timestamp ?? 0)) / 1e9).toFixed(1)}s`}
          >
            tape {tpsLabel}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto text-[11px] font-mono tnum">
        {error && (
          <div className="p-3">
            <PanelError compact message={`Trades unavailable: ${errorMessage(error)}`} />
          </div>
        )}
        {!error && trades.length === 0 && (
          <div className="px-3 py-3 text-zinc-500 text-center">
            {loading ? (
              <span className="inline-flex items-center gap-2 font-mono text-[11px]">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
                loading trades...
              </span>
            ) : wsConnected && ticker ? (
              <span className="inline-flex items-center gap-2 font-mono text-[11px]">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
                waiting for trades...
              </span>
            ) : ticker ? (
              "No recent trades."
            ) : (
              "Select a contract."
            )}
          </div>
        )}
        {trades.map((t, i) => {
          // Find the nearest quote at or before this trade's timestamp for aggressor coloring.
          let bid: number | undefined;
          let ask: number | undefined;
          if (usingWS) {
            const q = wsQuotes.find((q) => q.timestamp <= t.timestamp);
            bid = q?.bid_price;
            ask = q?.ask_price;
          } else {
            const q = restQuotes.find((q) => q.timestamp <= t.timestamp);
            bid = q?.bid_price ?? fallbackQuote?.bid_price;
            ask = q?.ask_price ?? fallbackQuote?.ask_price;
          }
          const aggressor =
            typeof bid === "number" && typeof ask === "number"
              ? t.price >= ask ? "buy"
              : t.price <= bid ? "sell"
              : null
              : null;
          return (
            <div
              key={`${t.timestamp}-${t.sequence_number ?? "x"}-${i}`}
              className="flex items-center justify-between px-3 py-1 border-b border-bg-border/30 last:border-b-0"
            >
              <span className="text-zinc-500">{fmtNanos(t.timestamp)}</span>
              <span
                className={
                  aggressor === "buy" ? "text-emerald-300"
                  : aggressor === "sell" ? "text-rose-300"
                  : "text-zinc-100"
                }
              >
                {fmtPrice(t.price)}
              </span>
              <span className="text-zinc-400 w-12 text-right">
                ×{fmtInt(t.size)}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
