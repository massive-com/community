"use client";

import { useState } from "react";
import { fmtPrice, fmtPct, fmtCompact, changeColor } from "@/lib/format";
import type { CurveResponse, CurveRow } from "@/lib/types";

interface Props {
  productCode: string;
  curve: CurveResponse | null;
  curveLoading?: boolean;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
}

type SortKey =
  | "ticker"
  | "days_to_maturity"
  | "price"
  | "change_percent"
  | "volume";

export function ContractsTable({
  productCode,
  curve,
  curveLoading,
  selectedTicker,
  onSelectTicker,
}: Props) {
  const data = curve;
  const loading = !curve && curveLoading;
  const [sortKey, setSortKey] = useState<SortKey>("days_to_maturity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showStale, setShowStale] = useState(false);

  const allRows: CurveRow[] = data?.rows ?? [];
  const liveCount = allRows.filter((r) => !r.stale).length;
  const showAllBecauseQuiet = allRows.length > 0 && liveCount === 0;
  const filtered = allRows.filter(
    (r) => showStale || showAllBecauseQuiet || !r.stale
  );

  const sorted = [...filtered].sort((a, b) => {
    const av = sortValue(a, sortKey);
    const bv = sortValue(b, sortKey);
    let cmp = 0;
    if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
    else cmp = String(av).localeCompare(String(bv));
    return sortDir === "asc" ? cmp : -cmp;
  });

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else {
      setSortKey(key);
      setSortDir(key === "ticker" ? "asc" : "desc");
    }
  }

  const staleCount = allRows.length - liveCount;

  return (
    <div className="terminal-panel rounded-lg flex flex-col h-full overflow-hidden">
      <div className="terminal-panel-header px-3 py-2 border-b border-bg-border flex items-center gap-2 flex-wrap">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
          {productCode} Contracts
        </h3>
        <span className="text-[10px] font-mono text-zinc-500">
          {loading
            ? "loading"
            : showAllBecauseQuiet
              ? `${staleCount} reference`
              : `${liveCount} live${staleCount > 0 ? ` · ${staleCount} inactive` : ""}`}
        </span>
        {staleCount > 0 && !showAllBecauseQuiet && (
          <label className="ml-auto flex items-center gap-1.5 text-[10px] text-zinc-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showStale}
              onChange={(e) => setShowStale(e.target.checked)}
              className="accent-blue-500"
            />
            show inactive
          </label>
        )}
      </div>
      <div className="overflow-y-auto">
        <table className="w-full text-[11px] font-mono tnum">
          <thead className="sticky top-0 bg-bg-panel/95 backdrop-blur z-10">
            <tr className="border-b border-bg-border text-[9px] uppercase tracking-wider text-zinc-500">
              <Th
                onClick={() => toggleSort("ticker")}
                active={sortKey === "ticker"}
                dir={sortDir}
              >
                Ticker
              </Th>
              <Th
                onClick={() => toggleSort("days_to_maturity")}
                active={sortKey === "days_to_maturity"}
                dir={sortDir}
              >
                Expires
              </Th>
              <Th
                onClick={() => toggleSort("price")}
                active={sortKey === "price"}
                dir={sortDir}
                right
              >
                Last
              </Th>
              <Th
                onClick={() => toggleSort("change_percent")}
                active={sortKey === "change_percent"}
                dir={sortDir}
                right
              >
                Chg %
              </Th>
              <Th
                onClick={() => toggleSort("volume")}
                active={sortKey === "volume"}
                dir={sortDir}
                right
              >
                Vol
              </Th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const isSelected = r.ticker === selectedTicker;
              const isFront = r.ticker === data?.front_month;
              return (
                <tr
                  key={r.ticker}
                  onClick={() => onSelectTicker(r.ticker)}
                  className={`cursor-pointer border-b border-bg-border/40 ${
                    isSelected ? "bg-accent-blue/8" : "hover:bg-bg-elev"
                  } ${r.stale ? "opacity-50" : ""}`}
                >
                  <td className="px-3 py-1 flex items-center gap-1.5">
                    <span
                      className={
                        r.stale
                          ? "text-zinc-500"
                          : isSelected
                            ? "text-accent-blue"
                            : "text-zinc-200"
                      }
                    >
                      {r.ticker}
                    </span>
                    {isFront && (
                      <span
                        className={`text-[8px] font-bold uppercase tracking-wider px-1 py-0.5 rounded border ${
                          r.stale
                            ? "bg-zinc-700/20 text-zinc-400 border-zinc-700"
                            : "bg-accent-green/15 text-accent-green border-accent-green/30"
                        }`}
                      >
                        {r.stale ? "near" : "front"}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-zinc-500">
                    <span className="text-zinc-400">{r.settlement_date}</span>{" "}
                    <span className="text-zinc-600">({r.days_to_maturity}d)</span>
                  </td>
                  <td
                    className={`px-2 py-1 text-right whitespace-nowrap ${r.stale ? "text-zinc-500" : "text-zinc-100"}`}
                  >
                    {r.price === null ? "No price" : fmtPrice(r.price)}
                  </td>
                  <td
                    className={`px-2 py-1 text-right whitespace-nowrap font-semibold ${changeColor(r.change_percent)}`}
                  >
                    {r.change_percent === null ? "No ref" : fmtPct(r.change_percent)}
                  </td>
                  <td className="px-3 py-1 text-right text-zinc-300 whitespace-nowrap">
                    {r.volume === null ? "No volume" : fmtCompact(r.volume)}
                  </td>
                </tr>
              );
            })}
            {!sorted.length && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-4 text-center text-zinc-500 text-[11px]"
                >
                  {loading ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
                      loading contracts...
                    </span>
                  ) : (
                    "No active contracts."
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function sortValue(row: CurveRow, key: SortKey): number | string {
  if (key === "ticker") return row.ticker;
  return row[key] ?? 0;
}

function Th({
  children,
  onClick,
  active,
  dir,
  right,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  dir: "asc" | "desc";
  right?: boolean;
}) {
  return (
    <th
      onClick={onClick}
      className={`px-2 py-1.5 cursor-pointer select-none ${
        right ? "text-right" : "text-left"
      } ${active ? "text-zinc-300" : ""}`}
    >
      {children}
      {active && (
        <span className="ml-0.5 text-[7px]">{dir === "asc" ? "▲" : "▼"}</span>
      )}
    </th>
  );
}
