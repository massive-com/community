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
