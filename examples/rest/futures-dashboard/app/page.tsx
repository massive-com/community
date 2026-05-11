"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { StatusStrip } from "@/components/StatusStrip";
import { Sidebar } from "@/components/Sidebar";
import { HeroCard } from "@/components/HeroCard";
import { PositionSizer } from "@/components/PositionSizer";
import { Watchlist } from "@/components/Watchlist";
import { TermStructure } from "@/components/TermStructure";
import { ContractsTable } from "@/components/ContractsTable";
import { TimeAndSales } from "@/components/TimeAndSales";
import { HistoryChart } from "@/components/HistoryChart";
import type { CurveResponse } from "@/lib/types";
import { errorMessage, fetchJson } from "@/lib/fetcher";

export default function Page() {
  return (
    <Suspense fallback={<main className="h-screen bg-bg-base" />}>
      <PageInner />
    </Suspense>
  );
}

function PageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlProduct = (searchParams.get("p") ?? "CL").toUpperCase();
  const urlTicker = searchParams.get("t");

  const [productCode, setProductCode] = useState<string>(urlProduct);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(
    urlTicker
  );
  const [autoFollowFrontMonth, setAutoFollowFrontMonth] = useState(!urlTicker);

  const {
    data: curve,
    error: curveError,
    isLoading: curveLoading,
  } = useSWR<CurveResponse>(`/api/product/${productCode}`, fetchJson, {
    refreshInterval: 60_000,
  });

  // Track contract loading at the page level so the overlay waits for the
  // panels that depend on this data (HeroCard, PositionSizer, TimeAndSales).
  // SWR deduplicates — no extra network request.
  const { isLoading: contractLoading } = useSWR(
    selectedTicker ? `/api/contract/${selectedTicker}` : null,
    fetchJson,
    { refreshInterval: 15_000 }
  );

  useEffect(() => {
    if (autoFollowFrontMonth && curve?.front_month) {
      setSelectedTicker(curve.front_month);
    }
  }, [autoFollowFrontMonth, curve?.front_month]);

  // Sync URL on product/ticker change.
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("p", productCode);
    if (selectedTicker) params.set("t", selectedTicker);
    const next = `?${params.toString()}`;
    if (next !== `?${searchParams.toString()}`) {
      router.replace(next, { scroll: false });
    }
  }, [productCode, selectedTicker, router, searchParams]);

  function handleProductSelect(code: string) {
    if (code === productCode) return;
    setProductCode(code);
    setSelectedTicker(null);
    setAutoFollowFrontMonth(true);
  }

  function handleTickerSelect(ticker: string) {
    setSelectedTicker(ticker);
    setAutoFollowFrontMonth(false);
  }

  return (
    <main className="app-shell h-screen flex flex-col bg-bg-base">
      <StatusStrip />
      <div className="flex-1 flex min-h-0">
        <Sidebar selected={productCode} onSelect={handleProductSelect} />
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden relative">
          {curveError && (
            <div className="mx-5 mt-4 rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 font-mono text-[11px] text-rose-200">
              Product data unavailable: {errorMessage(curveError)}
            </div>
          )}
          <HeroCard
            productCode={productCode}
            ticker={selectedTicker}
            curve={curve ?? null}
            curveLoading={curveLoading}
            onSwitchProduct={handleProductSelect}
          />

          <div className="flex-1 min-h-0 flex flex-col px-5 pt-4 pb-3 gap-4 overflow-hidden">
            <div className="flex-shrink-0 h-72 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr),380px] gap-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <TermStructure
                  curve={curve ?? null}
                  curveLoading={curveLoading}
                  selectedTicker={selectedTicker}
                  onSelectTicker={handleTickerSelect}
                />
                <HistoryChart ticker={selectedTicker} />
              </div>
              <PositionSizer
                productCode={productCode}
                ticker={selectedTicker}
                curve={curve ?? null}
                curveLoading={curveLoading}
                onSwitchProduct={handleProductSelect}
              />
            </div>

            <div className="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[minmax(0,1.4fr),minmax(0,1fr),minmax(0,0.8fr)] gap-4">
              <Watchlist
                selected={productCode}
                onSelect={handleProductSelect}
              />
              <ContractsTable
                productCode={productCode}
                curve={curve ?? null}
                curveLoading={curveLoading}
                selectedTicker={selectedTicker}
                onSelectTicker={handleTickerSelect}
              />
              <TimeAndSales ticker={selectedTicker} />
            </div>
          </div>

          <div
            className={`absolute inset-0 z-50 flex flex-col items-center justify-center transition-opacity duration-300 ${
              curveLoading || !selectedTicker || contractLoading
                ? "opacity-100"
                : "opacity-0 pointer-events-none"
            }`}
            style={{ background: "#070810" }}
          >
            <img
              src="/massive-logo-white.svg"
              alt="Massive"
              className="w-28 opacity-50"
            />
            <p className="mt-4 font-mono text-[11px] text-zinc-600 animate-pulse">
              loading market data...
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
