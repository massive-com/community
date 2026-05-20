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
