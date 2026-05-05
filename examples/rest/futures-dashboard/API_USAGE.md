# API Usage Profile

A note for the futures API team: this document describes how many requests this dashboard makes against `/futures/v1/*` endpoints, broken down by user flow. Numbers are empirical, captured against the live staging API on 2026-05-05 with cache-busted client requests.

## TL;DR

| Flow | Upstream calls | Notes |
|------|----------------|-------|
| First page load (cold cache) | **70** | One-shot burst over ~3.6s wall time |
| Idle dashboard, per minute | **135** | ~2.3 calls/sec, sustained |
| Product switch | **17** | New `/api/product/<code>` + new `/api/contract/<ticker>` |
| Ticker switch (within same product) | **5** | Just refreshes the contract detail panel |

These are **per Next.js server instance**, not per browser. With Next's built-in route response cache (`revalidate = 30` on the heavy endpoints), N concurrent browsers connected to the same server share a single 30-second upstream poll cycle for the cached routes.

A naïve build (no cap on the prior-aggregates fan-out) issued **191 cold-load** and **256 idle/min** calls. The numbers above include the cap described under "Optimizations applied."

## How to reproduce

The dashboard ships with a counter at `GET /api/stats` (and `POST /api/stats?reset=1` to zero it). After running any flow, hit the stats endpoint to see the breakdown.

```bash
# Reset
curl -X POST "http://localhost:3000/api/stats?reset=1"

# Cold-page-load simulation
curl -s "http://localhost:3000/api/overview?cb=$RANDOM" -o /dev/null &
curl -s "http://localhost:3000/api/products?cb=$RANDOM" -o /dev/null &
curl -s "http://localhost:3000/api/macro?cb=$RANDOM" -o /dev/null &
curl -s "http://localhost:3000/api/product/CL?cb=$RANDOM" -o /dev/null &
curl -s "http://localhost:3000/api/schedule/CL?cb=$RANDOM" -o /dev/null &
wait
curl -s "http://localhost:3000/api/contract/CLM6?cb=$RANDOM" -o /dev/null

# Read counters
curl -s "http://localhost:3000/api/stats" | jq
```

Use `?cb=...` to bypass Next.js's route cache and exercise upstream for every request.

## Per-route fan-out

The dashboard exposes 7 internal `/api/*` routes that proxy through `@massive.com/client-js`. Each internal route fans out to one or more upstream Massive calls.

| Internal route | Upstream calls | Per call | Composition |
|----------------|----------------|----------|-------------|
| `/api/overview` | `market_status` × 1, `exchanges` × 1 | **2** | Status strip + venue indicators |
| `/api/products` | `products` × 1 (auto-paginates the SDK across the 1,545-product catalog if needed) | **1–2** | Sidebar catalog + search |
| `/api/macro` | `products` × 1 (one batched call), `contracts` × **24** (one per curated product), `snapshot` × 1 (batched), `aggregates` × **24** (sparkline per front month) | **50** | 24-tile watchlist |
| `/api/product/[code]` | `products` × 1, `contracts` × 1, `snapshot` × 1, `aggregates` × **min(N, 8)** where N = active contract count | **4–11** | Term structure + contracts table |
| `/api/contract/[ticker]` | `snapshot` × 1, `aggregates` × 1 (90-day history), `trades` × 1, `quotes` × 1, `contracts` × 1 (specs lookup) | **5** | Hero, position sizer, history, time & sales |
| `/api/schedule/[code]` | `schedules` × 1 | **1** | Next-session indicator (6s timeout, returns `[]` on slow products) |
| `/api/stats` | none | **0** | Local counter readout (only the dashboard needs it) |

## Polling cadences (steady state)

| Internal route | Browser refresh interval | Upstream cost per minute (per server) |
|----------------|--------------------------|----------------------------------------|
| `/api/overview` | 30s | 2 calls × 2/min = **4** |
| `/api/products` | mount-only (revalidate on focus) | ~0 ongoing |
| `/api/macro` | 30s | 50 × 2 = **100** |
| `/api/product/[code]` | 60s | (4–11) × 1 ≈ **8 (avg)** |
| `/api/contract/[ticker]` | 15s | 5 × 4 = **20** |
| `/api/schedule/[code]` | mount-only | ~0 ongoing |

Per browser per minute: ~135 upstream calls.

## Burst behavior

