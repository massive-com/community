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
from massive import RESTClient

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
