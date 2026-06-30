import type { Segment } from "../../shared/universe.js";

// Refresh intervals (ms) the UI offers. This is a client-side poll cadence; the
// backend does not see or validate it.
export const REFRESH_OPTIONS = [2000, 5000, 10000, 30000, 60000];
export const DEFAULT_REFRESH_MS = 5000;

export interface Settings {
  version: 1;
  hiddenSegments: Segment[];
  hiddenUniverses: string[];
  // Per-lookback color-clamp overrides, keyed by lookback days; value is a fraction
  // (e.g. 0.2 = ±20%). Missing keys fall back to the built-in default for that lookback.
  clamps: Record<number, number>;
  // How often the backend re-polls the snapshot, in milliseconds.
  refreshMs: number;
}

export const STORAGE_KEY = "massive-heatmap-settings";

export const DEFAULT_SETTINGS: Settings = {
  version: 1,
  hiddenSegments: [],
  hiddenUniverses: [],
  clamps: {},
  refreshMs: DEFAULT_REFRESH_MS,
};

export function loadSettings(raw: string | null): Settings {
  if (!raw) return DEFAULT_SETTINGS;
  let parsed: any;
  try { parsed = JSON.parse(raw); } catch { return DEFAULT_SETTINGS; }
  if (!parsed || typeof parsed !== "object") return DEFAULT_SETTINGS;
  return {
    version: 1,
    hiddenSegments: Array.isArray(parsed.hiddenSegments) ? parsed.hiddenSegments : [],
    hiddenUniverses: Array.isArray(parsed.hiddenUniverses) ? parsed.hiddenUniverses : [],
    clamps: parsed.clamps && typeof parsed.clamps === "object" ? parsed.clamps : {},
    refreshMs: REFRESH_OPTIONS.includes(parsed.refreshMs) ? parsed.refreshMs : DEFAULT_REFRESH_MS,
  };
}

export function serializeSettings(s: Settings): string {
  return JSON.stringify(s);
}
