export const LOOKBACKS = [1, 7, 30, 90, 180, 365, 1825] as const;
export type Lookback = (typeof LOOKBACKS)[number];

export function isLookback(n: unknown): n is Lookback {
  return typeof n === "number" && (LOOKBACKS as readonly number[]).includes(n);
}

// UTC YYYY-MM-DD for an epoch.
function ymd(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

// Candidate window-start dates to try, newest first: (now - days), then walk back
// up to `back` more calendar days to skip weekends/holidays (grouped returns empty).
export function windowStartCandidates(nowMs: number, days: number, back = 6): string[] {
  const start = nowMs - days * 86_400_000;
  const out: string[] = [];
  for (let i = 0; i <= back; i++) out.push(ymd(start - i * 86_400_000));
  return out;
}
