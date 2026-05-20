# Short Squeeze Monitor — Design Spec

**Date:** 2026-05-20
**Branch:** short-squeeze
**Location:** `examples/websocket/short-squeeze-monitor/`

## Overview

A real-time short squeeze detector that streams three Massive WebSocket feeds simultaneously (trades, per-second agg bars, and LULD bands) and fires alerts when signal thresholds indicate a squeeze is forming or reversing. Follows the two-file pattern established by the LULD monitor: a raw firehose for exploration and a smart monitor for production use.

## Audiences

Primary: quantitative analysts and algorithmic traders who want early warning of momentum events. Secondary: fintech developers building squeeze scanners or momentum dashboards who want to understand how to combine multiple Massive WebSocket streams.

## File Structure

```
examples/websocket/short-squeeze-monitor/
├── basic_firehose.py     # raw stream dump for all three feeds
├── squeeze_monitor.py    # signal detection and alert output
├── pyproject.toml        # uv project, massive>=2.3.2
├── .env.example          # MASSIVE_API_KEY template
└── README.md
```

## Data Streams

Three subscriptions on a single `WebSocketClient` connection:

| Stream | Subscription | Model | Purpose |
|---|---|---|---|
| Trades | `T.*` or `T.TICKER` | `EquityTrade` | Volume velocity, uptick/downtick ratio, price tracking |
| Agg bars | `A.*` or `A.TICKER` | `EquityAgg` | Per-second OHLCV, price velocity baseline |
| LULD | `LULD.*` or `LULD.TICKER` | `LimitUpLimitDown` | Band proximity, halt/resumption events |

## Operating Modes

**Market-wide** (no `--ticker`): subscribes to `T.*`, `A.*`, `LULD.*`. Monitors all US equities. No REST pre-load. Float % omitted from output.

**Watchlist** (`--ticker GME AMC CAR`): subscribes to specific tickers only. At startup, queries `FinancialsClient.list_stocks_floats()` and `FinancialsClient.list_financials_ratios()` for each ticker to pre-load `free_float_percent` and `average_volume`. These appear as context fields on SQUEEZE and REVERSAL alerts.

## Per-Ticker Rolling State

Each ticker maintains independent state. No state is shared between tickers.

```python
@dataclass
class TickerState:
    trades: deque        # (timestamp_ms, price, size, is_uptick) — last N seconds
    aggs: deque          # (timestamp_ms, close, volume) — last N seconds
    last_price: float    # most recent trade price
    last_luld: LimitUpLimitDown | None  # most recent LULD event for this ticker
    cooldowns: dict      # alert_type -> last_fired_timestamp
    # watchlist mode only:
    free_float_pct: float | None
    avg_volume: float | None
```

Deques are trimmed on every event: entries older than `--window` seconds are discarded before signal evaluation.

## Signal Logic

### SQUEEZE ALERT

All three conditions must be true simultaneously:

1. **Volume velocity**: shares traded in the last 10 seconds >= `--vol-multiplier` x the per-second average over the full window. Formula: `(last_10s_volume / 10) >= (window_volume / window_seconds) * vol_multiplier`
2. **Price velocity**: most recent trade price >= `--price-pct`% above the oldest agg close in the window
3. **Uptick ratio**: >= `--uptick-ratio` fraction of trades in the window landed on an uptick (current price > previous trade price)

### REVERSAL ALERT

Stateless. Both conditions must be true simultaneously:

1. **Price velocity**: most recent trade price <= `-price-pct`% below the oldest agg close in the window
2. **Downtick dominance**: >= `--uptick-ratio` fraction of trades in the window landed on a downtick

### LULD Signals

Derived by combining the most recent LULD bands with last known trade price:

- **UPPER BAND**: `(last_luld.high_price - last_price) / last_price <= band_pct / 100`
- **LOWER BAND**: `(last_price - last_luld.low_price) / last_price <= band_pct / 100`
- **HALT**: indicator 17 present in `last_luld.indicators`
- **RESUMPTION**: indicator 18 present in `last_luld.indicators`

LULD signals evaluate on every LULD event. UPPER/LOWER BAND also re-evaluate on every trade event (price may move into band range between LULD updates).

### Alert Cooldown

After any alert fires for a ticker, that alert type is suppressed for `--cooldown` seconds for that ticker. Prevents the same signal from printing every second while conditions persist. Cooldown is per ticker per alert type (a SQUEEZE ALERT cooldown does not suppress a REVERSAL ALERT).

## Output Format

### basic_firehose.py

Requires `--ticker`. Prints all three streams interleaved, prefixed by stream type:

```
09:31:02  TRADE  GME   $41.20  x500    uptick   exch:4
09:31:02  AGG    GME   O:41.10 H:41.25 L:41.08 C:41.20  vol:12400
09:31:03  LULD   GME   upper:$45.00  lower:$38.00  ind:[]
```

### squeeze_monitor.py

One alert per line, fired as thresholds are crossed:

```
09:32:14  GME   SQUEEZE ALERT  | $42.30 (+4.1%)  | vol: 8.2x  | uptick: 78%  | float: 4.2%
09:32:45  GME   REVERSAL ALERT | $39.80 (-2.3%)  | vol: 2.1x  | downtick: 69%
09:33:01  CAR   UPPER BAND     | $51.90  | band: $52.40  | gap: 1.0%
09:33:15  GME   HALT           | $42.10  | upper: $45.00  | lower: $38.00
09:33:45  GME   RESUMPTION     | $42.10  | upper: $45.00  | lower: $38.00
```

Float % appears only in watchlist mode on SQUEEZE and REVERSAL alerts. LULD alerts show band values regardless of mode.

## CLI Args

| Arg | Default | Description |
|---|---|---|
| `--ticker TICKER [...]` | all | Watchlist mode; omit for market-wide |
| `--window` | 60 | Rolling window in seconds |
| `--vol-multiplier` | 3.0 | Volume burst multiplier vs per-second average |
| `--price-pct` | 2.0 | Price move threshold (%) |
| `--uptick-ratio` | 0.65 | Uptick/downtick dominance fraction |
| `--band-pct` | 1.0 | LULD band proximity threshold (%) |
| `--cooldown` | 30 | Seconds between repeated alerts per ticker per type |

## REST Integration (Watchlist Mode Only)

At startup, before opening the WebSocket connection, the monitor queries:

- `FinancialsClient.list_stocks_floats(ticker=t)` — retrieves `free_float_percent`
- `FinancialsClient.list_financials_ratios(ticker=t)` — retrieves `average_volume`

Both calls use `RESTClient` with the same `MASSIVE_API_KEY`. Results are stored in the ticker's `TickerState`. If a ticker returns no data (unlisted, no coverage), the fields are `None` and omitted from output rather than crashing.

Note: Massive provides free float percentage, not short interest percentage. True short interest (shares sold short as % of float) is published by FINRA twice monthly and is not available in the Massive API. Free float is a related and useful signal: a tight float amplifies squeeze magnitude.

## Error Handling

- Missing `MASSIVE_API_KEY`: raise `ValueError` at startup with a clear message (matches existing demo pattern)
- REST pre-load failure for a ticker: log a warning, continue with `None` values, do not block startup
- WebSocket disconnect: rely on the Massive SDK's built-in reconnection behavior
- Tickers with insufficient trade history to fill the window: signals require at least 2 trades and 2 agg bars before evaluating; fewer than that produces no alerts

## Dependencies

```toml
[project]
dependencies = [
    "massive>=2.3.2",
    "python-dotenv>=1.0.0",
]
```

No additional dependencies. Python 3.11+ for `ZoneInfo` without backport.
