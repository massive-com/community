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
