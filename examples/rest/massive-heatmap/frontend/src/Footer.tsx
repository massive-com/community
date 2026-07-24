import type { SessionPhase } from "../../shared/protocol.js";
const SESSION_LABEL: Record<SessionPhase, string> = {
  regular: "Market open", premarket: "Pre-market", afterhours: "After hours", closed: "Market closed", open24: "24/7",
};
export function Footer({ session, dateStr, clamp = 0.06 }: { session: SessionPhase; dateStr: string; clamp?: number }) {
  const pct = Math.round(clamp * 100);
  return (
    <div className="footer">
      <div>Data via Massive.com &nbsp;&middot;&nbsp; {SESSION_LABEL[session] ?? "—"}</div>
      <div className="right">
        <div className="legend"><span>-{pct}%</span><div className="legend-bar" /><span>+{pct}%</span></div>
        <div>{dateStr}</div>
      </div>
    </div>
  );
}
