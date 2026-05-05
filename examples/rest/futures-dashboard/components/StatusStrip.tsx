"use client";

import useSWR from "swr";
import type { VenueStatus } from "@/lib/types";
import { fetchJson } from "@/lib/fetcher";

interface OverviewResponse {
  venues: VenueStatus[];
  asof: string;
}

interface ProductsResponse {
  total: number;
}

export function StatusStrip() {
  const { data, error: overviewError } = useSWR<OverviewResponse>(
    "/api/overview",
    fetchJson,
    {
      refreshInterval: 30_000,
    }
  );
  const { data: productsData, error: productsError } = useSWR<ProductsResponse>(
    "/api/products",
    fetchJson
  );
  const hasError = overviewError || productsError;
  const primaryState = data?.venues?.find((v) => v.state !== "closed")?.state;
  const marketLabel =
    primaryState === "open"
      ? "Globex open"
      : primaryState === "paused"
        ? "Globex paused"
        : primaryState === "maintenance"
          ? "Globex maintenance"
          : data?.venues?.length
            ? "Globex closed"
            : "checking venues";

  return (
    <div className="flex items-center gap-5 px-5 py-2.5 border-b border-bg-border bg-bg-deep/95 backdrop-blur">
      <div className="flex items-center gap-3">
        <a
          href="https://massive.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center"
          title="Massive"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/massive-logo-white.svg"
            alt="Massive"
            className="h-3.5 w-auto opacity-80 hover:opacity-100 transition-opacity"
          />
        </a>
        <span className="text-zinc-700 text-xs">/</span>
        <span className="font-mono text-[11px] tracking-tight text-zinc-300 uppercase">
          Futures Command
        </span>
        <a
          href="https://massive.com/docs/rest/futures/overview"
          target="_blank"
          rel="noreferrer"
          className="text-[10px] font-mono text-zinc-500 hover:text-accent-blue transition-colors"
          title="Massive Futures REST documentation"
        >
          docs ↗
        </a>
      </div>

      <div className="hidden xl:flex items-center gap-2 rounded-full border border-bg-edge bg-bg-panel/70 px-2.5 py-1">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${stateDot(primaryState ?? "closed")}`}
        />
        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-300">
          {marketLabel}
        </span>
      </div>

      <div className="flex items-center gap-3">
        {hasError ? (
          <span className="text-[11px] text-rose-300 font-mono">
            API unavailable
          </span>
        ) : (
          data?.venues?.map((v) => (
            <div
              key={v.mic}
              className="flex items-center gap-1.5 text-[11px] font-mono"
              title={`${v.name} (${v.mic}) · ${v.open}/${v.total} products open`}
            >
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  stateDot(v.state)
                }`}
              />
              <span className="text-zinc-300">{v.acronym}</span>
              <span className="text-zinc-600">
                {v.label}
              </span>
            </div>
          )) ?? (
            <span className="text-[11px] text-zinc-600 font-mono">
              loading...
            </span>
          )
        )}
      </div>

      <div className="ml-auto flex items-center gap-4 text-[11px] font-mono text-zinc-500">
        <span className="hidden lg:inline" title="REST snapshots poll every 15 seconds.">
          REST poll 15s
        </span>
        {productsData?.total !== undefined && (
          <span>
            <span className="text-zinc-300">
              {productsData.total.toLocaleString()}
            </span>{" "}
            products
          </span>
        )}
        {data?.asof && (
          <span title={data.asof}>
            {new Date(data.asof).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

function stateDot(state: VenueStatus["state"] | "closed"): string {
  if (state === "open") return "bg-accent-green shadow-[0_0_10px_rgba(34,197,94,0.45)] animate-pulse";
  if (state === "maintenance") return "bg-accent-amber shadow-[0_0_10px_rgba(245,158,11,0.35)]";
  if (state === "paused") return "bg-accent-amber animate-pulse";
  return "bg-zinc-600";
}
