import { NextResponse } from "next/server";
import {
  listProducts,
  listContracts,
  getSnapshot,
  getAggregates,
} from "@/lib/massive";
import { todayISO } from "@/lib/format";
import { findFamily } from "@/lib/curated-products";
import type { CurveResponse, CurveRow, VariantInfo } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 30;

const STALENESS_THRESHOLD_DAYS = 5;

function classifyCurve(rows: CurveRow[]): CurveResponse["contango"] {
  const valid = rows
    .filter((r) => typeof r.price === "number" && !r.stale)
    .sort((a, b) => a.days_to_maturity - b.days_to_maturity)
    .slice(0, 8);
  if (valid.length < 2) return "insufficient_data";

  let upCount = 0;
  let downCount = 0;
  for (let i = 1; i < valid.length; i++) {
    const a = valid[i - 1].price as number;
    const b = valid[i].price as number;
    if (b > a) upCount += 1;
    else if (b < a) downCount += 1;
  }
  const total = upCount + downCount;
  if (!total) return "insufficient_data";
  if (upCount / total >= 0.75) return "contango";
  if (downCount / total >= 0.75) return "backwardation";
  return "mixed";
}

function rollYieldAnnualized(rows: CurveRow[]): number | null {
  const valid = rows
    .filter((r) => typeof r.price === "number" && !r.stale)
    .sort((a, b) => a.days_to_maturity - b.days_to_maturity);
  if (valid.length < 2) return null;

  const front = valid[0];
  const next = valid[1];
  const fp = front.price as number;
  const np = next.price as number;
  if (fp <= 0 || np <= 0) return null;

  const dDays = next.days_to_maturity - front.days_to_maturity;
  if (dDays <= 0) return null;

  const rollReturn = (fp - np) / fp;
  const annualized = (rollReturn / dDays) * 365 * 100;
  return annualized;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ code: string }> }
) {
  try {
    const { code } = await params;
    const productCode = code.toUpperCase();
    const date = todayISO();

    const family = findFamily(productCode);
    const familyCodes =
      family?.variants?.map((v) => v.code) ?? [productCode];
    const productCodeQuery = Array.from(new Set([productCode, ...familyCodes])).join(
      ","
    );

    const [productList, contracts] = await Promise.all([
      listProducts({
        date,
        type: "single",
        productCodeAnyOf: productCodeQuery,
        limit: 30,
      }),
      listContracts({
        productCode,
        date,
        active: true,
        limit: 250,
      }),
    ]);

    const productByCode = new Map<string, (typeof productList)[number]>();
    for (const p of productList) {
      if (p.product_code && !productByCode.has(p.product_code)) {
        productByCode.set(p.product_code, p);
      }
    }
    const product = productByCode.get(productCode) ?? null;

    const variants: VariantInfo[] =
      family?.variants?.map((v) => {
        const live = productByCode.get(v.code);
        return {
          code: v.code,
          size: v.size,
          multiplier:
            (typeof live?.unit_of_measure_qty === "number"
              ? live.unit_of_measure_qty
              : null) ??
            v.fallbackMultiplier ??
            null,
          unit: live?.unit_of_measure ?? v.fallbackUnit ?? null,
          name: live?.name ?? null,
        };
      }) ?? [];

    const future = contracts
      .filter(
        (c) =>
          typeof c.days_to_maturity === "number" && c.days_to_maturity! >= 0
      )
      .sort(
        (a, b) => (a.days_to_maturity ?? 0) - (b.days_to_maturity ?? 0)
      );

    const activeVariant =
      variants.find((v) => v.code === productCode) ?? null;
    const multiplier =
      activeVariant?.multiplier ??
      (typeof product?.unit_of_measure_qty === "number"
        ? product.unit_of_measure_qty
        : null);
    const unit = activeVariant?.unit ?? product?.unit_of_measure ?? null;

    if (!future.length) {
      return NextResponse.json({
        product,
        contango: "insufficient_data" as const,
        roll_yield_annualized: null,
        front_month: null,
        total_volume: 0,
        rows: [],
        multiplier,
        unit,
        variants,
        family_label: family?.primary?.label ?? null,
        group_label: family?.group ?? null,
      } satisfies CurveResponse);
    }

    const tickers = future.map((c) => c.ticker);

    const fiveDaysAgo = new Date();
    fiveDaysAgo.setDate(fiveDaysAgo.getDate() - 7);
    const priorStart = fiveDaysAgo.toISOString().slice(0, 10);

    // Cap the prior-aggregates fan-out: the curve classifier and roll yield
    // only use the first 8 liquid contracts, and per-row change% is a nice-to-
    // have for far-dated rows (which usually trade infrequently anyway). This
    // turns a per-product call from O(N) aggregates fetches into a constant
    // ~PRIOR_AGG_FANOUT, which is the difference between ~130 calls (CL) and
    // ~8 calls per /api/product/CL request.
    const PRIOR_AGG_FANOUT = 8;
    const aggTickers = tickers.slice(0, PRIOR_AGG_FANOUT);

    const [snapshots, priorAggsTop] = await Promise.all([
      getSnapshot({ tickerAnyOf: tickers.join(","), limit: 500 }),
      Promise.all(
        aggTickers.map(async (t) => {
          try {
            const bars = await getAggregates({
              ticker: t,
              resolution: "1day",
              windowStartGte: priorStart,
              limit: 6,
              sort: "window_start.desc",
            });
            const recent = bars[0];
            const settled = bars.find(
              (b) =>
                typeof b.settlement_price === "number" &&
                b.settlement_price > 0
            );
            const fallback = bars[1]?.close ?? bars[0]?.close;
            return {
              ticker: t,
              recent_close:
                typeof recent?.close === "number" && recent.close > 0
                  ? recent.close
                  : null,
              recent_session_end: recent?.session_end_date ?? null,
              prior:
                settled?.settlement_price ??
                (typeof fallback === "number" && fallback > 0 ? fallback : null),
            };
          } catch {
            return {
              ticker: t,
              recent_close: null as number | null,
              recent_session_end: null as string | null,
              prior: null as number | null,
            };
          }
        })
      ),
    ]);
    // Pad with empty entries for the contracts we deliberately didn't fetch.
    const priorAggs = priorAggsTop.concat(
      tickers.slice(PRIOR_AGG_FANOUT).map((t) => ({
        ticker: t,
        recent_close: null as number | null,
        recent_session_end: null as string | null,
        prior: null as number | null,
      }))
    );

    const snapByTicker = new Map<string, (typeof snapshots)[number]>();
    for (const s of snapshots) {
      if (s.details?.ticker) snapByTicker.set(s.details.ticker, s);
    }
    const priorByTicker = new Map(priorAggs.map((p) => [p.ticker, p]));

    const nowMs = Date.now();
    const today = new Date();

    const rows: CurveRow[] = future.map((c) => {
      const s = snapByTicker.get(c.ticker);
      const settle = s?.session?.settlement_price ?? null;
      const last = s?.last_trade?.price ?? null;
      const lastUpdated = s?.last_trade?.last_updated;
      const aggInfo = priorByTicker.get(c.ticker);
      const prev = aggInfo?.prior ?? null;

      let lastTradeAge: number | null = null;
      if (typeof lastUpdated === "number" && lastUpdated > 0) {
        lastTradeAge = Math.floor((nowMs - lastUpdated / 1_000_000) / 86_400_000);
      }

      let recentAge: number | null = null;
      if (aggInfo?.recent_session_end) {
        const sd = new Date(aggInfo.recent_session_end + "T00:00:00Z");
        recentAge = Math.floor(
          (today.getTime() - sd.getTime()) / 86_400_000
        );
      }

      const tradeFresh = lastTradeAge !== null && lastTradeAge <= STALENESS_THRESHOLD_DAYS;
      const aggFresh = recentAge !== null && recentAge <= STALENESS_THRESHOLD_DAYS;

      let price: number | null = null;
      if (tradeFresh && typeof last === "number") {
        price = last;
      } else if (aggFresh && typeof aggInfo?.recent_close === "number") {
        price = aggInfo.recent_close;
      } else if (
        typeof settle === "number" &&
        settle > 0 &&
        (tradeFresh || aggFresh)
      ) {
        price = settle;
      }

      const stale = !tradeFresh && !aggFresh;
      const ageDays = lastTradeAge ?? recentAge;

      let change: number | null = null;
      let changePct: number | null = null;
      if (
        typeof price === "number" &&
        typeof prev === "number" &&
        prev > 0
      ) {
        change = price - prev;
        changePct = (change / prev) * 100;
      }

      return {
        ticker: c.ticker,
        settlement_date: c.settlement_date ?? c.last_trade_date ?? "",
        days_to_maturity: c.days_to_maturity ?? 0,
        price,
        settlement: typeof settle === "number" ? settle : null,
        previous_settlement: prev,
        change,
        change_percent: changePct,
        volume: stale
          ? null
          : typeof s?.session?.volume === "number"
            ? s!.session!.volume!
            : null,
        bid:
          tradeFresh && typeof s?.last_quote?.bid === "number"
            ? s!.last_quote!.bid!
            : null,
        ask:
          tradeFresh && typeof s?.last_quote?.ask === "number"
            ? s!.last_quote!.ask!
            : null,
        timeframe:
          s?.last_trade?.timeframe ?? s?.last_minute?.timeframe ?? null,
        stale,
        last_trade_age_days: ageDays,
      };
    });

    const totalVolume = rows.reduce(
      (sum, r) => sum + (typeof r.volume === "number" ? r.volume : 0),
      0
    );

    const liveRows = rows.filter((r) => !r.stale);
    let frontMonth: string | null = liveRows[0]?.ticker ?? future[0]?.ticker ?? null;
    let frontVol = -1;
    for (const r of liveRows.slice(0, 6)) {
      const v = typeof r.volume === "number" ? r.volume : 0;
      if (v > frontVol) {
        frontVol = v;
        frontMonth = r.ticker;
      }
    }

    return NextResponse.json({
      product,
      contango: classifyCurve(rows),
      roll_yield_annualized: rollYieldAnnualized(rows),
      front_month: frontMonth,
      total_volume: totalVolume,
      rows,
      multiplier,
      unit,
      variants,
      family_label: family?.primary?.label ?? null,
      group_label: family?.group ?? null,
    } satisfies CurveResponse);
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "product_failed" },
      { status: 500 }
    );
  }
}
