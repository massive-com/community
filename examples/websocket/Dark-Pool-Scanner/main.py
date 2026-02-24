#!/usr/bin/env python3
"""Dark Pool Scanner - Filters for TRF (off-exchange) trades"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from massive import WebSocketClient
from massive.websocket.models import EquityTrade, Market

MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "YOUR_API_KEY_HERE")
MIN_NOTIONAL = 100_000

TRF_NAMES = {
    201: "FINRA/NYSE TRF",
    202: "FINRA/NASDAQ TRF Carteret",
    203: "FINRA/NASDAQ TRF Chicago"
}

def et(ms):
    """Convert millisecond timestamp to Eastern Time string."""
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")

def show_trade(m):
    """Pretty print a dark pool trade."""
    notional = m.price * m.size
    trf = TRF_NAMES.get(m.trf_id, f"TRF {m.trf_id}")
    conditions = getattr(m, "conditions", None)
    
    print(f"""
Symbol:      {m.symbol}
Price:       ${m.price:,.2f}
Size:        {m.size:,} shares
Notional:    ${notional:,.2f}
Venue:       {trf}
Timestamp:   {et(m.timestamp)}
Conditions:  {conditions if conditions else "N/A"}

------------------------""")

def main():
    c = WebSocketClient(api_key=MASSIVE_API_KEY, market=Market.Stocks, subscriptions=["T.*"])

    def handler(msgs):
        for m in msgs:
            if not isinstance(m, EquityTrade) or m.exchange != 4 or m.trf_id is None:
                continue
            if m.price * m.size < MIN_NOTIONAL:
                continue
            show_trade(m)

    c.run(handle_msg=handler)

if __name__ == "__main__":
    main()