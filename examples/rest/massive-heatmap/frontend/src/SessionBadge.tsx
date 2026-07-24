import type { SessionPhase } from "../../shared/protocol.js";
const MAP: Record<SessionPhase, { label: string; color: string }> = {
  regular: { label: "MARKET OPEN", color: "#16A34A" },
  premarket: { label: "PRE-MARKET", color: "#F59E0B" },
  afterhours: { label: "AFTER HOURS", color: "#3B82F6" },
  closed: { label: "CLOSED", color: "#7D8794" },
  open24: { label: "24/7", color: "#16A34A" },
};
export function SessionBadge({ phase }: { phase: SessionPhase }) {
  const m = MAP[phase] ?? MAP.closed;
  return <span className="badge" style={{ borderColor: m.color, color: m.color }}>
    <span className="badge-dot" style={{ background: m.color }} />{m.label}
  </span>;
}
