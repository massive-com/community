import type { Segment } from "./universe.js";

// Re-export Segment so backend/frontend modules can import it from protocol.
export type { Segment } from "./universe.js";

export type SessionPhase = "premarket" | "regular" | "afterhours" | "closed" | "open24";

export interface Tile {
  ticker: string;
  name: string;
  group: string;
  marketCap: number;
  priorClose: number;
  price: number;
  pct: number; // (price - priorClose) / priorClose, 0 when priorClose<=0
}

export interface TileUpdate {
  ticker: string;
  price: number;
  pct: number;
}

// server -> client
export interface SnapshotMsg {
  type: "snapshot";
  universeId: string;
  label: string;
  segment: Segment;
  session: SessionPhase;
  tiles: Tile[];
}
export interface DiffMsg {
  type: "diff";
  session: SessionPhase;
  updates: TileUpdate[];
}
export interface ErrorMsg {
  type: "error";
  message: string;
}
export type ServerMsg = SnapshotMsg | DiffMsg | ErrorMsg;
