#!/usr/bin/env python3
from datetime import datetime
from zoneinfo import ZoneInfo
from massive import WebSocketClient
from massive.websocket.models import EquityTrade, Market

MASSIVE_API_KEY = "your_massive_api_key"

# TRF ID to venue name mapping
TRF_NAMES = {
    201: "FINRA/NYSE TRF",
    202: "FINRA/NASDAQ TRF Carteret",
    203: "FINRA/NASDAQ TRF Chicago"
}

def et(ms):
    """Convert millisecond timestamp to Eastern Time string."""
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("America/New_York")).strftime("%H:%M:%S")


def main():
    c = WebSocketClient(api_key=MASSIVE_API_KEY, market=Market.Stocks, subscriptions=["T.*"])
    
    print(f"\n{'Time':<12} {'Symbol':<8} {'Price':>12} {'Size':>10} {'Notional':>16} {'TRF':<28}")
    print("-" * 90)

    def handler(msgs):
        for m in msgs:
            # Filter for dark pool trades: exchange 4 (TRF) with a valid trf_id
            if not isinstance(m, EquityTrade) or m.exchange != 4 or m.trf_id is None:
                continue
            
            trf = TRF_NAMES.get(m.trf_id, f"TRF {m.trf_id}")
            print(f"{et(m.timestamp):<12} {m.symbol:<8} ${m.price:>10,.2f} {m.size:>10,} ${m.price * m.size:>14,.2f} {trf:<28}")

    c.run(handle_msg=handler)

if __name__ == "__main__":
    main()
