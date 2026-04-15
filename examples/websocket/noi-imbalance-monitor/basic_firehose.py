from massive import WebSocketClient
from massive.websocket.models import Feed, Market
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

# Subscribe to all NOI events (firehose mode)
client.subscribe("NOI.*")

def handle_msg(msgs):
    for m in msgs:
        print(m)

# ==================== RUN ====================
print("NOI Basic Firehose Started")
print("Streaming ALL NYSE order imbalance updates in real time")
print("Press Ctrl+C to stop\n")

try:
    client.run(handle_msg)
except KeyboardInterrupt:
    pass
