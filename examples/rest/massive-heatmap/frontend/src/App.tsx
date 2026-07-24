import { useEffect, useRef, useState } from "react";
import { connect } from "./api.js";
import { TileStore } from "./store.js";
import { Heatmap } from "./Heatmap.js";
import { Controls } from "./Controls.js";
import { SessionBadge } from "./SessionBadge.js";
import { Footer } from "./Footer.js";
import { Tooltip } from "./Tooltip.js";
import { ExportPreview } from "./ExportPreview.js";
import { SettingsModal } from "./SettingsModal.js";
import { LoadingOverlay } from "./LoadingOverlay.js";
import { useSettings } from "./settings.js";
import { clampForLookback } from "./color.js";
import type { Tile, Segment, SessionPhase } from "../../shared/protocol.js";

const SESSION_LABEL: Record<SessionPhase, string> = {
  regular: "Market open", premarket: "Pre-market", afterhours: "After hours", closed: "Market closed", open24: "24/7",
};
const SEGMENT_TITLE: Record<Segment, string> = {
  stocks: "Stocks", etfs: "ETFs", crypto: "Crypto", forex: "Forex", futures: "Futures", indices: "Indices",
};
const LOOKBACKS = [1, 7, 30, 90, 180, 365, 1825] as const;
const LOOKBACK_LABEL: Record<number, string> = { 1: "1D", 7: "7D", 30: "30D", 90: "90D", 180: "180D", 365: "1Y", 1825: "5Y" };
const LOOKBACK_EXPORT: Record<number, string> = { 1: "1 Day", 7: "7 Day", 30: "30 Day", 90: "90 Day", 180: "180 Day", 365: "1 Year", 1825: "5 Year" };
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

export function App() {
  const store = useRef(new TileStore());
  const [, force] = useState(0);
  const [label, setLabel] = useState("S&P 500");
  const [segment, setSegment] = useState<Segment>("stocks");
  const [hover, setHover] = useState<{ tile: Tile; x: number; y: number } | null>(null);
  const [showExport, setShowExport] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [lookback, setLookback] = useState(1);
  // Covers the heatmap from when a fetch is requested until its snapshot (or an
  // error) arrives. loadingName is what's being fetched, shown in the overlay.
  const [loading, setLoading] = useState(true);
  const [loadingName, setLoadingName] = useState("S&P 500");
  const wrapRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; sl: number; st: number } | null>(null);
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight - 108 });
  const [conn] = useState(() =>
    connect((m) => {
      if (m.type === "snapshot") { store.current.applySnapshot(m); setLabel(m.label); setSegment(m.segment); setLoading(false); }
      else if (m.type === "diff") store.current.applyDiff(m);
      else if (m.type === "error") setLoading(false);
      force((n) => n + 1);
    })
  );
  // Futures roll across contracts, so lookback is not meaningful: force 1D (intraday)
  // and hide the lookback control while a futures universe is shown.
  const isFutures = segment === "futures";
  const effLookback = isFutures ? 1 : lookback;
  const { settings } = useSettings();
  const colorClamp = settings.clamps[effLookback] ?? clampForLookback(effLookback);
  useEffect(() => { conn.select("sp500", 1); }, []);
  // Re-time the polling interval on load and whenever the setting changes.
  useEffect(() => { conn.setRefresh(settings.refreshMs); }, [settings.refreshMs]);
  useEffect(() => {
    const onResize = () => setVp({ w: window.innerWidth, h: window.innerHeight - 108 });
    window.addEventListener("resize", onResize); return () => window.removeEventListener("resize", onResize);
  }, []);

  // Mouse wheel zooms (anchored to the cursor); no modifier needed.
  useEffect(() => {
    const el = wrapRef.current; if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
      setZoom((z) => {
        const nz = clamp(+(z * (e.deltaY < 0 ? 1.12 : 1 / 1.12)).toFixed(3), 1, 8);
        if (nz === z) return z;
        const ratio = nz / z;
        requestAnimationFrame(() => {
          el.scrollLeft = (el.scrollLeft + cx) * ratio - cx;
          el.scrollTop = (el.scrollTop + cy) * ratio - cy;
        });
        return nz;
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // Click and drag to pan.
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const el = wrapRef.current, d = dragRef.current; if (!el || !d) return;
      el.scrollLeft = d.sl - (e.clientX - d.x);
      el.scrollTop = d.st - (e.clientY - d.y);
    };
    const onUp = () => { dragRef.current = null; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  const tiles = store.current.tiles();
  const session = store.current.session() as SessionPhase;
  const dateStr = new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  const title = `${SEGMENT_TITLE[segment]} ${label}`;

  return (
    <div className="app">
      <header className="topbar">
        <div className="title-block">
          <div className="eyebrow">Real-time &middot; Sized by market cap</div>
          <div className="headline">{title} <span className="accent">Heatmap</span></div>
        </div>
        <Controls onSelectUniverse={(id, seg, name) => { setLoading(true); setLoadingName(name); conn.select(id, seg === "futures" ? 1 : lookback); setZoom(1); }} />
        {!isFutures && (
          <select className="lookback-select"
            value={lookback}
            onChange={(e) => { const lb = Number(e.target.value); setLoading(true); setLoadingName(label); setLookback(lb); conn.setLookback(lb); }}>
            {LOOKBACKS.map((lb) => <option key={lb} value={lb}>{LOOKBACK_LABEL[lb]}</option>)}
          </select>
        )}
        <div className="right-cluster">
          <button className="btn-ghost" onClick={() => setShowSettings(true)}>Settings</button>
          <button className="btn-ghost export-btn" onClick={() => setShowExport(true)}>Export</button>
          <SessionBadge phase={session} />
          <img className="wordmark-img" src="/massive-logo-white.svg" alt="MASSIVE" />
        </div>
      </header>
      <div className="canvas-stage">
        <div className={`canvas-wrap${loading ? " is-loading" : ""}`} ref={wrapRef}
          title="Scroll to zoom, drag to pan, double-click to reset"
          onDoubleClick={() => setZoom(1)}
          onMouseDown={(e) => {
            const el = wrapRef.current; if (!el) return;
            dragRef.current = { x: e.clientX, y: e.clientY, sl: el.scrollLeft, st: el.scrollTop };
            setHover(null);
          }}>
          <Heatmap tiles={tiles} width={Math.round(vp.w * zoom)} height={Math.round(vp.h * zoom)}
            clamp={colorClamp}
            onHover={(t, x, y) => { if (dragRef.current) return; setHover(t ? { tile: t, x: x ?? 0, y: y ?? 0 } : null); }} />
        </div>
        {loading && <LoadingOverlay name={loadingName} />}
      </div>
      <Footer session={session} dateStr={dateStr} clamp={colorClamp} />
      {hover && <Tooltip tile={hover.tile} x={hover.x} y={hover.y}
        periodLabel={effLookback === 1 ? "Prev close" : `${LOOKBACK_LABEL[effLookback]} ago`} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showExport && (
        <ExportPreview tiles={tiles}
          meta={{ title, sessionLabel: SESSION_LABEL[session] ?? "—", dateStr,
            lookbackLabel: LOOKBACK_EXPORT[effLookback] ?? `${effLookback} Day` }}
          clamp={colorClamp} layoutW={vp.w} layoutH={vp.h} onClose={() => setShowExport(false)} />
      )}
    </div>
  );
}
