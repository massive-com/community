import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { Universe, Constituent, Segment } from "../../shared/universe.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const UNIVERSE_DIR = join(HERE, "..", "..", "universes");
const SEGMENTS: Segment[] = ["stocks", "etfs", "crypto", "forex", "futures", "indices"];

export function listUniverseIds(): string[] {
  return readdirSync(UNIVERSE_DIR).filter((f) => f.endsWith(".json")).map((f) => f.replace(/\.json$/, ""));
}
function isConstituent(x: unknown): x is Constituent {
  const c = x as Constituent;
  return !!c && typeof c.ticker === "string" && typeof c.wsSymbol === "string"
    && typeof c.name === "string" && typeof c.group === "string" && typeof c.marketCap === "number";
}
export function loadUniverse(id: string): Universe {
  if (!listUniverseIds().includes(id)) throw new Error(`Unknown universe: ${id}`);
  const raw = JSON.parse(readFileSync(join(UNIVERSE_DIR, `${id}.json`), "utf8")) as Universe;
  if (!SEGMENTS.includes(raw.segment)) throw new Error(`Bad segment in ${id}: ${raw.segment}`);
  if (!Array.isArray(raw.constituents) || !raw.constituents.every(isConstituent)) throw new Error(`Invalid constituents in ${id}`);
  return raw;
}
