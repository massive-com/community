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
