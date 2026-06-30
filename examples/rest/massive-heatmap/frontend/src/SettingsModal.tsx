import { useSettings } from "./settings.js";
import { clampForLookback } from "./color.js";
import { REFRESH_OPTIONS } from "./settingsStore.js";
import type { Segment } from "../../shared/universe.js";

const LOOKBACKS = [1, 7, 30, 90, 180, 365, 1825];
const LOOKBACK_LABEL: Record<number, string> = { 1: "1D", 7: "7D", 30: "30D", 90: "90D", 180: "180D", 365: "1Y", 1825: "5Y" };
const round1 = (x: number) => Math.round(x * 10) / 10;
const refreshLabel = (ms: number) => `${ms / 1000}s`;

const SEGMENTS: { id: Segment; label: string }[] = [
  { id: "stocks", label: "Stocks" }, { id: "etfs", label: "ETFs" }, { id: "crypto", label: "Crypto" },
  { id: "forex", label: "Forex" }, { id: "futures", label: "Futures" }, { id: "indices", label: "Indices" },
];
const UNIVERSES: Record<string, { id: string; label: string }[]> = {
  stocks: [{ id: "sp500", label: "S&P 500" }, { id: "nasdaq100", label: "Nasdaq 100" }, { id: "dow30", label: "Dow 30" }],
  etfs: [{ id: "etf-sectors", label: "Sector SPDRs" }, { id: "etf-broad", label: "Broad Market" }, { id: "etf-thematic", label: "Thematic" }],
  crypto: [{ id: "crypto", label: "Top Coins" }, { id: "crypto-l1", label: "Layer 1s" }, { id: "crypto-defi", label: "DeFi" }],
  forex: [{ id: "forex", label: "FX Majors" }, { id: "forex-crosses", label: "Crosses" }, { id: "forex-exotic", label: "USD Exotics" }],
  futures: [{ id: "futures-equity", label: "Equity Index" }, { id: "futures-energy", label: "Energy" }, { id: "futures-metals", label: "Metals" }],
  indices: [{ id: "indices", label: "Major Indices" }, { id: "indices-sectors", label: "Sectors" }, { id: "indices-global", label: "Global" }],
};

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const { settings, setHiddenSegments, setHiddenUniverses, setClamps, setRefreshMs } = useSettings();
  const hiddenSeg = new Set(settings.hiddenSegments);
  const hiddenUni = new Set(settings.hiddenUniverses);

  const clampPct = (lb: number) => round1((settings.clamps[lb] ?? clampForLookback(lb)) * 100);
  const setClampPct = (lb: number, raw: string) => {
    const v = Number(raw);
    if (!Number.isFinite(v) || v <= 0) return;
    setClamps({ ...settings.clamps, [lb]: v / 100 });
  };

  const toggleSeg = (id: Segment) => {
    const next = new Set(hiddenSeg);
    next.has(id) ? next.delete(id) : next.add(id);
    setHiddenSegments([...next] as Segment[]);
  };
  const toggleUni = (id: string) => {
    const next = new Set(hiddenUni);
    next.has(id) ? next.delete(id) : next.add(id);
    setHiddenUniverses([...next]);
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-head">
          <h2>Settings</h2>
          <button className="btn-ghost" onClick={onClose}>Close</button>
        </div>
        <section>
          <div className="settings-section-title">Visible asset classes</div>
          <p className="settings-hint">Hide classes your Massive key cannot reach.</p>
          {SEGMENTS.map((s) => (
            <div key={s.id} className="settings-group">
              <label className="settings-row">
                <input type="checkbox" checked={!hiddenSeg.has(s.id)} onChange={() => toggleSeg(s.id)} />
                <span>{s.label}</span>
              </label>
              {!hiddenSeg.has(s.id) && (
                <div className="settings-universes">
                  {(UNIVERSES[s.id] ?? []).map((u) => (
                    <label key={u.id} className="settings-row settings-sub">
                      <input type="checkbox" checked={!hiddenUni.has(u.id)} onChange={() => toggleUni(u.id)} />
                      <span>{u.label}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}
        </section>
        <section style={{ marginTop: 18 }}>
          <div className="settings-section-title">Updates</div>
          <p className="settings-hint">How often the heatmap re-polls Massive for fresh prices.</p>
          <label className="settings-row">
            <span style={{ flex: 1 }}>Refresh every</span>
            <select className="lookback-select" value={settings.refreshMs}
              onChange={(e) => setRefreshMs(Number(e.target.value))}>
              {REFRESH_OPTIONS.map((ms) => <option key={ms} value={ms}>{refreshLabel(ms)}</option>)}
            </select>
          </label>
        </section>
        <section style={{ marginTop: 18 }}>
          <div className="settings-section-title">Color scale</div>
          <p className="settings-hint">The percent move that fully saturates green/red, per lookback. Drives the tiles and the footer legend.</p>
          {LOOKBACKS.map((lb) => (
            <label key={lb} className="settings-row">
              <span style={{ flex: 1 }}>{LOOKBACK_LABEL[lb]}</span>
              <span className="tt-label">&plusmn;</span>
              <input className="clamp-input" type="number" min="0.1" step="0.5"
                value={clampPct(lb)} onChange={(e) => setClampPct(lb, e.target.value)} />
              <span className="tt-label">%</span>
            </label>
          ))}
        </section>
      </div>
    </div>
  );
}
