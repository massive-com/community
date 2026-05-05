"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { fmtUSDFull, fmtInt } from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";
import type { CurveResponse, Snapshot } from "@/lib/types";

interface ContractDetail {
  snapshot: Snapshot | null;
  contract: { trade_tick_size?: number } | null;
  is_stale: boolean;
}

interface Props {
  productCode: string;
  ticker: string | null;
  curve: CurveResponse | null;
  curveLoading?: boolean;
  onSwitchProduct: (code: string) => void;
}

export function PositionSizer({
  productCode,
  ticker,
  curve,
  curveLoading,
  onSwitchProduct,
}: Props) {
  const { data, error } = useSWR<ContractDetail>(
    ticker ? `/api/contract/${ticker}` : null,
    fetchJson,
    { refreshInterval: 30_000 }
  );
  const loading =
    (curveLoading || (!!ticker && !data)) && !error;

  const snap = data?.snapshot;
  const last = snap?.last_trade?.price ?? snap?.session?.close ?? null;
  const price = data?.is_stale ? null : last;
  const multiplier = curve?.multiplier ?? null;
  const tickSize = data?.contract?.trade_tick_size ?? null;

  const [contracts, setContracts] = useState<number>(1);
  const [targetUSD, setTargetUSD] = useState<string>("");

  useEffect(() => {
    if (typeof price === "number" && typeof multiplier === "number") {
      const notional = price * multiplier * contracts;
      setTargetUSD(formatNotionalInput(notional));
    }
  }, [contracts, price, multiplier]);

  function handleTargetChange(s: string) {
    setTargetUSD(s);
    const cleaned = s.replace(/[^0-9.]/g, "");
    const target = parseFloat(cleaned);
    if (
      !isFinite(target) ||
      target <= 0 ||
      typeof price !== "number" ||
      typeof multiplier !== "number" ||
      multiplier <= 0
    ) {
      return;
    }
    const perContract = price * multiplier;
    const n = Math.max(1, Math.round(target / perContract));
    setContracts(n);
  }

  const notionalPerContract =
    typeof price === "number" && typeof multiplier === "number"
      ? price * multiplier
      : null;
  const notionalTotal =
    notionalPerContract !== null ? notionalPerContract * contracts : null;
  const tickValue =
    typeof tickSize === "number" && typeof multiplier === "number"
      ? tickSize * multiplier
      : null;
  const onePtPnl = typeof multiplier === "number" ? multiplier : null;

  const variants = curve?.variants ?? [];
  const activeVariant = variants.find((v) => v.code === productCode);
  const otherVariants = variants.filter((v) => v.code !== productCode);

  // FX clarity: when the unit_of_measure is a currency code other than USD, the
  // notional represents foreign-currency exposure (the contract is quoted in
  // USD per unit of that currency). Surface the exposure side.
  const FX_CURRENCIES = new Set([
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "NZD",
    "MXN",
    "BRL",
    "ZAR",
    "RUB",
    "PLN",
    "SEK",
    "NOK",
    "DKK",
    "CZK",
    "HUF",
    "ILS",
    "INR",
    "KRW",
  ]);
  const unit = curve?.unit ?? null;
  const isFxContract = !!unit && FX_CURRENCIES.has(unit);
  const fxExposure =
    isFxContract && typeof multiplier === "number"
      ? multiplier * contracts
      : null;

  function equivalentContracts(siblingMultiplier: number | null): number | null {
    if (
      typeof notionalTotal !== "number" ||
      typeof siblingMultiplier !== "number" ||
      typeof price !== "number" ||
      siblingMultiplier <= 0
    ) {
      return null;
    }
    return Math.max(1, Math.round(notionalTotal / (price * siblingMultiplier)));
  }

  return (
    <div className="terminal-panel rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Position Sizing
        </h3>
        {activeVariant && (
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
            {productCode} ·{" "}
            {typeof multiplier === "number"
              ? `1× = ${fmtInt(multiplier)} ${curve?.unit ?? ""}`.trim()
              : "spec pending"}
          </span>
        )}
      </div>

      {error && (
        <PanelError
          compact
          message={`Sizing data unavailable: ${errorMessage(error)}`}
        />
      )}

      {loading && (
        <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-500">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
          loading sizing data...
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <label className="text-[10px] uppercase tracking-wider text-zinc-500">
          Contracts
          <input
            type="number"
            min={1}
            step={1}
            value={contracts}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              if (isFinite(n) && n > 0) setContracts(n);
            }}
            className="mt-1 w-full px-2 py-1.5 bg-bg-deep border border-bg-edge rounded font-mono text-base text-zinc-100 focus:outline-none focus:border-accent-blue tnum"
          />
        </label>
        <label className="text-[10px] uppercase tracking-wider text-zinc-500">
          Target Notional
          <input
            type="text"
            value={targetUSD}
            onChange={(e) => handleTargetChange(e.target.value)}
            placeholder="e.g. 100000"
            className="mt-1 w-full px-2 py-1.5 bg-bg-deep border border-bg-edge rounded font-mono text-base text-zinc-100 focus:outline-none focus:border-accent-blue tnum"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-2 mt-1">
        <Cell
          label="Total Notional (USD)"
          value={
            loading ? null : notionalTotal === null ? "No price" : fmtUSDFull(notionalTotal)
          }
          big
          accent="text-zinc-50"
          sub={
            !loading && isFxContract && fxExposure !== null
              ? `${fmtInt(fxExposure)} ${unit} exposure`
              : undefined
          }
        />
        <Cell
          label="Per Contract"
          value={
            loading
              ? null
              : notionalPerContract === null
                ? "No price"
                : fmtUSDFull(notionalPerContract)
          }
          accent="text-zinc-200"
          sub={
            !loading && isFxContract && typeof multiplier === "number"
              ? `${fmtInt(multiplier)} ${unit}`
              : undefined
          }
        />
        <Cell
          label="Tick Value"
          value={loading ? null : tickValue === null ? "No spec" : fmtUSDFull(tickValue)}
        />
        <Cell
          label="P&L per 1pt"
          value={loading ? null : onePtPnl === null ? "No spec" : fmtUSDFull(onePtPnl)}
          sub={
            !loading && typeof multiplier === "number"
              ? `× ${contracts} = ${fmtUSDFull(onePtPnl ? onePtPnl * contracts : null)}`
              : undefined
          }
        />
      </div>

      {otherVariants.length > 0 && (
        <div className="border-t border-bg-border pt-3">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">
            Same notional in other sizes
          </div>
          <div className="flex flex-col gap-1.5">
            {otherVariants.map((v) => {
              const eq = equivalentContracts(v.multiplier);
              return (
                <button
                  key={v.code}
                  onClick={() => {
                    if (eq !== null) setContracts(eq);
                    onSwitchProduct(v.code);
                  }}
                  className="flex items-center justify-between text-left bg-bg-deep border border-bg-edge rounded px-2.5 py-1.5 hover:border-accent-blue transition-colors group"
                  title={v.name ?? v.code}
                >
                  <span className="font-mono text-xs text-zinc-300 group-hover:text-white">
                    {v.code}
                    <span className="ml-2 text-[10px] uppercase tracking-wider text-zinc-500">
                      {v.size}
                    </span>
                  </span>
                  <span className="font-mono text-xs tnum text-zinc-100">
                    {eq !== null ? `${fmtInt(eq)}×` : "No price"}
                    <span className="ml-2 text-[10px] text-zinc-500">
                      {v.multiplier
                        ? `1× = ${fmtInt(v.multiplier)} ${v.unit ?? ""}`.trim()
                        : ""}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {price === null && (
        <div className="text-[11px] text-zinc-500 italic">
          Live price unavailable. Sizing values update once the contract trades.
        </div>
      )}
    </div>
  );
}

function formatNotionalInput(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return Math.round(n).toString();
}

function Cell({
  label,
  value,
  big,
  accent,
  sub,
}: {
  label: string;
  value: string | null;
  big?: boolean;
  accent?: string;
  sub?: string;
}) {
  return (
    <div className="bg-bg-deep border border-bg-edge rounded px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">
        {label}
      </div>
      {value === null ? (
        <span
          className={`inline-block align-middle bg-bg-edge/60 rounded animate-pulse mt-1 ${big ? "h-5" : "h-3.5"}`}
          style={{ width: big ? "5.5rem" : "4rem" }}
        />
      ) : (
        <div
          className={`font-mono tnum mt-0.5 ${big ? "text-base" : "text-xs"} ${accent ?? "text-zinc-100"}`}
        >
          {value}
        </div>
      )}
      {sub && <div className="text-[10px] text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}
