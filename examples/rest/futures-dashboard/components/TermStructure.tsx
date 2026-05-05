"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { fmtPrice, fmtPct, changeColor } from "@/lib/format";
import type { CurveResponse } from "@/lib/types";

interface Props {
  curve: CurveResponse | null;
  curveLoading?: boolean;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
}

const SHAPE_LABEL: Record<CurveResponse["contango"], string> = {
  contango: "Contango",
  backwardation: "Backwardation",
  mixed: "Mixed",
  insufficient_data: "Quiet",
};

const SHAPE_COLOR: Record<CurveResponse["contango"], string> = {
  contango: "text-amber-300 bg-amber-300/10 border-amber-300/30",
  backwardation: "text-emerald-300 bg-emerald-300/10 border-emerald-300/30",
  mixed: "text-zinc-300 bg-zinc-300/10 border-zinc-300/20",
  insufficient_data: "text-zinc-500 bg-zinc-700/20 border-zinc-700",
};

const SHAPE_HINT: Record<CurveResponse["contango"], string> = {
  contango: "Deferred contracts trade above the front. Carry is negative for longs.",
  backwardation:
    "Deferred contracts trade below the front. Carry is positive for longs.",
  mixed: "No consistent direction across the front of the curve.",
  insufficient_data: "Not enough liquid contracts to classify.",
};

export function TermStructure({
  curve,
  curveLoading,
  selectedTicker,
  onSelectTicker,
}: Props) {
  const data = curve;
  const loading = !curve && curveLoading;

  const chartData = (data?.rows ?? [])
    .filter((r) => typeof r.price === "number" && !r.stale)
    .map((r) => ({
      ticker: r.ticker,
      days: r.days_to_maturity,
      price: r.price as number,
    }));

  const shape = data?.contango ?? "insufficient_data";
  const frontIdx = chartData.findIndex((d) => d.ticker === data?.front_month);
  const hasReferenceContracts = (data?.rows?.length ?? 0) > 0;

  return (
    <section className="terminal-panel rounded-lg overflow-hidden flex flex-col h-full">
      <div className="terminal-panel-header px-3 py-2 border-b border-bg-border flex items-center gap-2 flex-wrap">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
          Term Structure
        </h3>
        {!loading && (
          <span
            className={`px-1.5 py-0.5 rounded border text-[9px] uppercase tracking-wider ${SHAPE_COLOR[shape]}`}
            title={SHAPE_HINT[shape]}
          >
            {SHAPE_LABEL[shape]}
          </span>
        )}
        <span className="text-[10px] font-mono text-zinc-500">
          {loading ? "loading" : `${chartData.length} liquid`}
        </span>
        {data?.roll_yield_annualized !== null &&
          data?.roll_yield_annualized !== undefined && (
            <span
              className={`ml-auto text-[10px] font-mono ${changeColor(data.roll_yield_annualized)}`}
              title="Annualized long roll yield from the front contract to the next liquid contract"
            >
              roll {fmtPct(data.roll_yield_annualized)}
            </span>
          )}
      </div>

      <div className="flex-1 p-2">
        {loading ? (
          <div className="h-full flex items-center justify-center gap-2 text-[11px] font-mono text-zinc-500">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
            building curve...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-zinc-500">
            {hasReferenceContracts
              ? "No recently active contracts."
              : "No active contracts."}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 6, right: 12, left: 0, bottom: 4 }}
            >
              <CartesianGrid stroke="#1c2030" vertical={false} />
              <XAxis
                dataKey="days"
                type="number"
                domain={["dataMin", "dataMax"]}
                stroke="#3a3f55"
                tick={{ fontSize: 9 }}
                tickFormatter={(d) => `${d}d`}
              />
              <YAxis
                stroke="#3a3f55"
                tick={{ fontSize: 9 }}
                domain={["auto", "auto"]}
                width={48}
                orientation="right"
              />
              <Tooltip
                contentStyle={{
                  background: "#0e1018",
                  border: "1px solid #1c2030",
                  fontSize: 11,
                }}
                labelFormatter={(d) => `${d} days to expiry`}
                formatter={(
                  value: number,
                  name: string,
                  item: { payload?: { ticker?: string } }
                ) => {
                  if (name === "price")
                    return [fmtPrice(value), item?.payload?.ticker ?? ""];
                  return [fmtPrice(value), name];
                }}
              />
              {frontIdx >= 0 && chartData[frontIdx] && (
                <ReferenceLine
                  x={chartData[frontIdx].days}
                  stroke="#3b82f6"
                  strokeDasharray="3 3"
                />
              )}
              <Line
                type="monotone"
                dataKey="price"
                stroke="#3b82f6"
                strokeWidth={1.6}
                dot={(props) => {
                  const t = props.payload?.ticker;
                  const isSelected = selectedTicker && t === selectedTicker;
                  const isFront = data?.front_month && t === data.front_month;
                  return (
                    <circle
                      key={t}
                      cx={props.cx}
                      cy={props.cy}
                      r={isSelected ? 4.5 : isFront ? 3.5 : 2.5}
                      fill={
                        isSelected
                          ? "#f59e0b"
                          : isFront
                            ? "#22c55e"
                            : "#3b82f6"
                      }
                      stroke="#070810"
                      strokeWidth={1}
                      style={{ cursor: "pointer" }}
                      onClick={() => t && onSelectTicker(t)}
                    />
                  );
                }}
                activeDot={{ r: 4.5, fill: "#f59e0b" }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
