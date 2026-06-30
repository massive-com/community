import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import {
  DEFAULT_SETTINGS, STORAGE_KEY, loadSettings, serializeSettings,
  type Settings,
} from "./settingsStore.js";

interface Ctx {
  settings: Settings;
  setHiddenSegments: (v: Settings["hiddenSegments"]) => void;
  setHiddenUniverses: (v: string[]) => void;
  setClamps: (v: Record<number, number>) => void;
  setRefreshMs: (v: number) => void;
}

const SettingsContext = createContext<Ctx | null>(null);

function read(): Settings {
  try { return loadSettings(localStorage.getItem(STORAGE_KEY)); } catch { return DEFAULT_SETTINGS; }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(read);
  const commit = useCallback((next: Settings) => {
    setSettings(next);
    try { localStorage.setItem(STORAGE_KEY, serializeSettings(next)); } catch { /* ignore quota */ }
  }, []);
  const value: Ctx = {
    settings,
    setHiddenSegments: (v) => commit({ ...settings, hiddenSegments: v }),
    setHiddenUniverses: (v) => commit({ ...settings, hiddenUniverses: v }),
    setClamps: (v) => commit({ ...settings, clamps: v }),
    setRefreshMs: (v) => commit({ ...settings, refreshMs: v }),
  };
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Ctx {
  const c = useContext(SettingsContext);
  if (!c) throw new Error("useSettings must be used within SettingsProvider");
  return c;
}
