import { describe, it, expect, vi } from "vitest";
import { startServer } from "../src/server.js";
import type { ServerDeps } from "../src/server.js";
import type { Universe } from "../../shared/universe.js";

const baselines = { BTC: { priorClose: 100, price: 100 }, ETH: { priorClose: 50, price: 50 } };

function deps(extra: Partial<ServerDeps> = {}) {
  return {
    port: 0,
    seed: vi.fn(async (_u: Universe, _lb: number) => ({ ...baselines })),
    fetchPrices: vi.fn(async (_u: Universe) => new Map([["BTC", 110]])),
    ...extra,
  };
}

async function start(extra?: Partial<ServerDeps>) {
  const d = deps(extra);
  const srv = await startServer(d as any);
  const base = `http://localhost:${srv.address().port}`;
  return { srv, base, d };
}

describe("http server", () => {
  it("GET /api/snapshot returns seeded tiles", async () => {
    const { srv, base, d } = await start();
    const body = await (await fetch(`${base}/api/snapshot?universe=crypto&lookback=1`)).json();
    expect(d.seed).toHaveBeenCalledWith(expect.anything(), 1);
    expect(body.universeId).toBe("crypto");
    expect(body.tiles).toContainEqual(expect.objectContaining({ ticker: "BTC", price: 100, pct: 0 }));
    await srv.close();
  });

  it("passes lookback to seed", async () => {
    const { srv, base, d } = await start();
    await fetch(`${base}/api/snapshot?universe=crypto&lookback=30`);
    expect(d.seed).toHaveBeenCalledWith(expect.anything(), 30);
    await srv.close();
  });

  it("GET /api/prices returns current price/pct updates", async () => {
    const { srv, base } = await start();
    const body = await (await fetch(`${base}/api/prices?universe=crypto&lookback=1`)).json();
    expect(body.updates).toContainEqual({ ticker: "BTC", price: 110, pct: 0.1 });
    await srv.close();
  });

  it("re-seeds on a prices cache miss when no snapshot ran first", async () => {
    const { srv, base, d } = await start();
    await fetch(`${base}/api/prices?universe=crypto&lookback=1`);
    expect(d.seed).toHaveBeenCalled();
    await srv.close();
  });

  it("returns 404 for an unknown universe", async () => {
    const { srv, base } = await start();
    const res = await fetch(`${base}/api/snapshot?universe=nope&lookback=1`);
    expect(res.status).toBe(404);
    await srv.close();
  });

  it("404s an unknown path", async () => {
    const { srv, base } = await start();
    const res = await fetch(`${base}/api/nope`);
    expect(res.status).toBe(404);
    await srv.close();
  });

  it("returns 500 when seed throws", async () => {
    const { srv, base } = await start({
      seed: vi.fn(async () => { throw new Error("upstream failed"); }),
    });
    const res = await fetch(`${base}/api/snapshot?universe=crypto&lookback=1`);
    expect(res.status).toBe(500);
    await srv.close();
  });
});
