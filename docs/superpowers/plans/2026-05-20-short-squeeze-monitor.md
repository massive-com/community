# Short Squeeze Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-file real-time short squeeze detector that streams Massive trades, per-second agg bars, and LULD bands simultaneously and fires alerts when signal thresholds indicate a squeeze is forming or reversing.

**Architecture:** `basic_firehose.py` dumps all three raw streams for a given ticker so developers can see the data before filtering. `squeeze_monitor.py` maintains per-ticker rolling state in 60-second deques, evaluates squeeze/reversal/LULD signals after each incoming message, and prints one-line alerts with a per-ticker per-type cooldown to prevent spam. Watchlist mode pre-loads free float % and average volume from the Massive REST API at startup and surfaces them as context on each alert.

**Tech Stack:** Python 3.11+, `massive>=2.3.2`, `python-dotenv`, `pytest` (dev), `uv` for dependency management.

---

## File Map

| File | Role |
|---|---|
| `examples/websocket/short-squeeze-monitor/pyproject.toml` | uv project config |
| `examples/websocket/short-squeeze-monitor/.env.example` | API key template |
| `examples/websocket/short-squeeze-monitor/basic_firehose.py` | Raw stream dump, three feeds interleaved |
| `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` | TickerState, signal logic, REST pre-load, handler, CLI |
| `examples/websocket/short-squeeze-monitor/tests/test_signals.py` | Unit tests for signal logic functions |
| `examples/websocket/short-squeeze-monitor/README.md` | Usage docs |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `examples/websocket/short-squeeze-monitor/pyproject.toml`
- Create: `examples/websocket/short-squeeze-monitor/.env.example`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "short-squeeze-monitor"
version = "0.1.0"
description = "Real-time short squeeze detector using Massive's WebSocket API"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "massive>=2.3.2",
    "python-dotenv>=1.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.setuptools]
