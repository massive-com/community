from massive import WebSocketClient
from massive.websocket.models import WebSocketMessage, Feed, Market
from typing import List
import os
from dotenv import load_dotenv

# ==================== CONFIG ====================
load_dotenv()
API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError("MASSIVE_API_KEY not found in .env file. Please add it and try again.")

client = WebSocketClient(
    api_key=API_KEY,
    feed=Feed.RealTime,
    market=Market.Stocks
)

# Subscribe to all LULD events (firehose mode)
client.subscribe("LULD.*")

def handle_msg(msgs: List[WebSocketMessage]):
    for m in msgs:
        print(m)

# ==================== RUN ====================
print("🚀 LULD Basic Firehose Started")
print("→ Streaming ALL LULD price-band updates in real time")
print("→ Press Ctrl+C to stop\n")

client.run(handle_msg)
