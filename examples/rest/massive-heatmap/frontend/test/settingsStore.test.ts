import { describe, it, expect } from "vitest";
import { DEFAULT_SETTINGS, loadSettings, serializeSettings } from "../src/settingsStore.js";

describe("settings store", () => {
  it("returns defaults for empty/invalid storage", () => {
    expect(loadSettings(null)).toEqual(DEFAULT_SETTINGS);
    expect(loadSettings("not json")).toEqual(DEFAULT_SETTINGS);
  });
  it("round-trips through serialize/load", () => {
    const s = { ...DEFAULT_SETTINGS, hiddenSegments: ["futures"], hiddenUniverses: ["dow30"] };
    expect(loadSettings(serializeSettings(s as any))).toEqual(s);
  });
  it("migrates missing version to current and keeps known fields", () => {
    const raw = JSON.stringify({ hiddenSegments: ["crypto"] });
    const loaded = loadSettings(raw);
    expect(loaded.version).toBe(1);
    expect(loaded.hiddenSegments).toEqual(["crypto"]);
    expect(loaded.hiddenUniverses).toEqual([]);
    expect(loaded.clamps).toEqual({});
  });
  it("round-trips clamp overrides", () => {
    const s = { ...DEFAULT_SETTINGS, clamps: { 1: 0.06, 365: 1.2 } };
    expect(loadSettings(serializeSettings(s as any)).clamps).toEqual({ 1: 0.06, 365: 1.2 });
  });
});
