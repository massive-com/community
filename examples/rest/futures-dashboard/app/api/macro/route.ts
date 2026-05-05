import { NextResponse } from "next/server";
import {
  listContracts,
  listProducts,
  getSnapshot,
  getAggregates,
} from "@/lib/massive";
import { CURATED_FLAT } from "@/lib/curated-products";
import { todayISO } from "@/lib/format";
import type { MacroTile } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 30;

function nearTermTickers(
  contracts: { ticker: string; days_to_maturity?: number }[]
): string[] {
  return contracts
    .filter(
      (c) => typeof c.days_to_maturity === "number" && c.days_to_maturity! >= 0
    )
    .sort((a, b) => (a.days_to_maturity ?? 0) - (b.days_to_maturity ?? 0))
    .slice(0, 5)
    .map((c) => c.ticker);
}

export async function GET() {
  try {
    const date = todayISO();
    const codeList = CURATED_FLAT.map((p) => p.code).join(",");

    const [products, contractLists] = await Promise.all([
      listProducts({
        date,
        type: "single",
        productCodeAnyOf: codeList,
        limit: 200,
      }),
      Promise.all(
        CURATED_FLAT.map(async (p) => {
          const contracts = await listContracts({
            productCode: p.code,
            date,
            active: true,
            limit: 500,
          });
          return { code: p.code, contracts };
        })
      ),
    ]);

    const productByCode = new Map<string, (typeof products)[number]>();
    for (const p of products) {
      if (p.product_code && !productByCode.has(p.product_code)) {
        productByCode.set(p.product_code, p);
      }
    }

    const tickerToCode: Record<string, string> = {};
    const candidateTickers: string[] = [];
    for (const { code, contracts } of contractLists) {
      const top = nearTermTickers(contracts);
      for (const t of top) {
        candidateTickers.push(t);
        tickerToCode[t] = code;
      }
    }

    const snapshots = candidateTickers.length
      ? await getSnapshot({ tickerAnyOf: candidateTickers.join(","), limit: 500 })
      : [];

    const snapByTicker = new Map<string, (typeof snapshots)[number]>();
    for (const s of snapshots) {
      if (s.details?.ticker) snapByTicker.set(s.details.ticker, s);
    }

    const STALE_MS = 5 * 86_400_000;
    const nowMs = Date.now();

    function isFresh(ticker: string): boolean {
      const lu = snapByTicker.get(ticker)?.last_trade?.last_updated;
      return typeof lu === "number" && lu > 0 && nowMs - lu / 1_000_000 < STALE_MS;
    }

    const frontByCode: Record<string, string> = {};
    for (const t of candidateTickers) {
      const code = tickerToCode[t];
      const fresh = isFresh(t);
      const vol = (snapByTicker.get(t)?.session?.volume ?? 0) * (fresh ? 1 : 0);
      const incumbent = frontByCode[code];
      const incumbentFresh = incumbent ? isFresh(incumbent) : false;
      const incumbentVol = incumbent
        ? (snapByTicker.get(incumbent)?.session?.volume ?? 0) *
          (incumbentFresh ? 1 : 0)
        : -1;
      if (!incumbent || vol > incumbentVol) {
        frontByCode[code] = t;
      }
    }
    const tickers = Object.values(frontByCode);

    const fourteenDaysAgo = new Date();
    fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14);
    const sparkStart = fourteenDaysAgo.toISOString().slice(0, 10);

    const sparks = await Promise.all(
      tickers.map(async (t) => {
        try {
          const bars = await getAggregates({
            ticker: t,
            resolution: "1day",
            windowStartGte: sparkStart,
            limit: 14,
            sort: "window_start.asc",
          });
          return {
            ticker: t,
            closes: bars.map((b) => b.close).filter((n) => typeof n === "number"),
            settlements: bars
              .map((b) => b.settlement_price)
              .filter((n): n is number => typeof n === "number" && n > 0),
          };
        } catch {
          return { ticker: t, closes: [] as number[], settlements: [] as number[] };
        }
      })
    );
    const sparkByTicker = new Map(sparks.map((s) => [s.ticker, s]));

    const tiles: MacroTile[] = CURATED_FLAT.map((p) => {
      const fm = frontByCode[p.code] ?? null;
      const snap = fm ? snapByTicker.get(fm) : undefined;
      const product = productByCode.get(p.code);
      const fresh = fm ? isFresh(fm) : false;

      const settle = snap?.session?.settlement_price;
      const last = snap?.last_trade?.price;

      const sparkData = fm ? sparkByTicker.get(fm) : undefined;
      const closes = sparkData?.closes ?? [];
      const settlements = sparkData?.settlements ?? [];

      let price: number | null = null;
      if (fresh && typeof last === "number") {
        price = last;
      } else if (closes.length >= 1) {
        price = closes[closes.length - 1];
      } else if (typeof settle === "number" && settle > 0 && fresh) {
        price = settle;
      }

      let changePct: number | null = null;
      let prevRef: number | null = null;
      if (settlements.length >= 1) {
        prevRef = settlements[settlements.length - 1];
      } else if (closes.length >= 2) {
        prevRef = closes[closes.length - 2];
      }
      if (typeof price === "number" && typeof prevRef === "number" && prevRef > 0) {
        changePct = ((price - prevRef) / prevRef) * 100;
      }

      return {
        product_code: p.code,
        product_name: product?.name ?? p.label,
        asset_class: product?.asset_class ?? "N/A",
        ticker: fm,
        price: typeof price === "number" ? price : null,
        change_percent: changePct,
        volume:
          fresh && typeof snap?.session?.volume === "number"
            ? snap!.session!.volume!
            : null,
        spark: closes,
        timeframe: snap?.last_trade?.timeframe ?? snap?.last_minute?.timeframe,
      };
    });

    return NextResponse.json({ tiles, asof: new Date().toISOString() });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "macro_failed" },
      { status: 500 }
    );
  }
}
