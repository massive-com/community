"use client";

import useSWR from "swr";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { fmtPrice } from "@/lib/format";
import { errorMessage, fetchJson } from "@/lib/fetcher";
import { PanelError } from "./PanelError";

interface ContractDetail {
  history: {
    date: string;
    close: number;
    volume: number;
  }[];
}

interface Props {
  ticker: string | null;
}

export function HistoryChart({ ticker }: Props) {
  const { data, error } = useSWR<ContractDetail>(
    ticker ? `/api/contract/${ticker}` : null,
    fetchJson,
    { refreshInterval: 60_000 }
  );
  const loading = !!ticker && !data && !error;

  const history = (data?.history ?? []).filter(
    (h) => typeof h.close === "number"
  );
  const closes = history.map((h) => h.close);
  const min = closes.length ? Math.min(...closes) : 0;
  const max = closes.length ? Math.max(...closes) : 0;

  return (
    <section className="terminal-panel rounded-lg overflow-hidden h-full flex flex-col">
      <div className="terminal-panel-header px-3 py-2 border-b border-bg-border flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
          90-Day History
        </h3>
        <span className="text-[10px] font-mono text-zinc-500">
          {ticker ? `${ticker} · ${history.length} sessions` : ""}
        </span>
      </div>
      <div className="flex-1 px-1 py-1">
        {error ? (
          <div className="p-2">
            <PanelError
              compact
              message={`History unavailable: ${errorMessage(error)}`}
            />
          </div>
        ) : history.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={history}
              margin={{ top: 8, right: 8, left: 0, bottom: 4 }}
            >
              <defs>
                <linearGradient id="histArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1c2030" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="#3a3f55"
                tick={{ fontSize: 9 }}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis
                yAxisId="price"
                stroke="#3a3f55"
                tick={{ fontSize: 9 }}
                domain={[min - (max - min) * 0.1, max + (max - min) * 0.1]}
                width={48}
                orientation="right"
              />
              <YAxis
                yAxisId="vol"
                stroke="#3a3f55"
                tick={false}
                axisLine={false}
                hide
              />
              <Tooltip
                contentStyle={{
                  background: "#0e1018",
                  border: "1px solid #1c2030",
                  fontSize: 11,
                }}
                formatter={(v: number, name: string) => {
                  if (name === "volume") return [v.toLocaleString(), "vol"];
                  return [fmtPrice(v), "close"];
                }}
              />
              <Bar
                yAxisId="vol"
                dataKey="volume"
                fill="#1c2030"
                stroke="none"
                isAnimationActive={false}
              />
              <Area
                yAxisId="price"
                type="monotone"
                dataKey="close"
                stroke="#3b82f6"
                strokeWidth={1.6}
                fill="url(#histArea)"
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : loading ? (
          <div className="h-full flex items-center justify-center gap-2 text-[11px] font-mono text-zinc-500">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
            loading 90 days...
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-xs text-zinc-500">
            {ticker ? "No history available." : "Select a contract."}
          </div>
        )}
      </div>
    </section>
  );
}