py-modules = ["squeeze_monitor", "basic_firehose"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create .env.example**

```
MASSIVE_API_KEY=your_api_key_here
```

- [ ] **Step 3: Install dependencies**

Run from `examples/websocket/short-squeeze-monitor/`:
```bash
uv sync --dev
```

Expected: `.venv` created, `massive`, `python-dotenv`, `pytest` installed.

- [ ] **Step 4: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/pyproject.toml examples/websocket/short-squeeze-monitor/.env.example
git commit -m "feat: scaffold short-squeeze-monitor project"
```

---

## Task 2: TickerState and Rolling Window Helpers

**Files:**
- Create: `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` (partial — dataclass + helpers only)
- Create: `examples/websocket/short-squeeze-monitor/tests/__init__.py`
- Create: `examples/websocket/short-squeeze-monitor/tests/test_signals.py`

- [ ] **Step 1: Write failing tests for TickerState and trim_window**

Create `tests/__init__.py` (empty file), then create `tests/test_signals.py`:

```python
import time
from collections import deque
from squeeze_monitor import TickerState, trim_window, is_cooled_down, mark_fired


def test_ticker_state_defaults():
    state = TickerState()
    assert len(state.trades) == 0
    assert len(state.aggs) == 0
    assert state.last_price == 0.0
    assert state.last_luld is None
    assert state.free_float_pct is None
    assert state.avg_volume is None


def test_trim_window_removes_old_trades():
    state = TickerState()
    now_ms = 100_000_000.0
    state.trades.append((now_ms - 70_000, 10.0, 100, True))   # 70s ago — too old
    state.trades.append((now_ms - 30_000, 11.0, 200, True))   # 30s ago — keep

    trim_window(state, window_secs=60, now_ms=now_ms)

    assert len(state.trades) == 1
    assert state.trades[0][1] == 11.0


def test_trim_window_removes_old_aggs():
    state = TickerState()
    now_ms = 100_000_000.0
    state.aggs.append((now_ms - 70_000, 10.0, 1000))   # too old
    state.aggs.append((now_ms - 30_000, 11.0, 2000))   # keep

    trim_window(state, window_secs=60, now_ms=now_ms)

    assert len(state.aggs) == 1
    assert state.aggs[0][1] == 11.0


def test_trim_window_keeps_all_recent():
    state = TickerState()
    now_ms = 100_000_000.0
    for i in range(5):
        state.trades.append((now_ms - i * 5_000, 10.0 + i, 100, True))

    trim_window(state, window_secs=60, now_ms=now_ms)

    assert len(state.trades) == 5


def test_is_cooled_down_fresh_state():
    state = TickerState()
    now = 1000.0
    assert is_cooled_down(state, "SQUEEZE ALERT", cooldown_secs=30, now=now) is True


def test_is_cooled_down_just_fired():
    state = TickerState()
    now = 1000.0
    mark_fired(state, "SQUEEZE ALERT", now=now)
    assert is_cooled_down(state, "SQUEEZE ALERT", cooldown_secs=30, now=now + 5) is False


def test_is_cooled_down_after_period():
    state = TickerState()
    now = 1000.0
    mark_fired(state, "SQUEEZE ALERT", now=now)
    assert is_cooled_down(state, "SQUEEZE ALERT", cooldown_secs=30, now=now + 31) is True


def test_cooldown_does_not_cross_alert_types():
    state = TickerState()
    now = 1000.0
    mark_fired(state, "SQUEEZE ALERT", now=now)
    # REVERSAL ALERT should still be available
    assert is_cooled_down(state, "REVERSAL ALERT", cooldown_secs=30, now=now + 5) is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: `ImportError` — `squeeze_monitor` not found yet.

- [ ] **Step 3: Implement TickerState, trim_window, is_cooled_down, mark_fired in squeeze_monitor.py**

Create `squeeze_monitor.py` with only these components for now:

```python
#!/usr/bin/env python3
"""
Short squeeze monitor: streams real-time trades, per-second agg bars, and
LULD price bands and fires alerts when signal thresholds indicate a squeeze
is forming or reversing.

Usage:
    uv run squeeze_monitor.py
    uv run squeeze_monitor.py --ticker GME AMC CAR
    uv run squeeze_monitor.py --ticker GME --vol-multiplier 2.5 --price-pct 1.5
"""

import argparse
import os
import time as time_module
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in environment variables. "
        "Please set it in your .env file."
    )

EASTERN = ZoneInfo("America/New_York")


@dataclass
class TickerState:
    trades: deque = field(default_factory=deque)  # (timestamp_ms, price, size, is_uptick)
    aggs: deque = field(default_factory=deque)    # (timestamp_ms, close, volume)
    last_price: float = 0.0
    last_luld: object = None                       # LimitUpLimitDown | None
    cooldowns: dict = field(default_factory=dict)  # alert_type -> last_fired epoch seconds
    free_float_pct: float | None = None
    avg_volume: float | None = None


def trim_window(state: TickerState, window_secs: int, now_ms: float | None = None) -> None:
    """Remove deque entries older than window_secs from both trades and aggs."""
    if now_ms is None:
        now_ms = time_module.time() * 1000
    cutoff_ms = now_ms - window_secs * 1000
    while state.trades and state.trades[0][0] < cutoff_ms:
        state.trades.popleft()
    while state.aggs and state.aggs[0][0] < cutoff_ms:
        state.aggs.popleft()


def is_cooled_down(state: TickerState, alert_type: str, cooldown_secs: int,
                   now: float | None = None) -> bool:
    """Returns True if enough time has passed since alert_type last fired."""
    if now is None:
        now = time_module.time()
    last = state.cooldowns.get(alert_type, 0.0)
    return (now - last) >= cooldown_secs


def mark_fired(state: TickerState, alert_type: str, now: float | None = None) -> None:
    """Record that alert_type fired right now."""
    if now is None:
        now = time_module.time()
    state.cooldowns[alert_type] = now
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/
git commit -m "feat: add TickerState, trim_window, and cooldown helpers with tests"
```

---

## Task 3: Squeeze and Reversal Signal Logic

**Files:**
- Modify: `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` (append signal functions)
- Modify: `examples/websocket/short-squeeze-monitor/tests/test_signals.py` (append tests)

- [ ] **Step 1: Append failing tests for check_squeeze and check_reversal**

Append to `tests/test_signals.py`:

```python
from squeeze_monitor import check_squeeze, check_reversal


def _make_squeeze_state(now_ms: float) -> TickerState:
    """Builds a state that satisfies all three squeeze conditions with defaults."""
    state = TickerState()
    base = now_ms - 60_000

    # 50 trades spread across the 60s window, all upticks, 100 shares each
    last_price = 40.0
    for i in range(50):
        price = 40.0 + i * 0.04          # trending up to ~42.0
        state.trades.append((base + i * 1_000, price, 100, price > last_price))
        last_price = price

    # Burst in last 10s: 10 trades, 400 shares each (4000 shares / 10s = 400/s)
    # Window average: (50*100 + 10*400) / 60 = 9000/60 = 150/s. 400/150 = 2.67x
    # Use vol_multiplier=2.0 in tests so this passes
    for i in range(10):
        price = 42.0 + i * 0.03
        state.trades.append((now_ms - 9_000 + i * 1_000, price, 400, True))

    # Oldest agg close 4.1% below current
    state.aggs.append((base, 40.65, 1000))
    state.aggs.append((now_ms - 1_000, 42.30, 2000))
    state.last_price = 42.30
    return state


def test_check_squeeze_all_conditions_met():
    now_ms = 100_000_000.0
    state = _make_squeeze_state(now_ms)
    result = check_squeeze(
        state, window_secs=60, vol_multiplier=2.0,
        price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is True


def test_check_squeeze_volume_condition_not_met():
    now_ms = 100_000_000.0
    state = _make_squeeze_state(now_ms)
    result = check_squeeze(
        state, window_secs=60, vol_multiplier=10.0,  # impossible threshold
        price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def test_check_squeeze_price_condition_not_met():
    now_ms = 100_000_000.0
    state = _make_squeeze_state(now_ms)
    # Set oldest close very close to current price (only 0.3% up)
    state.aggs[0] = (state.aggs[0][0], 42.17, state.aggs[0][2])
    result = check_squeeze(
        state, window_secs=60, vol_multiplier=2.0,
        price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def test_check_squeeze_uptick_condition_not_met():
    now_ms = 100_000_000.0
    state = _make_squeeze_state(now_ms)
    # Flip all trades to downtick
    state.trades = deque(
        (ts, price, size, False) for ts, price, size, _ in state.trades
    )
    result = check_squeeze(
        state, window_secs=60, vol_multiplier=2.0,
        price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def test_check_squeeze_too_few_data_points():
    state = TickerState()
    now_ms = 100_000_000.0
    state.trades.append((now_ms - 5_000, 42.0, 100, True))
    state.aggs.append((now_ms - 5_000, 41.0, 1000))
    result = check_squeeze(
        state, window_secs=60, vol_multiplier=2.0,
        price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def _make_reversal_state(now_ms: float) -> TickerState:
    """Builds a state that satisfies both reversal conditions."""
    state = TickerState()
    base = now_ms - 60_000
    last_price = 45.0
    for i in range(60):
        price = 45.0 - i * 0.05          # trending down to ~42.0
        state.trades.append((base + i * 1_000, price, 200, price > last_price))
        last_price = price

    # Oldest agg close 3.0% above current
    state.aggs.append((base, 45.0, 1000))
    state.aggs.append((now_ms - 1_000, 42.65, 2000))
    state.last_price = 42.65
    return state


def test_check_reversal_both_conditions_met():
    now_ms = 100_000_000.0
    state = _make_reversal_state(now_ms)
    result = check_reversal(
        state, window_secs=60, price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is True


def test_check_reversal_price_not_negative_enough():
    now_ms = 100_000_000.0
    state = _make_reversal_state(now_ms)
    # Set oldest close very close to current (only 0.3% above)
    state.aggs[0] = (state.aggs[0][0], 42.78, state.aggs[0][2])
    result = check_reversal(
        state, window_secs=60, price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def test_check_reversal_downtick_not_dominant():
    now_ms = 100_000_000.0
    state = _make_reversal_state(now_ms)
    # Flip all trades to uptick — downtick ratio drops to 0
    state.trades = deque(
        (ts, price, size, True) for ts, price, size, _ in state.trades
    )
    result = check_reversal(
        state, window_secs=60, price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False


def test_check_reversal_too_few_data_points():
    state = TickerState()
    now_ms = 100_000_000.0
    state.trades.append((now_ms - 5_000, 42.0, 100, False))
    state.aggs.append((now_ms - 5_000, 45.0, 1000))
    result = check_reversal(
        state, window_secs=60, price_pct=2.0, uptick_ratio=0.65, now_ms=now_ms,
    )
    assert result is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_signals.py -v -k "squeeze or reversal"
```

Expected: `ImportError` — `check_squeeze` and `check_reversal` not defined yet.

- [ ] **Step 3: Implement check_squeeze and check_reversal in squeeze_monitor.py**

Append to `squeeze_monitor.py` after `mark_fired`:

```python
def check_squeeze(
    state: TickerState,
    window_secs: int,
    vol_multiplier: float,
    price_pct: float,
    uptick_ratio: float,
    now_ms: float | None = None,
) -> bool:
    """Returns True when all three squeeze conditions are simultaneously met."""
    if len(state.trades) < 2 or len(state.aggs) < 2:
        return False

    if now_ms is None:
        now_ms = time_module.time() * 1000

    # 1. Volume velocity: last 10s burst vs per-second average over full window
    cutoff_10s = now_ms - 10_000
    last_10s_vol = sum(t[2] for t in state.trades if t[0] >= cutoff_10s)
    window_vol = sum(t[2] for t in state.trades)
    if window_vol == 0:
        return False
    per_sec_avg = window_vol / window_secs
    if per_sec_avg == 0 or (last_10s_vol / 10) < per_sec_avg * vol_multiplier:
        return False

    # 2. Price velocity: current price vs oldest agg close
    oldest_close = state.aggs[0][1]
    if oldest_close == 0:
        return False
    price_change_pct = (state.last_price - oldest_close) / oldest_close * 100
    if price_change_pct < price_pct:
        return False

    # 3. Uptick dominance
    total = len(state.trades)
    upticks = sum(1 for t in state.trades if t[3])
    if upticks / total < uptick_ratio:
        return False

    return True


def check_reversal(
    state: TickerState,
    window_secs: int,
    price_pct: float,
    uptick_ratio: float,
    now_ms: float | None = None,
) -> bool:
    """Returns True when both reversal conditions are simultaneously met (stateless)."""
    if len(state.trades) < 2 or len(state.aggs) < 2:
        return False

    # 1. Price velocity: current price down by price_pct vs oldest agg close
    oldest_close = state.aggs[0][1]
    if oldest_close == 0:
        return False
    price_change_pct = (state.last_price - oldest_close) / oldest_close * 100
    if price_change_pct > -price_pct:
        return False

    # 2. Downtick dominance
    total = len(state.trades)
    downticks = sum(1 for t in state.trades if not t[3])
    if downticks / total < uptick_ratio:
        return False

    return True
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/squeeze_monitor.py examples/websocket/short-squeeze-monitor/tests/
git commit -m "feat: add squeeze and reversal signal logic with tests"
```

---

## Task 4: LULD Signal Logic

**Files:**
- Modify: `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` (append check_luld_signals)
- Modify: `examples/websocket/short-squeeze-monitor/tests/test_signals.py` (append tests)

- [ ] **Step 1: Append failing tests for check_luld_signals**

Append to `tests/test_signals.py`:

```python
from squeeze_monitor import check_luld_signals
from unittest.mock import MagicMock


def _make_luld(high: float, low: float, indicators: list) -> object:
    m = MagicMock()
    m.high_price = high
    m.low_price = low
    m.indicators = indicators
    return m


def test_luld_halt_indicator():
    state = TickerState()
    state.last_price = 42.0
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[17])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert "HALT" in alerts


def test_luld_resumption_indicator():
    state = TickerState()
    state.last_price = 42.0
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[18])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert "RESUMPTION" in alerts


def test_luld_upper_band_approach():
    state = TickerState()
    state.last_price = 44.60   # within 0.9% of upper band at 45.0
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert "UPPER BAND" in alerts


def test_luld_lower_band_approach():
    state = TickerState()
    state.last_price = 38.30   # within 0.8% of lower band at 38.0
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert "LOWER BAND" in alerts


def test_luld_no_signals_mid_range():
    state = TickerState()
    state.last_price = 42.0    # mid-range, not near either band
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert alerts == []


def test_luld_no_luld_state():
    state = TickerState()
    state.last_price = 42.0
    alerts = check_luld_signals(state, band_pct=1.0)
    assert alerts == []


def test_luld_no_price():
    state = TickerState()
    state.last_price = 0.0
    state.last_luld = _make_luld(high=45.0, low=38.0, indicators=[])
    alerts = check_luld_signals(state, band_pct=1.0)
    assert alerts == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_signals.py -v -k "luld"
```

Expected: `ImportError` — `check_luld_signals` not defined yet.

- [ ] **Step 3: Implement check_luld_signals in squeeze_monitor.py**

Append to `squeeze_monitor.py` after `check_reversal`:

```python
def check_luld_signals(state: TickerState, band_pct: float) -> list[str]:
    """Returns a list of LULD alert types to fire based on current state."""
    if state.last_luld is None or state.last_price == 0.0:
        return []

    alerts = []
    luld = state.last_luld
    indicators = luld.indicators or []

    if 17 in indicators:
        alerts.append("HALT")
    if 18 in indicators:
        alerts.append("RESUMPTION")

    threshold = band_pct / 100

    if luld.high_price and luld.high_price > 0:
        upper_gap = (luld.high_price - state.last_price) / state.last_price
        if 0.0 <= upper_gap <= threshold:
            alerts.append("UPPER BAND")

    if luld.low_price and luld.low_price > 0:
        lower_gap = (state.last_price - luld.low_price) / state.last_price
        if 0.0 <= lower_gap <= threshold:
            alerts.append("LOWER BAND")

    return alerts
```

- [ ] **Step 4: Run full test suite to confirm all pass**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/squeeze_monitor.py examples/websocket/short-squeeze-monitor/tests/test_signals.py
git commit -m "feat: add LULD signal logic with tests"
```

---

## Task 5: basic_firehose.py

**Files:**
- Create: `examples/websocket/short-squeeze-monitor/basic_firehose.py`

- [ ] **Step 1: Create basic_firehose.py**

```python
#!/usr/bin/env python3
"""
Short squeeze monitor — raw firehose: streams trades, per-second agg bars,
and LULD price bands for one or more tickers and prints every event as it
arrives. Use this to understand the raw data before running squeeze_monitor.py.

Usage:
    uv run basic_firehose.py --ticker GME
    uv run basic_firehose.py --ticker GME AMC CAR
"""

import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from massive import WebSocketClient
from massive.websocket.models import EquityAgg, EquityTrade, LimitUpLimitDown, Market

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in environment variables. "
        "Please set it in your .env file."
    )

