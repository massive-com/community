# Futures Dashboard

<div align="center">
  <img src="../../../images/logo_new.png" alt="Project Logo" width="100%"/>
</div>

## Background

A futures contract is an agreement to buy or sell something at a fixed price on a future date. Every product, whether crude oil, gold, the S&P 500, or 10-year Treasuries, has many contracts trading at the same time. Each one expires in a different month, and the prices form a curve across expirations.

The shape of that curve carries information. When far-dated contracts trade above near-dated ones, the market is in **contango**, often signaling abundant supply or storage costs. When the opposite holds, the market is in **backwardation**, usually a sign of immediate scarcity. The dashboard reports annualized roll yield from the front contract to the next liquid contract, using the long-roll convention: contango is typically negative carry for long exposure, while backwardation is typically positive carry.

Many CME products also come in size variants (Standard, E-mini, Micro). The S&P 500 ships as ES (E-mini, $50/pt) and MES (Micro, $5/pt); WTI crude ships as CL (1,000 bbl) and MCL (100 bbl). Traders pick the size that matches the notional exposure they want.

This dashboard puts all of that on one screen, built on Massive's REST API. The same query patterns work across the 1,500+ futures product catalog spanning CME, CBOT, NYMEX, and COMEX. Reference: [docs](https://massive.com/docs/rest/futures/overview).

## What it looks like

```
┌── Status strip ─ logo · CME● CBOT● NYMEX● COMEX● · 1,545 products ─ docs↗ ─┐
├──────────┬────────────────────────────────────────────────────────────────┤
│ Search   │  ┌── Hero ─────────────────────────────────────────────────┐   │
│          │  │  ESM6  S&P 500  [E-mini│Micro]  REAL-TIME              │   │
│ ES NQ YM │  │                                                         │   │
│ ZB ZN    │  │   7,231.50    ▼ -29.50  -0.41%                          │   │
│ CL NG    │  │   bid 7228 · ask 7228.5 · spread 0.25                   │   │
│ GC SI HG │  │   L 7,213 ──────────●────────── H 7,280                 │   │
│ ...      │  │   1.18M vol · expires 45d · session ends 16:00          │   │
│          │  └─────────────────────────────────────────────────────────┘   │
│ Catalog  │                                                                 │
│  energy  │  ┌── Term Structure ──┬── 90-Day History ──┬── Position ───┐  │
│  ...     │  │  curve              │  area + volume     │  Contracts: 1│  │
│          │  │  contango  -3% roll │                    │  Notional: $X│  │
│          │  └─────────────────────┴────────────────────┴───────────────┘  │
│          │                                                                 │
│          │  ┌── Watchlist ──┬── Contracts ──┬── Time & Sales ──┐         │
│          │  │ symbol  last  │ ESM6 front    │ 14:30 7228.5 ×2  │         │
│          │  │ chg%   spark  │ ESU6          │ ...              │         │
│          │  └───────────────┴───────────────┴──────────────────┘         │
└──────────┴────────────────────────────────────────────────────────────────┘
```

## What's in each panel

| Panel | Purpose | Endpoints |
|-------|---------|-----------|
| Status strip | Massive logo, current CME Group venue state (open, maintenance, paused, closed), product count, REST polling cadence, link to the futures REST docs | Market Status, Exchanges, Products |
| Sidebar | Demo watchlist plus a reference catalog search across all 1,500+ products by code, name, or asset class. Catalog groups rank demo-ready products before thin reference products | Products |
| Hero card | The active contract front-and-center: ticker, full product name, size variant pills (E-mini / Micro), large price with up/down flash on update, change & change %, bid / ask / spread, day-range visualizer, REAL-TIME or DELAYED badge, expires-in countdown, next session event, and a clear quiet-product state when no recent tick exists | Snapshot, Aggregates, Contracts, Schedules |
| Position sizer | Contracts ↔ target notional input, total notional, per-contract notional, tick value, P&L per point. The sibling-size buttons compute and apply equivalent contract counts when switching between Standard, E-mini, Mini, and Micro products. FX products also show the exposure currency beside USD notional | Products (multipliers), Snapshot |
| Term structure | Settlement curve with contango/backwardation badge and annualized roll yield. Front-month dot is green, selected dot is amber. Click any point to load it in the hero | Contracts, Snapshot |
| 90-day history | Area chart with volume underlay for the selected contract | Aggregates |
| Watchlist | Sortable quote board: 24 futures products across six asset classes, front-month per product (picked by session volume), last price, change %, volume, sparkline | Contracts, Snapshot, Aggregates |
| Contracts table | Sortable list of every active contract for the selected product. Front-month row carries a `front` badge; stale contracts are dimmed and toggleable | Contracts, Snapshot |
| Time & sales | Recent tick-level trades with aggressor coloring estimated from the nearest available quote at or before each trade, plus a tape-speed indicator derived from the recent trade batch | Trades, Quotes, Snapshot |

