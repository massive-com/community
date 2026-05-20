"use client";

import useSWR from "swr";
import { useEffect, useRef, useState } from "react";
import {
  fmtPrice,
  fmtPct,
  fmtCompact,
  changeColor,
  fmtInt,
} from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";
import { Skeleton } from "./Skeleton";
import type {
  Snapshot,
  Contract,
  CurveResponse,
  ScheduleEvent,
} from "@/lib/types";
import { detectSizeFromName } from "@/lib/curated-products";
import type { WSTrade, WSQuote } from "@/lib/useFuturesWS";

interface ContractDetail {
  ticker: string;
  snapshot: Snapshot | null;
  contract: Contract | null;
  prior_reference: number | null;
  is_stale: boolean;
  last_trade_age_days: number | null;
}

interface Props {
  productCode: string;
  ticker: string | null;
  curve: CurveResponse | null;
  curveLoading?: boolean;
  onSwitchProduct: (code: string) => void;
  wsLastTrade?: WSTrade | null;
  wsLatestQuote?: WSQuote | null;
  wsConnected?: boolean;
  wsConnectionLimited?: boolean;
}

export function HeroCard({
  productCode,
  ticker,
  curve,
  curveLoading,
  onSwitchProduct,
  wsLastTrade,
  wsLatestQuote,
  wsConnected,
  wsConnectionLimited,
}: Props) {
  const { data, error } = useSWR<ContractDetail>(
    ticker ? `/api/contract/${ticker}` : null,
    fetchJson,
    { refreshInterval: 15_000 }
  );
  // Show loading while the curve is being fetched (so front-month auto-select
  // can fire), or while a ticker is set but its contract data is in flight, or
  // when we have no ticker yet (SSR / initial hydration before the curve
  // resolves the front month).
  const loading = !error && (curveLoading || !ticker || !data);
  const { data: scheduleData } = useSWR<{ events: ScheduleEvent[] }>(
    productCode ? `/api/schedule/${productCode}` : null,
    fetchJson
  );
  const nextEvent = (() => {
    const now = Date.now();
    return (scheduleData?.events ?? []).find(
      (e) => new Date(e.timestamp).getTime() > now
    );
  })();

  const snap = data?.snapshot;
  const session = snap?.session;
  const lastTrade = snap?.last_trade;
  const lastQuote = snap?.last_quote;
  const isStale = !!data?.is_stale;
  const contract = data?.contract;

  // WS price takes priority over REST snapshot when connected, a trade has arrived,
  // and we have a prior_reference loaded (so the change calculation won't flash "No ref").
  const lastFromHistory = null;
  const restPrice = isStale
    ? null
    : (lastTrade?.price ?? session?.close ?? lastFromHistory ?? null);
  const prev = data?.prior_reference;
  const price =
    wsConnected && wsLastTrade && typeof prev === "number" && prev > 0
      ? wsLastTrade.price
      : restPrice;

  let change: number | null = null;
  let changePct: number | null = null;
  if (typeof price === "number" && typeof prev === "number" && prev > 0) {
    change = price - prev;
    changePct = (change / prev) * 100;
  }

  const high = session?.high;
  const low = session?.low;
  const open = session?.open;
  const rangePct =
    typeof price === "number" &&
    typeof high === "number" &&
    typeof low === "number" &&
    high > low
      ? Math.max(0, Math.min(1, (price - low) / (high - low)))
      : null;

  // WS quote takes priority over REST snapshot when connected.
  const bid = wsConnected && wsLatestQuote ? wsLatestQuote.bid_price : lastQuote?.bid;
  const ask = wsConnected && wsLatestQuote ? wsLatestQuote.ask_price : lastQuote?.ask;
  const spread =
    typeof bid === "number" && typeof ask === "number" && ask >= bid
      ? ask - bid
      : null;

  const prevPriceRef = useRef<number | null>(null);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    if (typeof price !== "number") return;
    const prevP = prevPriceRef.current;
    if (prevP !== null && prevP !== price) {
      setFlash(price > prevP ? "up" : "down");
      const id = setTimeout(() => setFlash(null), 700);
      return () => clearTimeout(id);
    }
    prevPriceRef.current = price;
  }, [price]);
  useEffect(() => {
    if (typeof price === "number") prevPriceRef.current = price;
  }, [price]);

  const variants = curve?.variants ?? [];
  const activeSize =
    variants.find((v) => v.code === productCode)?.size ??
    detectSizeFromName(curve?.product?.name);
  const familyLabel = curve?.family_label;
  const productName = curve?.product?.name ?? "";
  const venue = curve?.product?.trading_venue ?? "";
  const timeframe = lastTrade?.timeframe ?? snap?.last_minute?.timeframe;
  const quietProduct = !loading && !error && price === null;

  return (
    <section className="market-hero border-b border-bg-border relative overflow-hidden">
      <div className="absolute inset-0 subtle-grid pointer-events-none opacity-40" />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-blue/70 to-transparent" />
      <div className="relative px-6 pt-5 pb-6 grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-6">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="font-mono text-xl font-bold text-white tracking-tight tnum">
              {ticker ?? <Skeleton className="h-5" width="5rem" />}
            </h2>
            {familyLabel && (
              <span className="text-xs text-zinc-300">{familyLabel}</span>
            )}
            {variants.length > 1 ? (
              <div className="flex items-center bg-bg-elev border border-bg-edge rounded-md p-0.5 ml-1">
                {variants.map((v) => (
                  <button
                    key={v.code}
                    onClick={() => onSwitchProduct(v.code)}
                    className={`px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider rounded-sm transition-colors ${
                      v.code === productCode
                        ? "bg-accent-blue/20 text-accent-blue"
                        : "text-zinc-500 hover:text-zinc-200"
                    }`}
                    title={v.name ?? v.code}
                  >
                    {v.size === "micro"
                      ? "Micro"
                      : v.size === "e-mini"
                        ? "E-mini"
                        : v.size === "mini"
                          ? "Mini"
                          : "Std"}
                  </button>
                ))}
              </div>
            ) : (
              <span
                className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-bg-elev border border-bg-edge text-zinc-400"
                title="Contract size class. Most CME products also list E-mini and Micro siblings; this product has only the size shown."
              >
                {activeSize === "micro"
                  ? "Micro"
                  : activeSize === "e-mini"
                    ? "E-mini"
                    : activeSize === "mini"
                      ? "Mini"
                      : "Standard"}
              </span>
            )}
            {wsConnected ? (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider bg-accent-green/15 text-accent-green border border-accent-green/30"
                title="Price and bid/ask streaming live via WebSocket. Session stats (volume, range) poll every 15s via REST."
              >
                RT · WS
              </span>
            ) : wsConnectionLimited ? (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider bg-amber-500/10 text-amber-300 border border-amber-500/30"
                title="WebSocket connection limit reached on this account. Falling back to REST polling. Retrying in ~2 min."
              >
                WS limit · REST
              </span>
            ) : (
              timeframe && !isStale && (
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider ${
                    timeframe === "REAL-TIME"
                      ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                      : "bg-amber-500/10 text-amber-300 border border-amber-500/30"
                  }`}
                  title={
                    timeframe === "REAL-TIME"
                      ? "Real-time data delivery (REST snapshot polled every 15s). Not a streaming WebSocket."
                      : "Delayed data (typically 10-15 min) from REST snapshot, polled every 15s."
                  }
                >
                  {timeframe === "REAL-TIME" ? "RT · REST" : "DELAYED · REST"}
                </span>
              )
            )}
            {!wsConnected && (
              <span
                className="text-[10px] font-mono text-zinc-500"
                title="Snapshot polls every 15 seconds. Watchlist polls every 30 seconds. Term structure polls every 60 seconds."
              >
                ↻ 15s
              </span>
            )}
            {isStale && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider bg-zinc-700/40 text-zinc-400 border border-zinc-700">
                no recent activity
              </span>
            )}
            {quietProduct && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wider bg-amber-500/10 text-amber-300 border border-amber-500/30">
                quiet product
              </span>
            )}
          </div>
          <div
            className="text-[11px] text-zinc-500 mt-0.5 truncate"
            title={productName}
          >
            {productName} · {venue}
          </div>

          {error && (
            <div className="mt-3">
              <PanelError
                message={`Contract data unavailable: ${errorMessage(error)}`}
              />
            </div>
          )}

          <div className="mt-4 flex items-baseline gap-3 flex-wrap">
            {loading ? (
              <>
                <Skeleton className="h-12" width="14rem" />
                <Skeleton className="h-5" width="6rem" />
                <Skeleton className="h-5" width="4rem" />
              </>
            ) : (
              <>
                <div
                  className={`font-mono text-5xl font-bold tracking-tight tnum px-1 -mx-1 rounded ${
                    quietProduct ? "text-zinc-300 text-3xl" : "text-white"
                  } ${
                    flash === "up"
                      ? "animate-flashGreen"
                      : flash === "down"
                        ? "animate-flashRed"
                        : ""
                  }`}
                >
                  {quietProduct ? "No recent tick" : fmtPrice(price)}
                </div>
                {!quietProduct && (
                  <>
                    <div className={`font-mono text-base ${changeColor(change)}`}>
                      {change !== null
                        ? `${change >= 0 ? "▲ +" : "▼ "}${fmtPrice(Math.abs(change))}`
                        : "No ref"}
                    </div>
                    <div
                      className={`font-mono text-base font-semibold ${changeColor(changePct)}`}
                    >
                      {changePct === null ? "No ref" : fmtPct(changePct)}
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 text-xs font-mono tnum">
            <KV
              label="Bid"
              value={loading ? null : quietProduct ? "No bid" : fmtPrice(bid)}
              accent="text-emerald-300"
            />
            <KV
              label="Ask"
              value={loading ? null : quietProduct ? "No ask" : fmtPrice(ask)}
              accent="text-rose-300"
            />
            <KV
              label="Spread"
              value={loading ? null : quietProduct ? "No spread" : fmtPrice(spread)}
            />
            <KV
              label="Open"
              value={loading ? null : quietProduct ? "No open" : fmtPrice(open)}
            />
          </div>

          {/* day range bar */}
          {loading ? (
            <div className="mt-4">
              <Skeleton className="h-1.5 block" width="100%" />
            </div>
          ) : (
            typeof low === "number" &&
            typeof high === "number" && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 tnum mb-1">
                  <span>L {fmtPrice(low)}</span>
                  <span className="text-zinc-600">day range</span>
                  <span>H {fmtPrice(high)}</span>
                </div>
                <div className="relative h-1.5 bg-bg-deep border border-bg-edge rounded-full overflow-hidden">
                  <div className="absolute inset-y-0 left-0 right-0 bg-gradient-to-r from-emerald-500/20 via-zinc-500/10 to-rose-500/20 opacity-60" />
                  {rangePct !== null && (
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.6)]"
                      style={{ left: `${rangePct * 100}%` }}
                    />
                  )}
                </div>
              </div>
            )
          )}

          {nextEvent && (
            <div className="mt-3 text-[10px] font-mono text-zinc-500">
              Next session{" "}
              <span className="text-zinc-300">{nextEvent.event}</span> at{" "}
              <span className="text-zinc-300">
                {new Date(nextEvent.timestamp).toLocaleString(undefined, {
                  weekday: "short",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 content-start">
          <Stat
            label="Session Volume"
            value={
              loading
                ? null
                : typeof session?.volume === "number"
                  ? fmtCompact(session.volume)
                  : "No volume"
            }
            accent="text-zinc-100"
          />
          <Stat
            label="Open Interest"
            value={
              loading
                ? null
                : typeof snap?.details?.open_interest === "number"
                  ? fmtCompact(snap.details.open_interest)
                  : "Not returned"
            }
            sub={
              loading
                ? undefined
                : typeof snap?.details?.open_interest === "number"
                  ? "outstanding contracts"
                  : "snapshot field absent"
            }
          />
          <Stat
            label="Expires In"
            value={
              loading
                ? null
                : contract?.days_to_maturity !== undefined
                  ? `${contract.days_to_maturity} days`
                  : "No spec"
            }
            sub={loading ? undefined : contract?.settlement_date ?? undefined}
          />
          <Stat
            label="Tick Size"
            value={
              loading
                ? null
                : contract?.trade_tick_size !== undefined
                  ? fmtPrice(contract.trade_tick_size)
                  : "No spec"
            }
            sub={
              loading
                ? undefined
                : curve?.multiplier && contract?.trade_tick_size
                  ? `$${(curve.multiplier * contract.trade_tick_size).toFixed(2)} per tick`
                  : undefined
            }
          />
          <Stat
            label="Multiplier"
            value={
              loading
                ? null
                : curve?.multiplier
                  ? `${fmtInt(curve.multiplier)}× ${curve.unit ?? ""}`.trim()
                  : "No spec"
            }
            sub={loading ? undefined : activeSize ? sizeLabel(activeSize) : undefined}
            wide
          />
        </div>
      </div>
    </section>
  );
}

function sizeLabel(size: string): string {
  if (size === "micro") return "Micro contract";
  if (size === "e-mini") return "E-mini contract";
  if (size === "mini") return "Mini contract";
  return "Standard contract";
}

function KV({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | null;
  accent?: string;
}) {
  return (
    <div className="flex items-baseline gap-1.5 min-w-0">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">
        {label}
      </span>
      {value === null ? (
        <Skeleton className="h-3" width="3rem" />
      ) : (
        <span className={`truncate ${accent ?? "text-zinc-200"}`}>{value}</span>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  accent,
  wide,
}: {
  label: string;
  value: string | null;
  sub?: string;
  accent?: string;
  wide?: boolean;
}) {
  return (
    <div
      className={`bg-bg-elev/60 border border-bg-edge rounded-md px-3 py-2 ${
        wide ? "col-span-2" : ""
      }`}
    >
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">
        {label}
      </div>
      {value === null ? (
        <Skeleton className="h-4 mt-1" width="5rem" />
      ) : (
        <div
          className={`font-mono text-sm tnum mt-0.5 ${accent ?? "text-zinc-100"}`}
        >
          {value}
        </div>
      )}
      {sub && <div className="text-[10px] text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}