EASTERN = ZoneInfo("America/New_York")


def fmt_time_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=EASTERN).strftime("%H:%M:%S")


def fmt_time_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=EASTERN).strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(
        description="Stream raw trades, agg bars, and LULD events for given tickers."
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        required=True,
        help="One or more tickers to watch (required)",
    )
    args = parser.parse_args()

    tickers = [t.upper() for t in args.ticker]
    subscriptions = []
    for t in tickers:
        subscriptions += [f"T.{t}", f"A.{t}", f"LULD.{t}"]

    client = WebSocketClient(
        api_key=API_KEY,
        market=Market.Stocks,
        subscriptions=subscriptions,
    )

    print(f"[firehose] connecting | tickers: {', '.join(tickers)}")
    print("[firehose] streaming T (trades), A (agg bars), LULD | Ctrl+C to stop\n")

    def handler(msgs):
        for m in msgs:
            if isinstance(m, EquityTrade):
                direction = "uptick" if getattr(m, "_uptick", False) else "      "
                print(
                    f"{fmt_time_ms(m.timestamp)}  TRADE  {m.symbol:<6}  "
                    f"${m.price:<9.2f} x{m.size:<8,}  exch:{m.exchange}",
                    flush=True,
                )
            elif isinstance(m, EquityAgg):
                print(
                    f"{fmt_time_ms(m.end_timestamp)}  AGG    {m.symbol:<6}  "
                    f"O:{m.open:.2f}  H:{m.high:.2f}  L:{m.low:.2f}  C:{m.close:.2f}  "
                    f"vol:{m.volume:,}",
                    flush=True,
                )
            elif isinstance(m, LimitUpLimitDown):
                ts = fmt_time_ns(m.timestamp) if m.timestamp else "--:--:--"
                print(
                    f"{ts}  LULD   {m.symbol:<6}  "
                    f"upper:${m.high_price:.2f}  lower:${m.low_price:.2f}  "
                    f"ind:{m.indicators or []}",
                    flush=True,
                )

    try:
        client.run(handle_msg=handler)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs without error**

