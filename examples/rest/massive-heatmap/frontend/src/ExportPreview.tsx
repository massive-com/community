import { useEffect, useRef } from "react";
import type { Tile } from "../../shared/protocol.js";
import { renderExport, downloadCanvasPng, type ExportMeta } from "./capture.js";

export function ExportPreview({ tiles, meta, clamp = 0.06, layoutW, layoutH, onClose }:
  { tiles: Tile[]; meta: ExportMeta; clamp?: number; layoutW: number; layoutH: number; onClose: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current; if (!canvas) return;
    const logo = new Image();
    logo.onload = () => renderExport(canvas, tiles, meta, logo, clamp, layoutW, layoutH);
    logo.onerror = () => renderExport(canvas, tiles, meta, undefined, clamp, layoutW, layoutH);
    logo.src = "/massive-logo-white.svg";
  }, [tiles, meta, clamp, layoutW, layoutH]);
  return (
    <div className="overlay" onClick={onClose}>
      <div className="export-card" onClick={(e) => e.stopPropagation()}>
        <canvas ref={ref} className="export-canvas" />
        <div className="export-actions">
          <button className="btn-ghost" onClick={onClose}>Close</button>
          <button className="btn-primary"
            onClick={() => ref.current && downloadCanvasPng(ref.current, `massive-heatmap-${meta.dateStr.replace(/[ ,]/g, "")}.png`)}>
            Download PNG
          </button>
        </div>
      </div>
    </div>
  );
}
