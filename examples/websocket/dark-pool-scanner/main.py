#!/usr/bin/env python3
"""
Dark pool scanner: streams real-time US stock trades and filters for
off-exchange (TRF) activity above a notional threshold.

Usage:
    uv run main.py
    uv run main.py --min-notional 50000
    uv run main.py --ticker NVDA TSLA
    uv run main.py --ticker AAPL --min-notional 200000
"""

import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from massive import WebSocketClient
from massive.websocket.models import EquityTrade, Market

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in environment variables. "
        "Please set it in your .env file."
    )

EASTERN = ZoneInfo("America/New_York")

TRF_NAMES = {
    201: "FINRA/NYSE TRF",
    202: "FINRA/NASDAQ TRF Carteret",
    203: "FINRA/NASDAQ TRF Chicago",
}


def fmt_time(ms: int) -> str:
    """Convert a millisecond epoch timestamp to an Eastern Time string."""
    return datetime.fromtimestamp(ms / 1000, tz=EASTERN).strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )


def show_trade(trade: EquityTrade) -> None:
    """Pretty-print a single dark pool trade."""
    notional = trade.price * trade.size
    venue = TRF_NAMES.get(trade.trf_id, f"TRF {trade.trf_id}")
    conditions = getattr(trade, "conditions", None)

    pl = lambda label, value, w=12: f"{(label + ':'):<{w}} {value}"

    print(
        "\n".join(
            [
                "",
                pl("Symbol", trade.symbol),
                pl("Price", f"${trade.price:,.2f}"),
                pl("Size", f"{trade.size:,} shares"),
                pl("Notional", f"${notional:,.2f}"),
                pl("Venue", venue),
                pl("Timestamp", fmt_time(trade.timestamp)),
                pl("Conditions", conditions if conditions else "N/A"),
                "",
                "------------------------",
            ]
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Stream dark pool (TRF) trades filtered by notional value."
    )
    parser.add_argument(
        "--min-notional",
        type=float,
        default=100_000,
        help="Minimum notional value in USD (default: 100,000)",
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        help="One or more tickers to watch (default: all)",
    )
    args = parser.parse_args()

    if args.ticker:
        subscriptions = [f"T.{t.upper()}" for t in args.ticker]
    else:
        subscriptions = ["T.*"]

    client = WebSocketClient(
        api_key=API_KEY, market=Market.Stocks, subscriptions=subscriptions
    )

    tickers_label = ", ".join(t.upper() for t in args.ticker) if args.ticker else "all tickers"
    print(
        f"[info] connecting to stock trade stream ({tickers_label})"
        f" | filter: TRF trades >= ${args.min_notional:,.0f} notional",
        flush=True,
    )

    def handler(msgs):
        for trade in msgs:
            if not isinstance(trade, EquityTrade):
                continue
            if trade.exchange != 4 or trade.trf_id is None:
                continue
            if trade.price * trade.size < args.min_notional:
                continue
            show_trade(trade)

    try:
        client.run(handle_msg=handler)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == "__main__":
    main()