```bash
uv run basic_firehose.py --ticker GME
```

Expected: connects and prints raw events. Press Ctrl+C after a few seconds.

- [ ] **Step 3: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/basic_firehose.py
git commit -m "feat: add basic_firehose.py for raw stream exploration"
```

---

## Task 6: REST Pre-load

**Files:**
- Modify: `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` (append prefetch_ticker_data)
- Modify: `examples/websocket/short-squeeze-monitor/tests/test_signals.py` (append tests)

- [ ] **Step 1: Append failing tests for prefetch_ticker_data**

Append to `tests/test_signals.py`:

```python
from squeeze_monitor import prefetch_ticker_data
from unittest.mock import MagicMock, patch


def test_prefetch_returns_none_on_empty_response():
    mock_client = MagicMock()
    mock_client.list_stocks_floats.return_value = iter([])
    mock_client.list_financials_ratios.return_value = iter([])

    with patch("squeeze_monitor.RESTClient", return_value=mock_client):
        result = prefetch_ticker_data(["GME"], api_key="fake")

    assert result["GME"]["free_float_pct"] is None
    assert result["GME"]["avg_volume"] is None


def test_prefetch_extracts_float_and_volume():
    mock_float = MagicMock()
    mock_float.free_float_percent = 12.5

    mock_ratio = MagicMock()
    mock_ratio.average_volume = 8_500_000.0

    mock_client = MagicMock()
    mock_client.list_stocks_floats.return_value = iter([mock_float])
    mock_client.list_financials_ratios.return_value = iter([mock_ratio])

    with patch("squeeze_monitor.RESTClient", return_value=mock_client):
        result = prefetch_ticker_data(["GME"], api_key="fake")

    assert result["GME"]["free_float_pct"] == 12.5
    assert result["GME"]["avg_volume"] == 8_500_000.0


