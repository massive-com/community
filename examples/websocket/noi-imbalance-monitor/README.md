# NYSE Order Imbalance Monitor

<div align="center">
  <img src="../../../images/logo_new.png" alt="Project Logo" width="100%"/>
</div>

Two example tools for streaming NYSE Net Order Imbalance (NOI) data in real time via Massive's WebSocket API. NOI events give you visibility into buy and sell pressure ahead of NYSE auctions, including imbalance quantity, paired shares, and the indicative clearing price. Full details on the NOI WebSocket feed are available in the [official imbalances documentation](https://massive.com/docs/websocket/stocks/imbalances).

This includes:
- A basic firehose script that streams every NOI event across all NYSE-listed tickers
- A smart monitor that formats output into a readable table with direction labels, convergence tracking, and optional ticker/size filters

## Background

Most stock transactions happen via continuous trading, where orders are matched individually throughout the day. NYSE auctions work differently. At the open, close, and following trading halts, NYSE batches all eligible orders and determines a single clearing price that maximizes shares traded. Every participant in that auction transacts at the same price.

In the minutes before each auction, buy and sell orders accumulate at different prices and sizes. The gap between buy-side and sell-side volume is the order imbalance. It signals which direction the auction price may need to move to attract enough liquidity to clear.

Each NOI event exposes:

| Field | Description |
|---|---|
| Imbalance quantity | Net difference between buy and sell orders (positive = buy-side, negative = sell-side) |
| Paired shares | Shares already matched and ready to clear |
| Indicative clearing price | The projected auction price given current order flow |
| Auction type | Open, close, or halt |

**Timing.** NYSE begins disseminating open imbalance data around 9:00 AM ET, roughly 30 minutes before the 9:30 AM auction. Close imbalance data starts around 3:50 PM ET. These two windows contain the bulk of actionable NOI volume. Outside of them, most events are from trading halt auctions.

**Coverage.** NOI data covers NYSE-listed tickers only.

## Features

- Real-time streaming of NOI events via Massive's WebSocket API
- Firehose mode for raw event inspection
- Smart monitor with formatted table output, direction (BUY/SELL) labels, and convergence tracking
- Filter by ticker, minimum imbalance size, or both

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Massive API key with NYSE order imbalance data access

## Quickstart

1. **Clone the repository**:
   ```bash
   git clone https://github.com/massive-com/community.git
   cd community/examples/websocket/noi-imbalance-monitor
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Set up your API key**:
   ```bash
   cp .env.example .env
   # Edit .env and add your MASSIVE_API_KEY
   ```

4. **Run the examples**:

   **Basic Firehose** (raw stream, all tickers):
   ```bash
   uv run basic_firehose.py
   ```

   **Smart Monitor** (recommended, formatted table with filtering):
   ```bash
   uv run noi_monitor.py
   ```

   Watch specific tickers:
   ```bash
   uv run noi_monitor.py --ticker JPM BAC GS
   ```

   Filter for large imbalances only:
   ```bash
   uv run noi_monitor.py --min-imbalance 5000
   ```

Press `Ctrl+C` to stop either script.

## Example outputs

### 1. Basic Firehose (`basic_firehose.py`)

Raw NOI stream showing every event as it arrives:

```
Imbalance(event_type='NOI', symbol='JPM', time_stamp=1776175650376809635, auction_time=930, auction_type='M', imbalance_quantity=5200, paired_quantity=42800, book_clearing_price=142.5, exchange_id=10, symbol_sequence=1284)
Imbalance(event_type='NOI', symbol='BAC', time_stamp=1776175650376812400, auction_time=930, auction_type='M', imbalance_quantity=-3100, paired_quantity=28400, book_clearing_price=38.75, exchange_id=10, symbol_sequence=1285)
```

### 2. Smart Monitor (`noi_monitor.py`)

Formatted table with direction, convergence tracking, and filters applied:

```
NOI Monitor | Watching: JPM, BAC, GS
Press Ctrl+C to stop

    Time  Symbol  Auction  Dir    Imbalance      Paired       Price  Trend
------------------------------------------------------------------------
09:15:22  JPM     Open     BUY        5,200      42,800   $  142.50
09:15:22  BAC     Open     SELL      -3,100      28,400   $   38.75
09:15:22  GS      Open     BUY       12,400      85,200   $  412.30
09:15:45  JPM     Open     BUY        3,800      44,200   $  142.35  shrinking
09:15:45  BAC     Open     SELL      -4,500      27,000   $   38.60  growing
09:15:45  GS      Open     BUY        8,100      89,500   $  412.15  shrinking
```

The "Trend" column tracks convergence. A shrinking imbalance means liquidity is arriving on the contra side, suggesting the final auction print will be close to the current indicative price. A growing imbalance means more pressure is building, and the clearing price may still have room to move.

## How it works

### NOI event structure

Each NOI message includes the ticker, auction type, imbalance quantity (signed), paired shares, indicative clearing price, exchange ID, and timestamp in nanoseconds.

| Field | SDK Attribute | Description |
|---|---|---|
| Event type | `event_type` | Always `NOI` |
| Symbol | `symbol` | NYSE-listed ticker |
| Timestamp | `time_stamp` | Nanosecond Unix epoch |
| Auction time | `auction_time` | Scheduled auction time (HHMM format, Eastern) |
| Auction type | `auction_type` | `M` = market open, `C` = close, `H` = halt |
| Imbalance qty | `imbalance_quantity` | Net imbalance in shares (positive = buy-side, negative = sell-side) |
| Paired qty | `paired_quantity` | Shares already matched |
| Clearing price | `book_clearing_price` | Indicative auction clearing price |
| Exchange | `exchange_id` | Exchange identifier |

### Interpreting imbalances

**Direction.** A positive imbalance quantity means more buy orders than sell orders in the auction queue. The indicative clearing price will typically rise to attract sellers. A negative quantity is the inverse: excess sell orders push the price lower.

**Magnitude.** The raw share count matters most in context. A 5,000-share buy imbalance on a thinly traded name carries more weight than the same figure on a high-volume stock. A useful approach is to normalize imbalance quantity against the stock's average daily volume.

**Convergence.** The smart monitor tracks whether each ticker's absolute imbalance is growing or shrinking between updates. A shrinking imbalance as the auction approaches means liquidity is arriving on the contra side, and the final print is likely near the current indicative price. A large imbalance that is not shrinking suggests the clearing price may still move.

## Troubleshooting

- **No data showing:** NOI events are concentrated around the open (~9:00-9:30 AM ET) and close (~3:50-4:00 PM ET). Outside these windows, events are sparse and limited to halt auctions.
- **Coverage:** Only NYSE-listed tickers produce NOI events. NASDAQ-listed names will not appear.
- **Too much output:** Use `--ticker` to watch specific names, or `--min-imbalance` to filter small imbalances.
- **API errors:** Verify your `MASSIVE_API_KEY` in `.env` and run `uv sync --upgrade`.

## Next steps

- Normalize imbalance against average daily volume for relative sizing
- Log events to CSV for backtesting auction strategies
- Combine with trade data to track how imbalances predict actual auction prints

## Disclaimer

Warning: The examples, demos, and outputs produced are provided "AS IS", may not always be accurate and may contain material inaccuracies. You should not rely on any outputs or actions without independently confirming their accuracy, and any outputs should not be treated as financial or legal advice. You remain responsible for verifying the accuracy, suitability, and legality of any output before relying on it.

## License

This project is licensed under the [MIT License](../../../LICENSE).
