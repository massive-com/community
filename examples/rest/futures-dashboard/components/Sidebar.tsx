"use client";

import useSWR from "swr";
import { useMemo, useState } from "react";
import {
  CURATED_FLAT,
  CURATED_GROUPS,
  SEARCH_ALIASES,
} from "@/lib/curated-products";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";

interface ProductsResponse {
  total: number;
  groups: {
    label: string;
    count: number;
    products: { product_code: string; name: string }[];
  }[];
}

interface Props {
  selected: string;
  onSelect: (code: string) => void;
}

const curatedRank = new Map(CURATED_FLAT.map((p, i) => [p.code, i]));

export function Sidebar({ selected, onSelect }: Props) {
  const { data, error } = useSWR<ProductsResponse>("/api/products", fetchJson);
  const [query, setQuery] = useState("");

  const allProducts = useMemo(() => {
    const list: { code: string; name: string; group: string }[] = [];
    for (const g of data?.groups ?? []) {
      for (const p of g.products) {
        list.push({ code: p.product_code, name: p.name, group: g.label });
      }
    }
    return list;
  }, [data]);

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    const codeQuery = q.toUpperCase();
    const aliasCodes = new Set(SEARCH_ALIASES[q] ?? []);
    return allProducts
      .filter(
        (p) =>
          aliasCodes.has(p.code) ||
          p.code.toLowerCase().includes(q) ||
          p.name.toLowerCase().includes(q) ||
          p.group.toLowerCase().includes(q)
      )
      .map((p) => ({
        ...p,
        score: aliasCodes.has(p.code) ? -1 : scoreProduct(p, q, codeQuery),
      }))
      .sort(
        (a, b) =>
          a.score - b.score ||
          a.code.length - b.code.length ||
          a.name.localeCompare(b.name)
      )
      .slice(0, 80);
  }, [query, allProducts]);

  return (
    <aside className="w-64 shrink-0 border-r border-bg-border bg-bg-deep overflow-y-auto">
      <div className="px-3 py-3 border-b border-bg-border sticky top-0 bg-bg-deep z-10">
        <input
          type="text"
          placeholder="Search products, codes, nicknames"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full px-2.5 py-2 text-[11px] font-mono bg-bg-panel border border-bg-border rounded-md focus:outline-none focus:border-accent-blue text-zinc-200 placeholder:text-zinc-600"
        />
      </div>

      {!searchResults && (
        <>
          <div className="px-3 py-3">
            <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-2 font-semibold">
              Demo Watchlist
            </div>
            <div className="flex flex-col gap-2.5">
              {CURATED_GROUPS.map((group) => (
                <div key={group.name}>
                  <div className="text-[10px] text-zinc-500 mb-1">
                    {group.name}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {group.products.map((p) => (
                      <button
                        key={p.code}
                        onClick={() => onSelect(p.code)}
                        className={`px-1.5 py-0.5 text-[10px] font-mono rounded border transition-colors ${
                          selected === p.code
                            ? "bg-accent-blue/20 border-accent-blue text-blue-100 shadow-[0_0_18px_rgba(59,130,246,0.12)]"
                            : "bg-bg-panel border-bg-border text-zinc-300 hover:border-bg-edge hover:text-white"
                        }`}
                        title={p.label}
                      >
                        {p.code}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-bg-border px-3 py-3">
            <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-2 font-semibold flex items-center justify-between">
              Reference Catalog
              {data?.total ? (
                <span className="text-zinc-600 normal-case">
                  {data.total.toLocaleString()}
                </span>
              ) : null}
            </div>
            {!data && (
              <div className="text-[11px] text-zinc-500 font-mono">
                loading...
              </div>
            )}
            {error && (
              <PanelError
                compact
                message={`Catalog unavailable: ${errorMessage(error)}`}
              />
            )}
            {data?.groups?.slice(0, 15).map((g) => (
              <details key={g.label} className="mb-1.5 group">
                <summary className="cursor-pointer text-[10px] text-zinc-400 hover:text-zinc-200 list-none flex items-center justify-between font-mono rounded px-1 py-0.5 hover:bg-bg-panel">
                  <span className="truncate">{g.label}</span>
                  <span className="text-zinc-600">{g.count}</span>
                </summary>
                <div className="mt-1 max-h-44 overflow-y-auto pl-1">
                  {g.products.slice(0, 50).map((p) => (
                    <button
                      key={p.product_code}
                      onClick={() => onSelect(p.product_code)}
                      className={`block w-full text-left text-[10px] py-1 px-1.5 hover:bg-bg-elev rounded truncate font-mono ${
                        selected === p.product_code
                          ? "bg-accent-blue/15 text-blue-200"
                          : "text-zinc-400"
                      }`}
                      title={p.name}
                    >
                      <span className="text-zinc-300">{p.product_code}</span>{" "}
                      <span className="text-zinc-500">{p.name}</span>
                    </button>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </>
      )}

      {searchResults && (
        <div className="px-3 py-3">
          <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-2 font-semibold">
            Search · {searchResults.length}
          </div>
          <div className="flex flex-col gap-0.5">
            {searchResults.map((p) => (
              <button
                key={p.code}
                onClick={() => {
                  onSelect(p.code);
                  setQuery("");
                }}
                className={`text-left text-[10px] py-1.5 px-2 hover:bg-bg-elev rounded font-mono transition-colors ${
                  selected === p.code
                    ? "bg-accent-blue/15 text-blue-200"
                    : "text-zinc-300"
                }`}
                title={p.name}
              >
                <div>
                  <span className="text-zinc-200 font-semibold">{p.code}</span>
                  <span className="ml-1.5 text-zinc-500 truncate">
                    {p.name}
                  </span>
                </div>
                <div className="text-[9px] text-zinc-600 truncate">
                  {p.group}
                </div>
              </button>
            ))}
            {searchResults.length === 0 && (
              <div className="text-[11px] text-zinc-500">No matches.</div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

function scoreProduct(
  product: { code: string; name: string; group: string },
  query: string,
  codeQuery: string
): number {
  const code = product.code.toUpperCase();
  const name = product.name.toLowerCase();
  const group = product.group.toLowerCase();
  const rank = curatedRank.get(product.code);

  if (code === codeQuery) return 0;
  if (code.startsWith(codeQuery)) return 1;
  if (rank !== undefined && name.includes(query)) return 2 + rank / 1000;
  if (name.startsWith(query)) return 3;
  if (name.includes(query)) return 4;
  if (group.includes(query)) return 5;
  return 6;
}
