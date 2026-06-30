import { useEffect, useState } from "react";
import { useSettings } from "./settings.js";

const SEGMENT_LABEL: Record<string, string> = { stocks: "Stocks", etfs: "ETFs", crypto: "Crypto", forex: "Forex", futures: "Futures", indices: "Indices" };
const UNIVERSES: Record<string, { id: string; label: string }[]> = {
  stocks: [{ id: "sp500", label: "S&P 500" }, { id: "nasdaq100", label: "Nasdaq 100" }, { id: "dow30", label: "Dow 30" }],
  etfs: [{ id: "etf-sectors", label: "Sector SPDRs" }, { id: "etf-broad", label: "Broad Market" }, { id: "etf-thematic", label: "Thematic" }],
  crypto: [{ id: "crypto", label: "Top Coins" }, { id: "crypto-l1", label: "Layer 1s" }, { id: "crypto-defi", label: "DeFi" }],
  forex: [{ id: "forex", label: "FX Majors" }, { id: "forex-crosses", label: "Crosses" }, { id: "forex-exotic", label: "USD Exotics" }],
  futures: [{ id: "futures-equity", label: "Equity Index" }, { id: "futures-energy", label: "Energy" }, { id: "futures-metals", label: "Metals" }],
  indices: [{ id: "indices", label: "Major Indices" }, { id: "indices-sectors", label: "Sectors" }, { id: "indices-global", label: "Global" }],
};

export function Controls({ onSelectUniverse }: {
  onSelectUniverse: (id: string, segment: string, label: string) => void;
}) {
  const { settings } = useSettings();
  const hiddenSeg = new Set(settings.hiddenSegments);
  const hiddenUni = new Set(settings.hiddenUniverses);

  const segments = Object.keys(UNIVERSES).filter((s) => !hiddenSeg.has(s as any));
  const [segment, setSegment] = useState(segments[0] ?? "stocks");

  const visibleUniverses = (seg: string) =>
    (UNIVERSES[seg] ?? []).filter((u) => !hiddenUni.has(u.id));

  const onSegmentChange = (s: string) => {
    setSegment(s);
    const first = visibleUniverses(s)[0];
    if (first) onSelectUniverse(first.id, s, first.label);
  };

  // If the active segment gets hidden in settings, fall back to the first visible one.
  useEffect(() => {
    if (segments.includes(segment)) return;
    const next = segments[0] ?? "stocks";
    setSegment(next);
    const first = visibleUniverses(next)[0];
    if (first) onSelectUniverse(first.id, next, first.label);
  }, [segments.join(","), segment]);

  return (
    <div className="controls">
      <select value={segment} onChange={(e) => onSegmentChange(e.target.value)}>
        {segments.map((s) => <option key={s} value={s}>{SEGMENT_LABEL[s] ?? s}</option>)}
      </select>
      <select onChange={(e) => {
        const u = visibleUniverses(segment).find((x) => x.id === e.target.value);
        onSelectUniverse(e.target.value, segment, u?.label ?? "");
      }}>
        {visibleUniverses(segment).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
    </div>
  );
}
