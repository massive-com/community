import type { Tile, SnapshotMsg, DiffMsg, SessionPhase } from "../../shared/protocol.js";

export class TileStore {
  private byTicker = new Map<string, Tile>();
  private order: string[] = [];
  private _session: SessionPhase = "closed";

  applySnapshot(msg: SnapshotMsg): void {
    this.byTicker.clear(); this.order = [];
    for (const t of msg.tiles) { this.byTicker.set(t.ticker, { ...t }); this.order.push(t.ticker); }
    this._session = msg.session;
  }
  applyDiff(msg: DiffMsg): void {
    this._session = msg.session;
    for (const u of msg.updates) {
      const t = this.byTicker.get(u.ticker);
      if (t) { t.price = u.price; t.pct = u.pct; }
    }
  }
  tiles(): Tile[] { return this.order.map((k) => this.byTicker.get(k)!); }
  session(): SessionPhase { return this._session; }
}
