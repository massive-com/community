import type { Segment, SessionPhase } from "../../shared/protocol.js";

const ET_FMT = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "2-digit", minute: "2-digit", weekday: "short", hour12: false,
});

function etParts(epochMs: number): { hours: number; weekday: number } {
  const parts = ET_FMT.formatToParts(new Date(epochMs));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const hour = parseInt(get("hour"), 10) % 24;
  const minute = parseInt(get("minute"), 10);
  const wdMap: Record<string, number> = { Sun:0, Mon:1, Tue:2, Wed:3, Thu:4, Fri:5, Sat:6 };
  return { hours: hour + minute / 60, weekday: wdMap[get("weekday")] ?? 0 };
}

export function sessionPhase(segment: Segment, epochMs: number): SessionPhase {
  if (segment === "crypto") return "open24";
  const { hours, weekday } = etParts(epochMs);
  const weekend = weekday === 0 || weekday === 6;
  if (segment === "forex" || segment === "futures") return weekend ? "closed" : "regular";
  if (weekend) return "closed";
  if (hours >= 4 && hours < 9.5) return "premarket";
  if (hours >= 9.5 && hours < 16) return "regular";
  if (hours >= 16 && hours < 20) return "afterhours";
  return "closed";
}