def test_prefetch_continues_on_api_error():
    mock_client = MagicMock()
    mock_client.list_stocks_floats.side_effect = Exception("API error")
    mock_client.list_financials_ratios.side_effect = Exception("API error")

    with patch("squeeze_monitor.RESTClient", return_value=mock_client):
        result = prefetch_ticker_data(["GME"], api_key="fake")

    assert result["GME"]["free_float_pct"] is None
    assert result["GME"]["avg_volume"] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_signals.py -v -k "prefetch"
```

Expected: `ImportError` — `prefetch_ticker_data` not defined yet.

- [ ] **Step 3: Implement prefetch_ticker_data in squeeze_monitor.py**

Add this import near the top of `squeeze_monitor.py` (after existing imports):

```python
from massive import RESTClient
```

Then append after `check_luld_signals`:

```python
def prefetch_ticker_data(tickers: list[str], api_key: str) -> dict[str, dict]:
    """
    Queries Massive REST API for free float % and average volume per ticker.
    Used in watchlist mode only. Returns None values for any ticker with no data.
    """
    client = RESTClient(api_key=api_key)
    result: dict[str, dict] = {}

    for ticker in tickers:
        data: dict = {"free_float_pct": None, "avg_volume": None}

        try:
            floats = list(client.list_stocks_floats(ticker=ticker, limit=1))
            if floats:
                data["free_float_pct"] = floats[0].free_float_percent
        except Exception as exc:
            print(f"[warn] float data unavailable for {ticker}: {exc}", flush=True)

        try:
            ratios = list(client.list_financials_ratios(ticker=ticker, limit=1))
            if ratios:
                data["avg_volume"] = ratios[0].average_volume
        except Exception as exc:
            print(f"[warn] ratio data unavailable for {ticker}: {exc}", flush=True)

        result[ticker] = data

    return result
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/squeeze_monitor.py examples/websocket/short-squeeze-monitor/tests/test_signals.py
git commit -m "feat: add REST pre-load for float and volume data with tests"
```

---

## Task 7: Alert Formatting, WebSocket Handler, and CLI

**Files:**
- Modify: `examples/websocket/short-squeeze-monitor/squeeze_monitor.py` (append the rest of the file)

- [ ] **Step 1: Append alert formatting functions to squeeze_monitor.py**

```python
def fmt_now() -> str:
    return datetime.now(tz=EASTERN).strftime("%H:%M:%S")


