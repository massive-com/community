from collections import deque
from squeeze_monitor import TickerState, trim_window, is_cooled_down, mark_fired
from squeeze_monitor import check_squeeze, check_reversal


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
