#!/usr/bin/env python3
"""
NYSE order imbalance monitor: streams real-time NOI events and displays
imbalance direction, magnitude, paired shares, and clearing prices
with convergence tracking.

Usage:
    uv run noi_monitor.py
    uv run noi_monitor.py --ticker JPM BAC GS
    uv run noi_monitor.py --min-imbalance 5000
    uv run noi_monitor.py --ticker SPY --min-imbalance 1000
"""

import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from massive import WebSocketClient
from massive.websocket.models import Feed, Market, Imbalance

# ==================== CONFIG ====================
load_dotenv()
API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in environment variables. "
        "Please set it in your .env file."
    )

EASTERN = ZoneInfo("America/New_York")

AUCTION_LABELS = {
    "M": "Open",
    "C": "Close",
    "H": "Halt",
}

# Track previous imbalance per ticker for convergence detection
prev_imbalance: dict[str, int] = {}


def fmt_time(ts_ns: int) -> str:
    """Convert a nanosecond epoch timestamp to an Eastern Time string."""
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=EASTERN).strftime(
        "%H:%M:%S"
    )


def fmt_auction_time(at: int) -> str:
    """Format auction time (HHMM integer) as HH:MM."""
    hours = at // 100
    minutes = at % 100
    return f"{hours:02d}:{minutes:02d}"


def direction(qty: int) -> str:
    if qty > 0:
        return "BUY"
    elif qty < 0:
        return "SELL"
    return "FLAT"


def convergence(symbol: str, current: int) -> str:
    """Compare current absolute imbalance to previous update for this ticker."""
    previous = prev_imbalance.get(symbol)
    prev_imbalance[symbol] = current

    if previous is None:
        return ""

    curr_abs = abs(current)
    prev_abs = abs(previous)

    if curr_abs < prev_abs:
        return "shrinking"
    elif curr_abs > prev_abs:
        return "growing"
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Stream NYSE order imbalance (NOI) data with smart filtering and convergence tracking."
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        help="One or more tickers to watch (default: all NYSE-listed)",
    )
    parser.add_argument(
        "--min-imbalance",
        type=int,
        default=0,
        help="Minimum absolute imbalance quantity to display (default: 0, show all)",
    )
    args = parser.parse_args()

    # Build subscriptions
    if args.ticker:
        subscriptions = [f"NOI.{t.upper()}" for t in args.ticker]
        watched = {t.upper() for t in args.ticker}
    else:
        subscriptions = ["NOI.*"]
        watched = None

    client = WebSocketClient(
        api_key=API_KEY,
        feed=Feed.RealTime,
        market=Market.Stocks,
        subscriptions=subscriptions,
    )

    tickers_label = (
        ", ".join(t.upper() for t in args.ticker) if args.ticker else "all NYSE tickers"
    )

    print(f"NOI Monitor | Watching: {tickers_label}")
    if args.min_imbalance > 0:
        print(f"Filtering: imbalance >= {args.min_imbalance:,} shares")
    print("Press Ctrl+C to stop\n")

    header = (
        f"{'Time':>8}  {'Symbol':6}  {'Auction':7}  {'Dir':4}  "
        f"{'Imbalance':>10}  {'Paired':>10}  {'Price':>10}  Trend"
    )
    print(header)
    print("-" * len(header))

    def handler(msgs):
        for m in msgs:
            if not isinstance(m, Imbalance):
                continue

            symbol = m.symbol or ""

            if watched and symbol not in watched:
                continue

            imb = m.imbalance_quantity or 0

            if abs(imb) < args.min_imbalance:
                continue

            paired = m.paired_quantity or 0
            price = m.book_clearing_price or 0.0
            auction = AUCTION_LABELS.get(m.auction_type or "", m.auction_type or "")
            ts = fmt_time(m.time_stamp) if m.time_stamp else "--:--:--"
            trend = convergence(symbol, imb)

            print(
                f"{ts:>8}  {symbol:6}  {auction:7}  {direction(imb):4}  "
                f"{imb:>10,}  {paired:>10,}  ${price:>9.2f}  {trend}",
                flush=True,
            )

    try:
        client.run(handle_msg=handler)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