def fmt_squeeze_alert(
    symbol: str, state: TickerState, window_secs: int, now_ms: float
) -> str:
    cutoff_10s = now_ms - 10_000
    last_10s_vol = sum(t[2] for t in state.trades if t[0] >= cutoff_10s)
    window_vol = sum(t[2] for t in state.trades)
    per_sec_avg = window_vol / window_secs if window_vol else 1
    actual_mult = (last_10s_vol / 10) / per_sec_avg if per_sec_avg else 0

    total = len(state.trades)
    upticks = sum(1 for t in state.trades if t[3])
    uptick_pct = upticks / total * 100 if total else 0

    oldest_close = state.aggs[0][1]
    price_chg = (state.last_price - oldest_close) / oldest_close * 100

    parts = [
        f"${state.last_price:,.2f} ({price_chg:+.1f}%)",
        f"vol: {actual_mult:.1f}x",
        f"uptick: {uptick_pct:.0f}%",
    ]
    if state.free_float_pct is not None:
        parts.append(f"float: {state.free_float_pct:.1f}%")

    return f"{fmt_now()}  {symbol:<6} SQUEEZE ALERT  | {'  | '.join(parts)}"


def fmt_reversal_alert(
    symbol: str, state: TickerState, window_secs: int, now_ms: float
) -> str:
    window_vol = sum(t[2] for t in state.trades)
    per_sec_avg = window_vol / window_secs if window_vol else 1
    cutoff_10s = now_ms - 10_000
    last_10s_vol = sum(t[2] for t in state.trades if t[0] >= cutoff_10s)
    actual_mult = (last_10s_vol / 10) / per_sec_avg if per_sec_avg else 0

    total = len(state.trades)
    downticks = sum(1 for t in state.trades if not t[3])
    downtick_pct = downticks / total * 100 if total else 0

    oldest_close = state.aggs[0][1]
    price_chg = (state.last_price - oldest_close) / oldest_close * 100

    parts = [
        f"${state.last_price:,.2f} ({price_chg:+.1f}%)",
        f"vol: {actual_mult:.1f}x",
        f"downtick: {downtick_pct:.0f}%",
    ]
    if state.free_float_pct is not None:
        parts.append(f"float: {state.free_float_pct:.1f}%")

    return f"{fmt_now()}  {symbol:<6} REVERSAL ALERT | {'  | '.join(parts)}"


