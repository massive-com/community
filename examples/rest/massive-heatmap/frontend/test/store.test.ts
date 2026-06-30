import { describe, it, expect } from "vitest";
import { TileStore } from "../src/store.js";
import type { SnapshotMsg, DiffMsg } from "../../shared/protocol.js";

const snap: SnapshotMsg = {
  type: "snapshot", universeId: "crypto", label: "Crypto", segment: "crypto", session: "open24",
  tiles: [{ ticker: "BTC", name: "Bitcoin", group: "L1", marketCap: 100, priorClose: 100, price: 100, pct: 0 }],
};

describe("TileStore", () => {
  it("applySnapshot replaces tiles", () => {
    const s = new TileStore(); s.applySnapshot(snap);
    expect(s.tiles()[0].ticker).toBe("BTC");
    expect(s.session()).toBe("open24");
  });
  it("applyDiff updates price/pct in place", () => {
    const s = new TileStore(); s.applySnapshot(snap);
    const diff: DiffMsg = { type: "diff", session: "open24", updates: [{ ticker: "BTC", price: 110, pct: 0.1 }] };
    s.applyDiff(diff);
    expect(s.tiles()[0].price).toBe(110);
    expect(s.tiles()[0].pct).toBeCloseTo(0.1);
  });
});
