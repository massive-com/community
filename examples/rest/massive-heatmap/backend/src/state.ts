import type { Constituent } from "../../shared/universe.js";
import type { Tile, TileUpdate } from "../../shared/protocol.js";

export class UniverseState {
  private rows = new Map<string, Tile>();

  constructor(constituents: Constituent[]) {
    for (const c of constituents) {
      this.rows.set(c.ticker, {
        ticker: c.ticker, name: c.name, group: c.group, marketCap: c.marketCap,
        priorClose: 0, price: 0, pct: 0,
      });
    }
  }
  seed(baselines: Record<string, { priorClose: number; price: number }>): void {
    for (const [ticker, b] of Object.entries(baselines)) {
      const row = this.rows.get(ticker);
      if (!row) continue;
      row.priorClose = b.priorClose; row.price = b.price;
      row.pct = b.priorClose > 0 ? (b.price - b.priorClose) / b.priorClose : 0;
    }
  }
  applyPrice(ticker: string, price: number): void {
    const row = this.rows.get(ticker);
    if (!row) return;
    row.price = price;
    row.pct = row.priorClose > 0 ? (price - row.priorClose) / row.priorClose : 0;
  }
  // Current price/pct for every tile. /api/prices returns the full set each poll, so
  // there is no per-call diff tracking to maintain.
  updates(): TileUpdate[] {
    return [...this.rows.values()].map((r) => ({ ticker: r.ticker, price: r.price, pct: r.pct }));
  }
  tiles(): Tile[] { return [...this.rows.values()].map((r) => ({ ...r })); }
}
