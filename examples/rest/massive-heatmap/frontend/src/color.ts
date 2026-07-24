export const CLAMP = 0.06; // color scale saturates at +/- this fraction (default)
const NEUTRAL = [42, 49, 58] as const;  // #2A313A dark slate
const GREEN = [22, 163, 74] as const;   // #16A34A
const RED = [220, 38, 38] as const;     // #DC2626

export const CLAMP_BY_LOOKBACK: Record<number, number> = {
  1: 0.06, 7: 0.10, 30: 0.20, 90: 0.35, 180: 0.50, 365: 0.80, 1825: 3.0,
};
export function clampForLookback(days: number): number {
  return CLAMP_BY_LOOKBACK[days] ?? 0.06;
}

// Legible sign color for text (e.g. the tooltip Change row). The diverging pctColor
// scale fades to near-neutral slate for small moves, which is right for tiles but
// unreadable as text on a dark surface, so color purely by sign at full brightness.
const TEXT_UP = "#22C55E", TEXT_DOWN = "#F87171", TEXT_FLAT = "#9AA4B2";
export function pctTextColor(pct: number): string {
  return pct > 0 ? TEXT_UP : pct < 0 ? TEXT_DOWN : TEXT_FLAT;
}

function lerp(a: number, b: number, t: number) { return Math.round(a + (b - a) * t); }

export function pctColor(pct: number, clamp = 0.06): string {
  const c = Math.max(-clamp, Math.min(clamp, pct));
  const t = Math.abs(c) / clamp;
  const target = c >= 0 ? GREEN : RED;
  const [r, g, b] = [0, 1, 2].map((i) => lerp(NEUTRAL[i], target[i], t));
  return `rgb(${r}, ${g}, ${b})`;
}
