from massive import WebSocketClient
from massive.websocket.models import Feed, Market, WebSocketMessage
from typing import List
import os
from dotenv import load_dotenv
import time

# ==================== CONFIG ====================
load_dotenv()
API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError("MASSIVE_API_KEY not found in .env file. Please add it and try again.")

# Mag7 (all NASDAQ-listed → halts/resumptions possible)
MAG7 = {"AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"}

client = WebSocketClient(
    api_key=API_KEY,
    feed=Feed.RealTime,
    market=Market.Stocks
)

# Subscribe to ALL LULD events (required for market-wide halts)
client.subscribe("LULD.*")

# Simple human-readable timestamp (nanoseconds → seconds)
def format_ts(ts: int) -> str:
    seconds = ts / 1_000_000_000
    return time.strftime("%H:%M:%S", time.localtime(seconds))

# ==================== HANDLER ====================
def handle_msg(msgs: List[WebSocketMessage]):
    for m in msgs:
        if m.event_type != "LULD":
            continue

        symbol = m.symbol
        indicators = m.indicators or []
        high = getattr(m, "high_price", None)
        low = getattr(m, "low_price", None)
        ts_str = format_ts(m.timestamp)

        # Halt / resumption detection
        alert = ""
        if 17 in indicators:
            alert = " 🚨 HALT / SUSPENDED PAUSE (Indicator 17)"
        elif 18 in indicators:
            alert = " ✅ RESUMPTION / REOPENING (Indicator 18)"

        # Show Mag7 price bands OR any halt/resumption
        if symbol in MAG7 or alert:
            print(f"{ts_str} | {symbol:6} | "
                  f"Upper: {high:>8.2f} | Lower: {low:>8.2f} | "
                  f"Ind: {indicators}{alert}")

# ==================== RUN ====================
print("🚀 LULD Smart Monitor Started")
print("→ Monitoring Mag7 price bands + all market halts/resumptions")
print("→ Press Ctrl+C to stop\n")

client.run(handle_msg)
