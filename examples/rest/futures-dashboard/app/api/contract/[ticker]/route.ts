import { NextResponse } from "next/server";
import {
  getSnapshot,
  getAggregates,
  getTrades,
  getQuotes,
  listContracts,
} from "@/lib/massive";
import { todayISO } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ ticker: string }> }
) {
  try {
    const { ticker } = await params;
    const t = ticker.toUpperCase();
    const today = todayISO();

    const sixtyDaysAgo = new Date();
    sixtyDaysAgo.setDate(sixtyDaysAgo.getDate() - 90);
    const histStart = sixtyDaysAgo.toISOString().slice(0, 10);

    const [snapshots, bars, trades, quotes] = await Promise.all([
      getSnapshot({ ticker: t, limit: 1 }),
      getAggregates({
        ticker: t,
        resolution: "1day",
        windowStartGte: histStart,
        limit: 90,
        sort: "window_start.asc",
      }).catch(() => []),
      getTrades({ ticker: t, limit: 30 }).catch(() => []),
      getQuotes({ ticker: t, limit: 50 }).catch(() => []),
    ]);

    const snap = snapshots[0] ?? null;
    const productCode = snap?.details?.product_code;

    let contract: Awaited<ReturnType<typeof listContracts>>[number] | null =
      null;
    if (productCode) {
      const contracts = await listContracts({
        productCode,
        date: today,
        active: true,
        limit: 250,
      }).catch(() => []);
      contract = contracts.find((c) => c.ticker === t) ?? null;
    }

    const sortedDesc = [...bars].sort((a, b) => b.window_start - a.window_start);
    let priorReference: number | null = null;
    if (sortedDesc.length >= 1) {
      const settled = sortedDesc.find(
        (b) =>
          typeof b.settlement_price === "number" && b.settlement_price > 0
      );
      priorReference =
        settled?.settlement_price ??
        sortedDesc[1]?.close ??
        sortedDesc[0]?.close ??
        null;
    }

    const STALE_DAYS = 5;
    const nowMs = Date.now();
    const lastUpdated = snap?.last_trade?.last_updated;
    let lastTradeAge: number | null = null;
    if (typeof lastUpdated === "number" && lastUpdated > 0) {
      lastTradeAge = Math.floor(
        (nowMs - lastUpdated / 1_000_000) / 86_400_000
      );
    }
    let recentBarAge: number | null = null;
    if (sortedDesc[0]?.session_end_date) {
      const sd = new Date(sortedDesc[0].session_end_date + "T00:00:00Z");
      recentBarAge = Math.floor(
        (Date.now() - sd.getTime()) / 86_400_000
      );
    }
    const tradeFresh =
      lastTradeAge !== null && lastTradeAge <= STALE_DAYS;
    const aggFresh = recentBarAge !== null && recentBarAge <= STALE_DAYS;
    const isStale = !tradeFresh && !aggFresh;

    return NextResponse.json({
      ticker: t,
      snapshot: snap,
      contract,
      prior_reference: priorReference,
      is_stale: isStale,
      last_trade_age_days: lastTradeAge ?? recentBarAge,
      history: bars.map((b) => ({
        date: b.session_end_date ?? "",
        ts: b.window_start,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
        settlement: b.settlement_price,
        volume: b.volume,
      })),
      recent_trades: trades,
      latest_quote: quotes[0] ?? null,
      recent_quotes: quotes,
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "contract_failed" },
      { status: 500 }
    );
  }
}