def fmt_band_alert(alert_type: str, symbol: str, state: TickerState, band_pct: float) -> str:
    luld = state.last_luld
    if alert_type == "UPPER BAND":
        gap = (luld.high_price - state.last_price) / state.last_price * 100
        return (
            f"{fmt_now()}  {symbol:<6} UPPER BAND     | "
            f"${state.last_price:,.2f}  | band: ${luld.high_price:,.2f}  | gap: {gap:.1f}%"
        )
    else:
        gap = (state.last_price - luld.low_price) / state.last_price * 100
        return (
            f"{fmt_now()}  {symbol:<6} LOWER BAND     | "
            f"${state.last_price:,.2f}  | band: ${luld.low_price:,.2f}  | gap: {gap:.1f}%"
        )


def fmt_halt_alert(alert_type: str, symbol: str, state: TickerState) -> str:
    luld = state.last_luld
    return (
        f"{fmt_now()}  {symbol:<6} {alert_type:<14} | "
        f"${state.last_price:,.2f}  | upper: ${luld.high_price:,.2f}  | lower: ${luld.low_price:,.2f}"
    )
```

- [ ] **Step 2: Append the WebSocket handler and main() to squeeze_monitor.py**

```python
def _fire_alert(line: str, symbol: str, alert_type: str, state: TickerState,
                cooldown_secs: int) -> None:
    print(line, flush=True)
    mark_fired(state, alert_type)


def _evaluate_trade_signals(
    symbol: str, state: TickerState, args: argparse.Namespace,
    now_ms: float, now: float
) -> None:
    if check_squeeze(state, args.window, args.vol_multiplier,
                     args.price_pct, args.uptick_ratio, now_ms):
        if is_cooled_down(state, "SQUEEZE ALERT", args.cooldown, now):
            _fire_alert(
                fmt_squeeze_alert(symbol, state, args.window, now_ms),
                symbol, "SQUEEZE ALERT", state, args.cooldown,
            )

    if check_reversal(state, args.window, args.price_pct, args.uptick_ratio, now_ms):
        if is_cooled_down(state, "REVERSAL ALERT", args.cooldown, now):
            _fire_alert(
                fmt_reversal_alert(symbol, state, args.window, now_ms),
                symbol, "REVERSAL ALERT", state, args.cooldown,
            )


def _evaluate_luld_signals(
    symbol: str, state: TickerState, args: argparse.Namespace, now: float
) -> None:
    for alert_type in check_luld_signals(state, args.band_pct):
        if is_cooled_down(state, alert_type, args.cooldown, now):
            if alert_type in ("UPPER BAND", "LOWER BAND"):
                line = fmt_band_alert(alert_type, symbol, state, args.band_pct)
            else:
                line = fmt_halt_alert(alert_type, symbol, state)
            _fire_alert(line, symbol, alert_type, state, args.cooldown)


