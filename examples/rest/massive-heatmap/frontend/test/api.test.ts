import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { connect } from "../src/api.js";

const snapshotBody = { universeId: "sp500", label: "S&P 500", segment: "stocks", session: "regular", tiles: [] };
const pricesBody = { session: "regular", updates: [{ ticker: "AAPL", price: 1, pct: 0 }] };

function mockFetch() {
  return vi.fn(async (input: string) => ({
    ok: true,
    status: 200,
    json: async () => (input.includes("/api/snapshot") ? snapshotBody : pricesBody),
  })) as unknown as typeof fetch;
}

describe("api client", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal("fetch", mockFetch()); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("select fetches a snapshot and emits it tagged", async () => {
    const msgs: any[] = [];
    const c = connect((m) => msgs.push(m));
    c.select("sp500", 1);
    await vi.waitFor(() => expect(msgs.find((m) => m.type === "snapshot")).toBeTruthy());
    expect(msgs[0]).toMatchObject({ type: "snapshot", universeId: "sp500", label: "S&P 500" });
  });

  it("polls /api/prices on the interval and emits a tagged diff", async () => {
    const msgs: any[] = [];
    const c = connect((m) => msgs.push(m));
    c.select("sp500", 1);
    c.setRefresh(2000);
    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(msgs.find((m) => m.type === "diff")).toBeTruthy());
    expect(msgs.find((m) => m.type === "diff")).toMatchObject({ type: "diff", updates: pricesBody.updates });
  });

  it("emits an error when the snapshot request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) })) as unknown as typeof fetch);
    const msgs: any[] = [];
    const c = connect((m) => msgs.push(m));
    c.select("sp500", 1);
    await vi.waitFor(() => expect(msgs.find((m) => m.type === "error")).toBeTruthy());
    expect(msgs.find((m) => m.type === "error")).toMatchObject({ type: "error", message: "snapshot 500" });
  });
});
