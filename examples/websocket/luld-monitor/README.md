# LULD Real-Time Monitor

<div align="center">
  <img src="../../../images/logo_new.png" alt="Project Logo" width="100%"/>
</div>

This repository contains two example tools to help you quickly get hands-on with Massive’s real-time Limit Up Limit Down (LULD) WebSocket feed for U.S. stocks. Full details on the LULD WebSocket feed are available in the [official LULD documentation](https://massive.com/docs/websocket/stocks/luld).

It includes:
- A basic firehose script that streams every LULD price-band update across the market
- A smart monitor script that focuses on price bands for the Magnificent 7 while surfacing all trading halts and resumptions (Indicators 17 & 18)

## Features

- Real-time streaming of LULD events via Massive’s WebSocket API
- Firehose example (watch high-volume feed)
- Monitoring example (Mag7 price bands + market-wide halt/resumption alerts)

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Massive API key (Stocks Advanced or the LULD Expansion pln are required for real-time LULD data)

## Quickstart

1. **Clone the repository**:
   ```bash
   git clone https://github.com/massive-com/community.git
   cd community/examples/websocket/luld-monitor
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

   **Basic Firehose** (raw high-volume stream):
   ```bash
   uv run basic_firehose.py
   ```

   **Smart Monitor** (recommended — Mag7 bands + halt alerts):
   ```bash
   uv run luld_monitor.py
   ```

Press `Ctrl+C` to stop either script.

## Example Outputs

### 1. Basic Firehose (`basic_firehose.py`)
This shows the raw, high-volume LULD stream (hundreds of messages per minute during trading hours):

```
LimitUpLimitDown(event_type='LULD', symbol='IPFXU', high_price=11.12, low_price=9.1, indicators=[16], tape=3, timestamp=1776175650376809635, sequence_number=2491344)
LimitUpLimitDown(event_type='LULD', symbol='ZMUN', high_price=55.19, low_price=45.15, indicators=[16], tape=3, timestamp=1776175650376767810, sequence_number=1932379)
LimitUpLimitDown(event_type='LULD', symbol='ZOOZ', high_price=0.46, low_price=0.16, indicators=[16], tape=3, timestamp=1776175650376768003, sequence_number=1932382)
LimitUpLimitDown(event_type='LULD', symbol='ZSPC', high_price=0.12, low_price=0.02, indicators=[16], tape=3, timestamp=1776175650376768117, sequence_number=1932384)
```

### 2. Smart Monitor (`luld_monitor.py`)
Clean filtered output focused on the Magnificent 7 and real halts/resumptions:

```
07:01:00 | NVDA   | Upper:   200.95 | Lower:   181.81 | Ind: [16]
07:01:00 | MSFT   | Upper:   411.48 | Lower:   372.29 | Ind: [16]
07:01:20 | AFJK   | Upper:     0.00 | Lower:     0.00 | Ind: [17] 🚨 HALT / SUSPENDED PAUSE (Indicator 17)
07:06:20 | AFJK   | Upper:    52.34 | Lower:    42.82 | Ind: [18] ✅ RESUMPTION / REOPENING (Indicator 18)
```

## How it works

### LULD Event Structure

Each LULD message includes the ticker, dynamic upper/lower price bands, indicators, tape, timestamp (nanoseconds), and sequence number. For a complete glossary of all conditions and indicators (including LULD-specific ones), see the [Massive Conditions & Indicators Glossary](https://massive.com/glossary/conditions-indicators).

Important Indicators:
| Indicator | Description                  | Notes |
|-----------|------------------------------|-------|
| 15 / 16   | Price band update            | Most frequent |
| **17**    | **Trading halt / pause**     | NASDAQ-listed only |
| **18**    | **Resumption / reopening**   | NASDAQ-listed only |

The basic_firehose.py script subscribes to `LULD.*` and prints everything. The luld_monitor.py script adds filtering and nice formatting so you can focus on the Magnificent 7 price bands and instantly spot any halts across the market.

## Troubleshooting

- No data showing: Ensure you have Stocks Advanced (or the expansion) and the market is open (9:30 AM – 4:00 PM ET). LULD is intraday only.
- Too much output: Use the smart monitor instead of the firehose.
- API errors: Verify your `MASSIVE_API_KEY` in `.env` and run `uv sync --upgrade`.

## Next Steps

- Log events to CSV or a database
- Build a simple dashboard to visualize price bands

## Disclaimer

Warning: The examples, demos, and outputs produced are provided "AS IS", may not always be accurate and may contain material inaccuracies. You should not rely on any outputs or actions without independently confirming their accuracy, and any outputs should not be treated as financial or legal advice. You remain responsible for verifying the accuracy, suitability, and legality of any output before relying on it.

## License

This project is licensed under the [MIT License](../../../LICENSE).