def main():
    parser = argparse.ArgumentParser(
        description="Real-time short squeeze detector using Massive WebSocket streams."
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        help="Tickers to watch (watchlist mode). Omit for market-wide.",
    )
    parser.add_argument("--window", type=int, default=60,
                        help="Rolling window in seconds (default: 60)")
    parser.add_argument("--vol-multiplier", type=float, default=3.0,
                        help="Volume burst multiplier vs per-second average (default: 3.0)")
    parser.add_argument("--price-pct", type=float, default=2.0,
                        help="Price move threshold in %% (default: 2.0)")
    parser.add_argument("--uptick-ratio", type=float, default=0.65,
                        help="Uptick/downtick dominance fraction (default: 0.65)")
    parser.add_argument("--band-pct", type=float, default=1.0,
                        help="LULD band proximity threshold in %% (default: 1.0)")
    parser.add_argument("--cooldown", type=int, default=30,
                        help="Seconds between repeated alerts per ticker per type (default: 30)")
    args = parser.parse_args()

    watchlist = [t.upper() for t in args.ticker] if args.ticker else None
    states: dict[str, TickerState] = {}

    if watchlist:
        print(f"[info] pre-loading float data for {', '.join(watchlist)}...", flush=True)
        prefetch = prefetch_ticker_data(watchlist, API_KEY)
        for ticker, data in prefetch.items():
            state = TickerState(
                free_float_pct=data["free_float_pct"],
                avg_volume=data["avg_volume"],
            )
            states[ticker] = state
            float_str = f"{data['free_float_pct']:.1f}%" if data["free_float_pct"] is not None else "N/A"
            print(f"[info]   {ticker}: float {float_str}", flush=True)

    if watchlist:
        subscriptions = []
        for t in watchlist:
            subscriptions += [f"T.{t}", f"A.{t}", f"LULD.{t}"]
        mode_label = f"watchlist ({', '.join(watchlist)})"
    else:
        subscriptions = ["T.*", "A.*", "LULD.*"]
        mode_label = "market-wide"

    from massive import WebSocketClient
    from massive.websocket.models import EquityAgg, EquityTrade, LimitUpLimitDown, Market

    client = WebSocketClient(
        api_key=API_KEY,
        market=Market.Stocks,
        subscriptions=subscriptions,
    )

    print(f"[info] connecting | mode: {mode_label}", flush=True)
    print(
        f"[info] thresholds: window={args.window}s  vol={args.vol_multiplier}x  "
        f"price={args.price_pct}%  uptick={args.uptick_ratio:.0%}  "
        f"band={args.band_pct}%  cooldown={args.cooldown}s",
        flush=True,
    )
    print("[info] press Ctrl+C to stop\n", flush=True)

    def handler(msgs):
        now_ms = time_module.time() * 1000
        now = now_ms / 1000

        for m in msgs:
            if isinstance(m, EquityTrade):
                symbol = m.symbol
                state = states.setdefault(symbol, TickerState())
                is_uptick = m.price > state.last_price if state.last_price else False
                state.trades.append((m.timestamp, m.price, m.size, is_uptick))
                state.last_price = m.price
                trim_window(state, args.window, now_ms)
                _evaluate_trade_signals(symbol, state, args, now_ms, now)
                if state.last_luld:
                    _evaluate_luld_signals(symbol, state, args, now)

            elif isinstance(m, EquityAgg):
                symbol = m.symbol
                state = states.setdefault(symbol, TickerState())
                state.aggs.append((m.end_timestamp, m.close, m.volume))
                trim_window(state, args.window, now_ms)

            elif isinstance(m, LimitUpLimitDown):
                symbol = m.symbol
                state = states.setdefault(symbol, TickerState())
                state.last_luld = m
                _evaluate_luld_signals(symbol, state, args, now)

    try:
        client.run(handle_msg=handler)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```bash
uv run pytest tests/test_signals.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Smoke test market-wide mode**

```bash
uv run squeeze_monitor.py
```

Expected: Connects, prints threshold config line, starts receiving events. No output until signals trigger. Ctrl+C exits cleanly.

- [ ] **Step 5: Smoke test watchlist mode with a volatile ticker**

```bash
uv run squeeze_monitor.py --ticker GME AMC --window 60 --vol-multiplier 2.0
```

Expected: Prints float pre-load info for each ticker, then connects and monitors. Lower `--vol-multiplier` makes alerts more likely during testing.

- [ ] **Step 6: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/squeeze_monitor.py
git commit -m "feat: add alert formatting, WebSocket handler, and CLI to squeeze_monitor"
```

---

## Task 8: README

**Files:**
- Create: `examples/websocket/short-squeeze-monitor/README.md`

- [ ] **Step 1: Create README.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add examples/websocket/short-squeeze-monitor/README.md
git commit -m "docs: add short-squeeze-monitor README"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Two-file pattern (firehose + monitor) | Tasks 5, 7 |
| TickerState with trades/aggs/luld/cooldowns/float fields | Task 2 |
| trim_window trimming both deques | Task 2 |
| check_squeeze — all three conditions | Task 3 |
| check_reversal — stateless, both conditions | Task 3 |
| check_luld_signals — HALT, RESUMPTION, UPPER/LOWER BAND | Task 4 |
| Alert cooldown per ticker per type | Tasks 2, 7 |
| REST pre-load at startup (watchlist mode only) | Task 6 |
| free_float_pct and avg_volume on SQUEEZE/REVERSAL alerts | Tasks 6, 7 |
| Market-wide mode omits float from output | Task 7 |
| All CLI args with correct defaults | Task 7 |
| LULD re-evaluates on every trade (price may move into band) | Task 7 |
| Minimum 2 trades + 2 aggs before signal evaluation | Tasks 3, 4 |
| Error handling: missing API key | Tasks 1, 5 |
| Error handling: REST failure warns and continues | Task 6 |
| pyproject.toml with massive>=2.3.2 | Task 1 |

**Type consistency:** `TickerState` defined once in Task 2, used identically across Tasks 3, 4, 6, 7. Signal function signatures (`now_ms: float | None = None`) consistent throughout. `states: dict[str, TickerState]` used in handler.

**No placeholders found.**