The dashboard auto-selects the front-month contract when you switch products. Click any other contract on the curve, in the contracts table, or in the watchlist to lock the workstation to that ticker. The URL updates as `/?p=ES&t=ESM6`, so demo states can be bookmarked and shared. Use the Position Sizing sibling buttons when you want to preserve approximate notional exposure while switching from E-mini to Micro, Standard to Micro, or another supported size pair.

## Trader-aware data handling

Several quirks of futures data only show up when you actually use the API. The dashboard handles them so you don't have to:

- **Stale snapshots.** Many far-dated contracts have a `session.close` field populated from their last traded session, which can be years old. Showing those values on a curve produces nonsense (E-mini S&P contracts that "drop from 7,200 to 2,400" three years out). The dashboard checks `last_trade.last_updated` and the most recent daily aggregate, treating anything without activity in the last 5 days as stale. Stale contracts are excluded from the curve, classifier, roll yield, and front-month picker; they remain visible in the contracts table behind a "show inactive" toggle.
- **Front month by liquidity, not date.** During roll periods, the contract with the nearest expiration is often less liquid than the next one out (e.g., GCK6 with 14 contracts of volume vs. GCM6 with 70,000). The watchlist and curve front-month indicators pick the highest-volume liquid contract.
- **Change percent from prior settlement.** The snapshot's `previous_settlement` field is often zero. The dashboard derives the prior reference from the most recent settled daily aggregate.
- **Long-roll convention.** Roll yield is calculated as `(front - next) / front`, annualized by the day gap between the two contracts. That keeps contango negative and backwardation positive for long exposure.
- **Aggressor estimate from quotes.** Time and sales compares each recent trade against the nearest available quote at or before the trade timestamp, rather than comparing every trade to the latest quote.
- **Tick-precise prices.** Different products quote in very different magnitudes (6J trades at 0.006381 USD/JPY, ES trades at 7,200 index points). Prices are formatted with adaptive precision so tick-level differences are always visible.
- **Notional from live multipliers.** The position sizer reads `unit_of_measure_qty` from the products endpoint, falling back to a hardcoded value per family if the live data is missing. That keeps the calculator accurate even if the dashboard is queried with a different point-in-time `date` filter.
- **Reference catalog versus liquid demo flow.** The products endpoint exposes the full futures product universe, including thin fuel-oil spreads, weather, freight, housing, and other products that may have valid specs but no recent tick data. The sidebar ranks demo-ready products first, and selected thin products show a quiet-product state instead of empty panels.
- **Open interest gap.** Massive's futures snapshot docs currently list `details.open_interest`, but the live `/futures/vX/snapshot` response and the installed JavaScript SDK type do not include that field for tested contracts. The hero reserves the slot as `Not returned` so the field appears automatically once the API response includes it.
- **Market status during the maintenance break.** Futures venues can report `close` during the daily maintenance window. The status strip labels this as maintenance when it occurs during the 4:00-5:00 PM CT break, rather than showing alarming red dots.

## Disclaimer

**Warning:** The examples, demos, and outputs produced with this project are generated by artificial intelligence and large language models. You acknowledge that this project and any outputs are provided "AS IS", may not always be accurate and may contain material inaccuracies even if they appear accurate because of their level of detail or specificity, outputs may not be error free, accurate, current, complete, or operate as you intended, you should not rely on any outputs or actions without independently confirming their accuracy, and any outputs should not be treated as financial or legal advice. You remain responsible for verifying the accuracy, suitability, and legality of any output before relying on it.

## Requirements

- Node.js 18.18+ (Node 20+ recommended)
- npm, pnpm, or yarn
- Massive API key with futures access. Real-time data requires a futures plan with real-time entitlement, while lower tiers can return delayed data. The dashboard labels delayed snapshots as `DELAYED`.

## Quickstart

1. **Clone the repository:**
   ```bash
   git clone https://github.com/massive-com/community.git
   cd community/examples/rest/futures-dashboard
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up credentials:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local and add your API key
   ```

   Your `.env.local` file should contain:
   ```
   MASSIVE_API_KEY=your-api-key
   ```

4. **Get your key:** Sign up at [massive.com](https://massive.com/) and copy your API key from the dashboard.

5. **Run the dev server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000).

To build for production:
```bash
npm run lint
npm run typecheck
npm run build
npm run start
```

## Local QA

