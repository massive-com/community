import type { ServerMsg } from "../../shared/protocol.js";

// Polling REST client. Mirrors the old ws.ts surface (select / setLookback / setRefresh)
// so App.tsx is unchanged apart from the import. select/setLookback fetch a fresh
// snapshot; a timer polls /api/prices every refreshMs. No socket, no reconnect.
export function connect(onMsg: (m: ServerMsg) => void): {
  select: (id: string, lookback: number) => void;
  setLookback: (lookback: number) => void;
  setRefresh: (intervalMs: number) => void;
} {
  let universeId: string | null = null;
  let lookback = 1;
  let intervalMs = 5000;
  let timer: ReturnType<typeof setInterval> | null = null;
  let snapshotInFlight = false;
  let polling = false;

  const query = () => `universe=${encodeURIComponent(universeId!)}&lookback=${lookback}`;

  const fetchSnapshot = async () => {
    if (!universeId) return;
    snapshotInFlight = true;
    try {
      const r = await fetch(`/api/snapshot?${query()}`);
      if (!r.ok) { onMsg({ type: "error", message: `snapshot ${r.status}` }); return; }
      onMsg({ type: "snapshot", ...(await r.json()) });
    } catch (e) {
      onMsg({ type: "error", message: String(e) });
    } finally {
      snapshotInFlight = false;
    }
  };

  // A failed poll keeps the last view and retries next tick. Skip while a snapshot is in
  // flight or a prior poll has not returned, so requests never pile up.
  const poll = async () => {
    if (!universeId || snapshotInFlight || polling) return;
    polling = true;
    try {
      const r = await fetch(`/api/prices?${query()}`);
      if (r.ok) onMsg({ type: "diff", ...(await r.json()) });
    } catch {
      /* keep last view */
    } finally {
      polling = false;
    }
  };

  const restart = () => {
    if (timer) clearInterval(timer);
    timer = setInterval(poll, intervalMs);
  };

  return {
    select: (id, lb) => { universeId = id; lookback = lb; fetchSnapshot(); restart(); },
    setLookback: (lb) => { lookback = lb; fetchSnapshot(); },
    setRefresh: (ms) => { intervalMs = ms; restart(); },
  };
}
