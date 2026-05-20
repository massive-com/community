# Short Squeeze Monitor

Real-time short squeeze detector using Massive's WebSocket API. Streams
trades, per-second agg bars, and LULD price bands simultaneously. Fires
alerts when signal thresholds indicate a squeeze is forming or a reversal
is underway.

## How it works

Three WebSocket feeds run on a single connection. For each ticker, a
rolling 60-second window of trade ticks and per-second bars is maintained
in memory. After every incoming message, three signals are evaluated:

**SQUEEZE ALERT** fires when all three conditions are true at once:

- Volume burst: shares traded in the last 10 seconds are at least 3x the
  per-second average across the full window
- Price velocity: current price is at least 2% above the oldest bar close
  in the window
- Uptick dominance: at least 65% of trades in the window landed on an uptick

**REVERSAL ALERT** fires when both conditions are true (stateless — no
prior squeeze required):

- Price velocity: current price is at least 2% below the oldest bar close
- Downtick dominance: at least 65% of trades in the window landed on a downtick

**LULD alerts** fire when:

- `UPPER BAND` or `LOWER BAND`: current price within 1% of the LULD band
- `HALT`: indicator 17 in the LULD stream
- `RESUMPTION`: indicator 18 in the LULD stream

Each alert type carries a 30-second cooldown per ticker to prevent the
same signal from printing every second while conditions persist.

## Setup

Copy `.env.example` to `.env` and add your Massive API key:

```
MASSIVE_API_KEY=your_api_key_here
```

Install dependencies:

```bash
uv sync
```

## Usage

**Market-wide mode** (monitors all US equities):

```bash
uv run squeeze_monitor.py
```

**Watchlist mode** (pre-loads float data, monitors specific tickers):

```bash
uv run squeeze_monitor.py --ticker GME AMC CAR
```

**Adjust thresholds:**

```bash
uv run squeeze_monitor.py --ticker GME --vol-multiplier 2.0 --price-pct 1.5 --uptick-ratio 0.60
```

**Raw stream exploration** (see the data before filtering):

```bash
uv run basic_firehose.py --ticker GME
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--ticker` | all | Watchlist mode. Omit for market-wide. |
| `--window` | 60 | Rolling window in seconds |
| `--vol-multiplier` | 3.0 | Volume burst multiplier vs per-second average |
| `--price-pct` | 2.0 | Price move threshold (%) |
| `--uptick-ratio` | 0.65 | Uptick/downtick dominance fraction |
| `--band-pct` | 1.0 | LULD band proximity threshold (%) |
| `--cooldown` | 30 | Seconds between repeated alerts per ticker per type |

## Output

```
09:32:14  GME   SQUEEZE ALERT  | $42.30 (+4.1%)  | vol: 8.2x  | uptick: 78%  | float: 4.2%
09:32:45  GME   REVERSAL ALERT | $39.80 (-2.3%)  | vol: 2.1x  | downtick: 69%
09:33:01  CAR   UPPER BAND     | $51.90  | band: $52.40  | gap: 1.0%
09:33:15  GME   HALT           | $42.10  | upper: $45.00  | lower: $38.00
```

Float percentage appears in watchlist mode only. It reflects the
percentage of total shares that are freely tradeable (from Massive's
float data). A tighter float amplifies squeeze magnitude. Note that this
is not the same as short interest percentage, which measures shares sold
short as a fraction of float and requires data published by FINRA
twice monthly.

## Requirements

Requires a Massive API key with WebSocket access. Market-wide mode
streams `T.*`, `A.*`, and `LULD.*` simultaneously and generates
significant data volume — a Starter plan or higher is recommended.