Cold load peaks at **~50 req/sec instantaneous** because every panel fires its initial fetch in parallel as the page mounts. Production load testing should plan for that burst, not just steady state.

Product-switch bursts scale with product code — same 5-call contract panel + a fresh product page. With the cap in place, even high-contract products like CL stay around 17 calls, finishing in <2s.

## Endpoint-level breakdown (idle minute, post-optimization)

```
contracts      53   (24×2 macro polls + 1 product + 1 contract×4)
aggregates     60   (24×2 macro spark + 8 product priors + 1 history×4)
snapshot        7   (macro×2 + product×1 + contract×4)
trades          4   (contract×4)
quotes          4   (contract×4)
products        3   (macro×2 + product×1)
market_status   2   (overview×2)
exchanges       2   (overview×2)
total         135
```

The two heaviest endpoints are `aggregates` (44%) and `contracts` (39%).

## Optimizations applied

1. **Cap prior-aggregates fan-out at 8 contracts** (`/api/product/[code]`). The curve classifier and roll-yield calc only need the front 8 contracts; per-row change% on far-dated illiquid contracts is a minor table affordance. Without the cap, CL (129 active contracts) issued **129 aggregates calls per /api/product/CL request**. With the cap, every product page issues at most 8.
   - Cold-load aggregates: **154 → 33** calls.
   - Idle/min aggregates: **181 → 60** calls.
2. **6-second timeout on `/api/schedule/[code]`** because the upstream call hangs for unknown product codes. Returns `{ events: [] }` on timeout so the UI degrades gracefully.
3. **Route-handler revalidation** (`export const revalidate = 30`) on overview/macro/product. Next.js caches the route response for 30s, so concurrent users on the same server share one upstream poll per cycle instead of fanning out per-user.
4. **Cached SDK client** across requests. The `restClient(...)` instance is constructed once per (key, baseUrl) tuple and reused.
5. **SWR client-side cache deduplication.** Hero, PositionSizer, HistoryChart, and TimeAndSales all read from `/api/contract/[ticker]` — SWR's keyed cache means they share one fetch instead of four.

## Further optimizations available

These are not implemented but would reduce upstream load if engineering needs more headroom:

1. **Cache `/api/products` for 6+ hours.** The product catalog rarely changes intraday. A long `revalidate` makes the catalog effectively free.
2. **Cache macro sparklines for 1+ hour.** The 14-day daily sparkline only changes once per day at session close. The 24 spark-aggregates calls per `/api/macro` could amortize to one call per day per ticker if cached separately.
3. **Lower `/api/contract/[ticker]` polling to 30s.** Real-time contract polling drives 20 of the 135 idle calls/min. Most desks tolerate 30s for an inactive contract; a 30s cadence drops it to 10/min.
4. **Defer `/api/schedule/[code]` until idle.** The schedule chip is purely informational and not on the critical path; a `requestIdleCallback`-style fetch removes 1 call from cold load.
5. **Group macro contracts call.** If `/futures/v1/contracts` accepted a `product_code.any_of` filter (or there were a `current-front-month` endpoint), the 24 sequential `contracts` calls in `/api/macro` could collapse to 1. This requires an API change, not a client one.
6. **Server-shared cache (Redis or similar)** in front of Next's per-instance route cache. Eliminates the per-server multiplier when running behind a load balancer.

## DDoS-relevant observations

- **There is no auth or rate limit at the dashboard's `/api/*` boundary.** A bot loading the page generates the same upstream burst as a real user. Engineering should consider per-IP limits at the dashboard layer, not just upstream.
- **Cache hit rate is the dominant variable.** A single Next.js server with 30s route cache absorbs N user fan-out into 1 upstream call. The DDoS risk is **dashboards-per-server**, not browsers-per-dashboard.
- **The catalog endpoint is the largest single payload** (1,545 products) but it's cached and infrequent — not a DDoS surface.
- **Product switching is the costliest user action** because it bypasses the contract polling cadence and forces a fresh fan-out. A user clicking through 10 products in 30s issues ~170 upstream calls.

## Open questions for engineering

1. Is there a planned multi-product `contracts` endpoint? Would let us collapse the 24 sequential macro calls.
2. Will `details.open_interest` start populating on `/futures/v1/snapshot`? Docs declare it; the API currently returns the field absent.
3. What's the recommended rate-limit posture for paid customers running internal dashboards like this? We can bake it into the polling cadence config if there are documented thresholds.
