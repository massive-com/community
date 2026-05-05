"use client";

import useSWR from "swr";
import { fmtPrice, fmtInt, fmtNanos } from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";
import type { Quote, Snapshot, Trade } from "@/lib/types";

interface ContractDetail {
  snapshot: Snapshot | null;
  recent_trades: Trade[];
  recent_quotes: Quote[];
}

interface Props {
  ticker: string | null;
}

export function TimeAndSales({ ticker }: Props) {
  const { data, error } = useSWR<ContractDetail>(
    ticker ? `/api/contract/${ticker}` : null,
    fetchJson,
    { refreshInterval: 15_000 }
  );
  const loading = !!ticker && !data && !error;

  const trades = data?.recent_trades ?? [];
  const quotes = data?.recent_quotes ?? [];
  const fallbackQuote = data?.snapshot?.last_quote;

  // Tape speed: trades-per-second across the most recent batch.
  let tps: number | null = null;
  if (trades.length >= 2) {
    const first = trades[0].timestamp;
    const last = trades[trades.length - 1].timestamp;
    const spanSec = (first - last) / 1_000_000_000;
    if (spanSec > 0) {
      tps = (trades.length - 1) / spanSec;
    }
  }
  const tpsLabel =
    tps === null
      ? "N/A"
      : tps >= 10
        ? `${tps.toFixed(0)}/s`
        : tps >= 1
          ? `${tps.toFixed(1)}/s`
          : tps >= 0.1
            ? `${tps.toFixed(2)}/s`
            : "<0.1/s";
  const tpsHeat =
    tps === null
      ? "text-zinc-500"
      : tps >= 5
        ? "text-emerald-300"
        : tps >= 1
          ? "text-amber-300"
          : "text-zinc-400";

  return (
    <section className="terminal-panel rounded-lg overflow-hidden flex flex-col h-full">
      <div className="terminal-panel-header px-3 py-2 border-b border-bg-border flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
          Time & Sales
        </h3>
        <span
          className="text-[10px] font-mono text-zinc-500"
          title="Aggressor color uses the nearest available quote at or before each trade timestamp."
        >
          {ticker ?? ""}
        </span>
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
            <PanelError
              compact
              message={`Trades unavailable: ${errorMessage(error)}`}
            />
          </div>
        )}
        {!error && trades.length === 0 && (
          <div className="px-3 py-3 text-zinc-500 text-center">
            {loading ? (
              <span className="inline-flex items-center gap-2 font-mono text-[11px]">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
                loading trades...
              </span>
            ) : ticker ? (
              "No recent trades."
            ) : (
              "Select a contract."
            )}
          </div>
        )}
        {trades.map((t, i) => {
          const quote = quotes.find((q) => q.timestamp <= t.timestamp);
          const bid = quote?.bid_price ?? fallbackQuote?.bid;
          const ask = quote?.ask_price ?? fallbackQuote?.ask;
          const aggressor =
            typeof bid === "number" &&
            typeof ask === "number"
              ? t.price >= ask
                ? "buy"
                : t.price <= bid
                  ? "sell"
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
                  aggressor === "buy"
                    ? "text-emerald-300"
                    : aggressor === "sell"
                      ? "text-rose-300"
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
