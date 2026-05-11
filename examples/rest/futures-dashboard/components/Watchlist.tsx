"use client";

import useSWR from "swr";
import { useState } from "react";
import { CURATED_GROUPS } from "@/lib/curated-products";
import { fmtPrice, fmtPct, fmtCompact, changeColor } from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { Sparkline } from "./Sparkline";
import { PanelError } from "./PanelError";
import { Skeleton } from "./Skeleton";
import type { MacroTile } from "@/lib/types";

interface MacroResponse {
  tiles: MacroTile[];
  asof: string;
}

type SortKey = "group" | "product" | "price" | "change_percent" | "volume";

interface Props {
  selected: string;
  onSelect: (code: string) => void;
}

export function Watchlist({ selected, onSelect }: Props) {
  const { data, error } = useSWR<MacroResponse>("/api/macro", fetchJson, {
    refreshInterval: 30_000,
  });
  const isLoading = !data && !error;
  const [sortKey, setSortKey] = useState<SortKey>("group");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const byCode = new Map<string, MacroTile>();
  for (const t of data?.tiles ?? []) {
    byCode.set(t.product_code, t);
  }

  const rows = CURATED_GROUPS.flatMap((group, groupIndex) =>
    group.products.map((product, productIndex) => ({
      group: group.name,
      groupIndex,
      productIndex,
      product,
      tile: byCode.get(product.code),
    }))
  );

  const sortedRows = [...rows].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortKey === "group") {
      return (
        (a.groupIndex - b.groupIndex || a.productIndex - b.productIndex) * dir
      );
    }
    if (sortKey === "product") {
      return a.product.code.localeCompare(b.product.code) * dir;
    }
    const av = valueForSort(a.tile, sortKey);
    const bv = valueForSort(b.tile, sortKey);
    return (av - bv || a.product.code.localeCompare(b.product.code)) * dir;
  });

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
      return;
    }
    setSortKey(key);
    setSortDir(key === "group" || key === "product" ? "asc" : "desc");
  }

  return (
    <section className="terminal-panel rounded-lg overflow-hidden flex flex-col h-full">
      <div className="terminal-panel-header px-4 py-2.5 border-b border-bg-border flex items-center gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Watchlist
        </h3>
        <span className="text-[10px] font-mono text-zinc-500">
          24 products · front-month by volume
        </span>
        {isLoading && (
          <span className="text-[10px] font-mono text-zinc-500 ml-auto">
            loading...
          </span>
        )}
      </div>

      {error && (
        <div className="p-3">
          <PanelError message={`Watchlist unavailable: ${errorMessage(error)}`} />
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto">
        <table className="w-full text-xs font-mono tnum">
          <thead className="sticky top-0 bg-bg-panel/95 backdrop-blur z-10">
            <tr className="border-b border-bg-border text-[9px] uppercase tracking-wider text-zinc-500">
              <Th
                active={sortKey === "group"}
                dir={sortDir}
                onClick={() => toggleSort("group")}
              >
                Group
              </Th>
              <Th
                active={sortKey === "product"}
                dir={sortDir}
                onClick={() => toggleSort("product")}
              >
                Product
              </Th>
              <th className="text-left px-2 py-1.5">Front</th>
              <Th
                active={sortKey === "price"}
                dir={sortDir}
                onClick={() => toggleSort("price")}
                right
              >
                Last
              </Th>
              <Th
                active={sortKey === "change_percent"}
                dir={sortDir}
                onClick={() => toggleSort("change_percent")}
                right
              >
                Chg %
              </Th>
              <Th
                active={sortKey === "volume"}
                dir={sortDir}
                onClick={() => toggleSort("volume")}
                right
              >
                Volume
              </Th>
              <th className="text-right px-3 py-1.5">10d</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(({ group, product, tile }) => (
              <Row
                key={product.code}
                group={group}
                product={product}
                tile={tile}
                isLoading={isLoading}
                selected={selected}
                onSelect={onSelect}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Row({
  group,
  product,
  tile,
  isLoading,
  selected,
  onSelect,
}: {
  group: string;
  product: { code: string; label: string };
  tile: MacroTile | undefined;
  isLoading: boolean;
  selected: string;
  onSelect: (code: string) => void;
}) {
  const positive =
    tile?.change_percent !== null && tile?.change_percent !== undefined
      ? tile.change_percent >= 0
      : undefined;
  const isSelected = selected === product.code;

  return (
    <tr
      onClick={() => onSelect(product.code)}
      className={`border-b border-bg-border/40 cursor-pointer transition-colors ${
        isSelected ? "bg-accent-blue/8" : "hover:bg-bg-elev"
      }`}
    >
      <td className="px-3 py-1.5 text-[10px] text-zinc-500">{group}</td>
      <td className="px-2 py-1.5 whitespace-nowrap">
        <span
          className={`font-semibold ${isSelected ? "text-accent-blue" : "text-zinc-200"}`}
        >
          {product.code}
        </span>
        <span className="ml-1.5 text-[10px] text-zinc-500">
          {product.label}
        </span>
      </td>
      <td className="px-2 py-1.5 text-zinc-400">
        {isLoading ? (
          <Skeleton className="h-3" width="3rem" />
        ) : (
          tile?.ticker ?? "Quiet"
        )}
      </td>
      <td className="px-2 py-1.5 text-right text-zinc-100">
        {isLoading ? (
          <Skeleton className="h-3" width="3.5rem" />
        ) : tile?.price === null || tile?.price === undefined ? (
          <span className="text-zinc-500">No tick</span>
        ) : (
          fmtPrice(tile.price)
        )}
      </td>
      <td
        className={`px-2 py-1.5 text-right font-semibold ${changeColor(tile?.change_percent)}`}
      >
        {isLoading ? (
          <Skeleton className="h-3" width="2.5rem" />
        ) : tile?.change_percent === null || tile?.change_percent === undefined ? (
          <span className="text-zinc-500">No ref</span>
        ) : (
          fmtPct(tile.change_percent)
        )}
      </td>
      <td className="px-2 py-1.5 text-right text-zinc-400">
        {isLoading ? (
          <Skeleton className="h-3" width="2.5rem" />
        ) : tile?.volume === null || tile?.volume === undefined ? (
          <span className="text-zinc-600">0</span>
        ) : (
          fmtCompact(tile.volume)
        )}
      </td>
      <td className="px-3 py-1.5 text-right">
        <div className="inline-block">
          {isLoading ? (
            <Skeleton className="h-4" width={64} />
          ) : (
            <Sparkline
              values={tile?.spark ?? []}
              positive={positive}
              width={64}
              height={18}
            />
          )}
        </div>
      </td>
    </tr>
  );
}

function valueForSort(tile: MacroTile | undefined, key: SortKey): number {
  if (!tile) return Number.NEGATIVE_INFINITY;
  if (key === "price") return tile.price ?? Number.NEGATIVE_INFINITY;
  if (key === "change_percent") {
    return tile.change_percent ?? Number.NEGATIVE_INFINITY;
  }
  if (key === "volume") return tile.volume ?? Number.NEGATIVE_INFINITY;
  return 0;
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
      className={`px-2 py-1.5 ${right ? "text-right" : "text-left"} ${
        active ? "text-zinc-300" : ""
      }`}
    >
      <button
        type="button"
        onClick={onClick}
        className={`select-none ${right ? "text-right" : "text-left"}`}
      >
        {children}
        {active && (
          <span className="ml-0.5 text-[7px]">
            {dir === "asc" ? "▲" : "▼"}
          </span>
        )}
      </button>
    </th>
  );
}