Run these checks before recording or publishing changes:

```bash
npm run lint
npm run typecheck
npm run build
```

The lint command uses ESLint directly, so it is safe for CI and non-interactive terminals.

## Troubleshooting

- If the app shows `MASSIVE_API_KEY is not set`, copy `.env.example` to `.env.local` and add a valid key.
- If panels show `API unavailable` or delayed badges, confirm the key has futures access and the expected real-time entitlement.
- If a product has no liquid contracts, stale far-dated contracts remain available behind the `show inactive` toggle in the contracts table.

## Curated products

The watchlist and sidebar default to a fixed set of major contracts. Where a sibling Micro or E-mini exists, the family is wired in so the hero card shows variant pills and the position sizer can compute equivalent contract counts.

| Group | Standard / E-mini | Micro / Mini |
|-------|-------------------|--------------|
| Equity Indices | ES (S&P 500), NQ (Nasdaq-100), YM (Dow), RTY (Russell 2000) | MES, MNQ, MYM, M2K |
| Rates | ZB (30Y), ZN (10Y), ZF (5Y), ZT (2Y) | N/A |
| Energy | CL (WTI Crude), NG (Nat Gas), HO (Heating Oil), RB (RBOB Gas) | MCL, QG |
| Metals | GC (Gold), SI (Silver), HG (Copper), PL (Platinum) | MGC, SIL, MHG |
| FX | 6E (EUR), 6B (GBP), 6J (JPY), 6A (AUD) | M6E, M6B, MJY, M6A |
| Agriculture | ZC (Corn), ZS (Soybeans), ZW (Wheat), LE (Live Cattle) | N/A |

The full catalog (1,500+ products) is reachable through the sidebar search.

## Project layout

```
app/
  api/
    overview/route.ts          - Status strip data (market status + exchanges)
    products/route.ts          - Full product catalog grouped by asset class
    macro/route.ts             - 24 product watchlist tiles with sparklines
    product/[code]/route.ts    - Term structure, contracts, curve analytics, family variants
    contract/[ticker]/route.ts - Snapshot, history, trades, quotes, specs, staleness
    schedule/[code]/route.ts   - Upcoming session events for a product
  layout.tsx
  page.tsx                     - Composes all panels and handles auto-selection
components/
  StatusStrip.tsx              - Logo, exchange status, product count, docs link
  Sidebar.tsx                  - Curated picker + catalog + full-catalog search
  HeroCard.tsx                 - Active contract focus with size variant pills
  PositionSizer.tsx            - Notional / tick value / sibling-size translator
  Watchlist.tsx                - 24-product quote board
  TermStructure.tsx            - Curve chart + classification
  HistoryChart.tsx             - 90-day area + volume
  ContractsTable.tsx           - Sortable contract list with front/stale badges
  TimeAndSales.tsx             - Tick-level trades with aggressor coloring
  Sparkline.tsx                - Inline 14-day price sparklines
lib/
  massive.ts                   - Server-only SDK wrapper (@massive.com/client-js)
  curated-products.ts          - 24 watchlist entries plus family variants
  format.ts                    - Number, percent, USD, tick-precision price helpers
  types.ts                     - Shared response types
public/
  massive-logo-white.svg       - Brand mark in the status strip
```

The `lib/massive.ts` file is the only place that talks to the Massive API. Every other piece of code goes through the `/api/*` route handlers, so the API key never leaves the server.

## Endpoints used

- [Products](https://massive.com/docs/rest/futures/products) (`/futures/vX/products`)
- [Contracts](https://massive.com/docs/rest/futures/contracts) (`/futures/vX/contracts`)
- [Contracts Snapshot](https://massive.com/docs/rest/futures/snapshots/contracts-snapshot) (`/futures/vX/snapshot`)
- [Aggregates](https://massive.com/docs/rest/futures/aggregates) (`/futures/vX/aggs/{ticker}`)
- [Trades](https://massive.com/docs/rest/futures/trades-quotes/trades) (`/futures/vX/trades/{ticker}`)
- [Quotes](https://massive.com/docs/rest/futures/trades-quotes/quotes) (`/futures/vX/quotes/{ticker}`)
- [Schedules](https://massive.com/docs/rest/futures/schedules) (`/futures/vX/schedules`)
- [Market Status](https://massive.com/docs/rest/futures/market-operations/market-status) (`/futures/vX/market-status`)
- [Exchanges](https://massive.com/docs/rest/futures/market-operations/exchanges) (`/futures/vX/exchanges`)

That covers every public REST endpoint in the futures product. For the broader picture, see the [Massive Futures overview](https://massive.com/docs/rest/futures/overview).
