#!/usr/bin/env python3
"""
Fractional Share Precision Demo
================================
Shows how fractional share precision was previously lost in trade reporting.
Fetches trades across Massive APIs (WebSocket, REST, Flat Files), identifies
trades with fractional volume, and quantifies the information that was hidden.

Usage:
    uv run python main.py websocket [TICKERS...] [-d SECONDS]
    uv run python main.py rest [TICKERS...] [--date YYYY-MM-DD] [--save]
    uv run python main.py flatfiles [--date DATE] [--type TYPE] [--save]
"""
import argparse
import csv
import gzip
import io
import json
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

W = 62
EASTERN = ZoneInfo("America/New_York")

S3_ENDPOINT = "https://files.massive.com"
S3_BUCKET = "flatfiles"


# ── Shared utilities ────────────────────────────────────────────


def get_api_key():
    """Return the Massive API key or raise."""
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        raise ValueError(
            "MASSIVE_API_KEY not found in environment variables. "
            "Please set it in your .env file."
        )
    return key


def get_s3_client():
    """Return a boto3 S3 client for Massive flat files."""
    import boto3
    from botocore.config import Config

    access = os.getenv("MASSIVE_S3_ACCESS_KEY")
    secret = os.getenv("MASSIVE_S3_SECRET_KEY")
    if not access or not secret:
        raise ValueError(
            "S3 credentials not found. Add to your .env file:\n"
            "  MASSIVE_S3_ACCESS_KEY=your-access-key\n"
            "  MASSIVE_S3_SECRET_KEY=your-secret-key\n\n"
            "Get these from your Massive dashboard."
        )
    session = boto3.Session(
        aws_access_key_id=access,
        aws_secret_access_key=secret,
    )
    return session.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        config=Config(
            signature_version="s3v4",
            connect_timeout=30,
            read_timeout=120,
            retries={"max_attempts": 3},
        ),
    )


def fmt_time(ts_ns):
    """Format a nanosecond timestamp to HH:MM:SS.mmm ET."""
    if ts_ns is None:
        return "N/A"
    dt = datetime.fromtimestamp(ts_ns / 1e9, tz=EASTERN)
    return dt.strftime("%H:%M:%S.%f")[:-3]


def banner(title):
    """Print a ═══ banner line with a title."""
    print(f"{'=' * W}")
    print(f"  {title}")
    print(f"{'=' * W}")


def section(title):
    """Print a ─── section divider with a title."""
    print(f"\n  {'─' * (W - 2)}")
    print(f"  {title}")
    print(f"  {'─' * (W - 2)}")


def most_recent_business_day():
    """Return the most recent completed business day (weekday)."""
    d = date.today()
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def old_reported_size(actual_size):
    """Compute what exchanges used to report before fractional precision.
    Sub-1-share trades (e.g. 0.038) were rounded UP to 1.
    Larger trades (e.g. 52.12) had the fractional portion DROPPED (truncated).
    """
    if actual_size < 1.0:
        return 1
    return int(actual_size)


def rounding_explainer():
    """Print the standard explanation of old rounding behavior."""
    print()
    print("  Before fractional precision, exchanges rounded trade sizes:")
    print("    Sub-1-share (e.g. 0.038) \u2192 reported as 1  (inflated)")
    print("    Larger frac (e.g. 52.12) \u2192 reported as 52 (deflated)")


def print_impact(sub_one, larger_frac, net_misreported, dollar_impact):
    """Print the standard impact summary block."""
    print("\n  Impact:")
    print(f"    Sub-1-share trades:   {sub_one:,} trades reported as 1 share"
          f" (volume inflated)")
    print(f"    Larger fractional:    {larger_frac:,} trades with fraction dropped"
          f" (volume deflated)")
    print(f"    Net volume misreported: {net_misreported:+,.4f} shares")
    print(f"    Dollar impact:          ${dollar_impact:+,.2f}")


# ── WebSocket demo ──────────────────────────────────────────────


def run_websocket(tickers, duration=30):
    """Stream real-time trades, identify fractional precision, save results."""
    from massive import WebSocketClient
    from massive.websocket.models import Market

    api_key = get_api_key()

    trade_count = 0
    agg_count = 0
    fractional_trades = []
    agg_samples = []
    sub_one_count = 0
    larger_frac_count = 0
    actual_frac_volume = 0.0
    reported_frac_volume = 0.0
    dollar_impact = 0.0
    start_time = time.monotonic()

    def handle_messages(raw_data):
        nonlocal trade_count, agg_count
        nonlocal sub_one_count, larger_frac_count
        nonlocal actual_frac_volume, reported_frac_volume, dollar_impact

        msgs = json.loads(raw_data)
        for msg in msgs:
            ev = msg.get("ev")

            if ev == "T":
                trade_count += 1
                ds = msg.get("ds")
                if isinstance(ds, str):
                    ds = ds.strip()
                    msg["ds"] = ds
                if ds is not None:
                    try:
                        actual = float(ds)
                        if actual != int(actual):
                            reported = old_reported_size(actual)
                            p = msg.get("p")
                            price = float(p) if p is not None else 0.0
                            hidden = actual - reported

                            fractional_trades.append({
                                "time": msg.get("t"),
                                "ticker": msg.get("sym", "???"),
                                "price": price,
                                "actual_size": actual,
                                "reported_size": reported,
                            })

                            actual_frac_volume += actual
                            reported_frac_volume += reported
                            dollar_impact += hidden * price

                            if actual < 1.0:
                                sub_one_count += 1
                            else:
                                larger_frac_count += 1
                    except (ValueError, TypeError):
                        pass

            elif ev in ("A", "AM"):
                agg_count += 1
                sym = msg.get("sym", "???")
                for i, existing in enumerate(agg_samples):
                    if existing.get("sym") == sym:
                        agg_samples[i] = msg
                        break
                else:
                    agg_samples.append(msg)

            elif ev == "status":
                continue

        elapsed = time.monotonic() - start_time
        remaining = max(0, int(duration - elapsed))
        sys.stdout.write(
            f"\r  Collecting... {trade_count} trades "
            f"({len(fractional_trades)} fractional), "
            f"{agg_count} aggs  [{remaining}s left]   "
        )
        sys.stdout.flush()

    def save_results():
        """Save collected data to CSV files in data/ directory."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = []

        if fractional_trades:
            path = os.path.join(data_dir, f"ws_trades_{timestamp}.csv")
            with open(path, "w", newline="") as f:
                fieldnames = ["time", "ticker", "price",
                              "reported_size", "actual_size",
                              "hidden_shares", "hidden_value"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for t in fractional_trades:
                    hidden = t["actual_size"] - t["reported_size"]
                    writer.writerow({
                        "time": fmt_time(t["time"]),
                        "ticker": t["ticker"],
                        "price": f"{t['price']:.4f}",
                        "reported_size": t["reported_size"],
                        "actual_size": f"{t['actual_size']:.6f}",
                        "hidden_shares": f"{hidden:.6f}",
                        "hidden_value": f"{hidden * t['price']:.4f}",
                    })
            saved.append((path, f"{len(fractional_trades)} fractional trades"))

        if agg_samples:
            path = os.path.join(data_dir, f"ws_aggs_{timestamp}.csv")
            with open(path, "w", newline="") as f:
                fieldnames = ["ticker", "volume_int", "volume_decimal",
                              "acc_volume_int", "acc_volume_decimal"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for a in agg_samples:
                    writer.writerow({
                        "ticker": a.get("sym", ""),
                        "volume_int": a.get("v", ""),
                        "volume_decimal": a.get("dv", ""),
                        "acc_volume_int": a.get("av", ""),
                        "acc_volume_decimal": a.get("dav", ""),
                    })
            saved.append((path, f"{len(agg_samples)} ticker snapshots"))

        return saved

    subs = []
    for t in tickers:
        subs.append(f"T.{t}")
        subs.append(f"A.{t}")

    banner("Fractional Share Precision \u2014 WebSocket Trade Analysis")
    print(f"  Tickers:  {', '.join(tickers)}")
    print(f"  Duration: {duration}s")
    print(f"  Feeds:    Trades (T) + Aggregates (A)")
    rounding_explainer()
    print(f"\n{'=' * W}")
    print()

    # Auto-stop after duration by sending SIGINT from a timer thread.
    # This reuses the existing KeyboardInterrupt handler, and the user
    # can still Ctrl+C early if they want.
    def _send_interrupt():
        import signal
        os.kill(os.getpid(), signal.SIGINT)

    timer = threading.Timer(duration, _send_interrupt)
    timer.daemon = True
    timer.start()

    client = WebSocketClient(
        api_key=api_key,
        market=Market.Stocks,
        raw=True,
        subscriptions=subs,
    )

    try:
        client.run(handle_messages)
    except KeyboardInterrupt:
        timer.cancel()

    # ── Results ──
    print("\n")
    banner("Fractional Share Precision \u2014 Results")
    print(f"  Trades received:     {trade_count:,}")
    print(f"  Aggregates received: {agg_count:,}")

    if fractional_trades:
        frac_count = len(fractional_trades)
        pct = frac_count / trade_count * 100
        print(f"  Fractional trades:   {frac_count:,} ({pct:.1f}% of total)")

    if fractional_trades:
        print(f"\n  {'Time':<13} {'Sym':<6} {'Price':>10}"
              f"  {'Old Rptd':>9}  {'Actual Size':>12}")
        print(f"  {'─' * 13} {'─' * 6} {'─' * 10}"
              f"  {'─' * 9}  {'─' * 12}")
        for t in fractional_trades[:10]:
            ts = fmt_time(t["time"])
            sym = t["ticker"]
            price = f"${t['price']:,.2f}" if t["price"] else "N/A"
            reported = str(t["reported_size"])
            actual = f"{t['actual_size']:.6f}"
            print(f"  {ts:<13} {sym:<6} {price:>10}"
                  f"  {reported:>9}  {actual:>12}")
        if len(fractional_trades) > 10:
            print(f"  ... and {len(fractional_trades) - 10:,} more (see CSV)")

        net_misreported = actual_frac_volume - reported_frac_volume
        print_impact(sub_one_count, larger_frac_count,
                     net_misreported, dollar_impact)

    saved = save_results()
    if saved:
        section("Saved files")
        for path, desc in saved:
            print(f"  {path}")
            print(f"    {desc}")
    else:
        print("\n  No data to save (no fractional trades or aggs captured).")

    print(f"\n{'=' * W}")


# ── REST demo ───────────────────────────────────────────────────


def fetch_and_analyze(client, ticker, trade_date):
    """Fetch all trades for a ticker on a date, return analysis dict."""
    print(f"  Fetching trades for {ticker} on {trade_date} ...")

    fractional_trades = []
    total_count = 0
    sub_one_count = 0
    larger_frac_count = 0
    actual_frac_volume = 0.0
    reported_frac_volume = 0.0
    dollar_impact = 0.0

    for t in client.list_trades(ticker, timestamp=str(trade_date), limit=50000):
        total_count += 1
        ds = t.decimal_size
        if ds is None:
            continue

        try:
            actual = float(ds)
        except (ValueError, TypeError):
            continue

        if actual != int(actual):
            reported = old_reported_size(actual)
            price = float(t.price) if t.price is not None else 0.0
            hidden = actual - reported
            hidden_value = hidden * price

            fractional_trades.append({
                "time": t.sip_timestamp,
                "price": price,
                "actual_size": actual,
                "reported_size": reported,
                "hidden_shares": hidden,
                "hidden_value": hidden_value,
            })

            actual_frac_volume += actual
            reported_frac_volume += reported
            dollar_impact += hidden_value

            if actual < 1.0:
                sub_one_count += 1
            else:
                larger_frac_count += 1

        if total_count % 10000 == 0:
            sys.stdout.write(f"\r  Fetched {total_count:,} trades so far...")
            sys.stdout.flush()

    if total_count >= 10000:
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()

    print(f"  Fetched {total_count:,} trades total.")

    return {
        "ticker": ticker,
        "total_count": total_count,
        "fractional_trades": fractional_trades,
        "fractional_count": len(fractional_trades),
        "sub_one_count": sub_one_count,
        "larger_frac_count": larger_frac_count,
        "actual_frac_volume": actual_frac_volume,
        "reported_frac_volume": reported_frac_volume,
        "dollar_impact": dollar_impact,
    }


def print_ticker_results(result):
    """Print analysis results for a single ticker."""
    ticker = result["ticker"]
    total = result["total_count"]
    frac_count = result["fractional_count"]
    frac_trades = result["fractional_trades"]

    section(ticker)

    print(f"  Total trades:      {total:,}")

    if total > 0:
        pct = frac_count / total * 100
        print(f"  Fractional trades: {frac_count:,} ({pct:.1f}% of total)")
    else:
        print(f"  Fractional trades: {frac_count:,}")
        return

    if not frac_trades:
        print("\n  No fractional trades found.")
        return

    # Example trades table
    print(f"\n  {'Time':<14} {'Price':>10} {'Old Rptd':>9} {'Actual Size':>13}")
    print(f"  {'─' * 14} {'─' * 10} {'─' * 9} {'─' * 13}")

    for ft in frac_trades[:10]:
        ts = fmt_time(ft["time"])
        price = f"${ft['price']:,.2f}" if ft["price"] else "N/A"
        reported = str(ft["reported_size"])
        actual = f"{ft['actual_size']:.6f}"
        print(f"  {ts:<14} {price:>10} {reported:>9} {actual:>13}")

    if len(frac_trades) > 10:
        print(f"  ... and {len(frac_trades) - 10:,} more")

    # Impact summary
    net_misreported = result["actual_frac_volume"] - result["reported_frac_volume"]
    print_impact(
        result["sub_one_count"],
        result["larger_frac_count"],
        net_misreported,
        result["dollar_impact"],
    )


def save_fractional_csv(result, trade_date):
    """Save fractional trades to CSV in data/ directory."""
    ticker = result["ticker"]
    frac_trades = result["fractional_trades"]
    if not frac_trades:
        return None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    filename = f"fractional_trades_{ticker}_{trade_date}.csv"
    path = os.path.join(data_dir, filename)

    with open(path, "w", newline="") as f:
        fieldnames = [
            "time", "ticker", "price", "reported_size",
            "actual_size", "hidden_shares", "hidden_value",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ft in frac_trades:
            writer.writerow({
                "time": fmt_time(ft["time"]),
                "ticker": ticker,
                "price": f"{ft['price']:.4f}",
                "reported_size": ft["reported_size"],
                "actual_size": f"{ft['actual_size']:.6f}",
                "hidden_shares": f"{ft['hidden_shares']:.6f}",
                "hidden_value": f"{ft['hidden_value']:.4f}",
            })

    return path


def run_rest(tickers, trade_date, save=False):
    """Fetch all trades for each ticker, analyze fractional precision."""
    from massive import RESTClient

    api_key = get_api_key()
    client = RESTClient(api_key=api_key, connect_timeout=30, read_timeout=60)

    banner("Fractional Share Precision \u2014 REST Trade Analysis")
    print(f"  Tickers: {', '.join(tickers)}")
    print(f"  Date:    {trade_date}")
    rounding_explainer()
    print(f"{'=' * W}")

    results = []
    for ticker in tickers:
        result = fetch_and_analyze(client, ticker, trade_date)
        results.append(result)
        print_ticker_results(result)

    # Grand total (if multiple tickers)
    if len(results) > 1:
        section("GRAND TOTAL")
        total_trades = sum(r["total_count"] for r in results)
        total_frac = sum(r["fractional_count"] for r in results)
        total_sub_one = sum(r["sub_one_count"] for r in results)
        total_larger = sum(r["larger_frac_count"] for r in results)
        total_actual = sum(r["actual_frac_volume"] for r in results)
        total_reported = sum(r["reported_frac_volume"] for r in results)
        total_dollar = sum(r["dollar_impact"] for r in results)
        net = total_actual - total_reported

        pct = (total_frac / total_trades * 100) if total_trades else 0
        print(f"  Trades analyzed:        {total_trades:,}")
        print(f"  Fractional trades:      {total_frac:,} ({pct:.1f}%)")
        print_impact(total_sub_one, total_larger, net, total_dollar)

    # CSV export
    if save:
        section("Saved files")
        for result in results:
            path = save_fractional_csv(result, trade_date)
            if path:
                print(f"  {path}")
                print(f"    {result['fractional_count']:,} fractional trades")
            else:
                print(f"  {result['ticker']}: no fractional trades to save")

    print(f"\n{'=' * W}")


# ── Flat files demo ─────────────────────────────────────────────


def download_and_read(s3, key, max_rows=50):
    """Download a gzipped CSV from S3 and return rows as dicts.

    Only fetches the first 512KB to avoid long downloads on slow connections.
    """
    print(f"  Downloading: {key} (first 512KB)...")
    try:
        resp = s3.get_object(
            Bucket=S3_BUCKET,
            Key=key,
            Range="bytes=0-524287",
        )
        data = resp["Body"].read()
    except s3.exceptions.NoSuchKey:
        raise FileNotFoundError(f"File not found: {key}")

    buf = io.BytesIO(data)
    rows = []
    try:
        with gzip.open(buf, "rt", errors="ignore") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= max_rows - 1:
                    break
    except EOFError:
        # Partial gzip is expected since we only fetched a range
        pass
    return rows


def save_rows_to_csv(rows, path):
    """Write a list of dicts to a CSV file."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  Saved {len(rows)} rows to {path}")


def _file_not_found_hint(file_date):
    """Return a hint string explaining why a flat file might be missing."""
    days_ago = (date.today() - file_date).days
    if days_ago <= 2:
        return ("  This file may not be published yet. Flat files are typically"
                " available\n  with a one-day delay."
                " Try an earlier date with --date YYYY-MM-DD.")
    return "  Try a different date with --date YYYY-MM-DD."


def demo_trades(s3, file_date, save=False):
    """Show fractional precision impact in the trades flat file."""
    year = file_date.strftime("%Y")
    month = file_date.strftime("%m")
    key = (f"us_stocks_sip/trades_v1/"
           f"{year}/{month}/{file_date.isoformat()}.csv.gz")

    section(f"TRADES flat file ({file_date})")

    try:
        rows = download_and_read(s3, key)
    except FileNotFoundError:
        print(f"  File not found: {key}")
        print(_file_not_found_hint(file_date))
        return
    except Exception as e:
        print(f"  Error: {e}")
        print("  Try a different date with --date YYYY-MM-DD")
        return

    if not rows:
        print("  No data in file.")
        return

    size_col = None
    for col in rows[0].keys():
        if col.lower() == "size":
            size_col = col
            break

    if not size_col:
        print("  'size' column not found in file.")
        return

    # Analyze all rows
    fractional_rows = []
    sub_one_count = 0
    larger_frac_count = 0
    actual_frac_volume = 0.0
    reported_frac_volume = 0.0
    dollar_impact = 0.0

    for row in rows:
        size_val = row.get(size_col, "")
        ticker = row.get("ticker", row.get("sym", "???"))
        price_str = row.get("price", row.get("p", "0"))

        try:
            actual = float(size_val)
        except (ValueError, TypeError):
            continue

        if actual != int(actual):
            reported = old_reported_size(actual)
            try:
                price = float(price_str)
            except (ValueError, TypeError):
                price = 0.0
            hidden = actual - reported

            fractional_rows.append({
                "ticker": ticker,
                "price": price,
                "actual_size": actual,
                "reported_size": reported,
            })

            actual_frac_volume += actual
            reported_frac_volume += reported
            dollar_impact += hidden * price

            if actual < 1.0:
                sub_one_count += 1
            else:
                larger_frac_count += 1

    total = len(rows)
    frac_count = len(fractional_rows)
    print(f"  Rows sampled:      {total}")

    if total > 0 and frac_count > 0:
        pct = frac_count / total * 100
        print(f"  Fractional trades: {frac_count} ({pct:.1f}% of sample)")
    else:
        print(f"  Fractional trades: {frac_count}")

    if fractional_rows:
        print(f"\n  {'Ticker':<8} {'Price':>10} {'Old Rptd':>9} {'Actual Size':>13}")
        print(f"  {'─' * 8} {'─' * 10} {'─' * 9} {'─' * 13}")

        for ft in fractional_rows[:10]:
            ticker = ft["ticker"]
            price = f"${ft['price']:,.2f}" if ft["price"] else "N/A"
            reported = str(ft["reported_size"])
            actual = f"{ft['actual_size']:.6f}"
            print(f"  {ticker:<8} {price:>10} {reported:>9} {actual:>13}")

        if len(fractional_rows) > 10:
            print(f"  ... and {len(fractional_rows) - 10} more")

        net_misreported = actual_frac_volume - reported_frac_volume
        print_impact(sub_one_count, larger_frac_count,
                     net_misreported, dollar_impact)

    if save:
        save_rows_to_csv(rows, f"trades_{file_date.isoformat()}.csv")


def demo_aggs(s3, file_date, save=False):
    """Show fractional precision impact in the aggregates flat file."""
    year = file_date.strftime("%Y")
    month = file_date.strftime("%m")
    key = (f"us_stocks_sip/minute_aggs_v1/"
           f"{year}/{month}/{file_date.isoformat()}.csv.gz")

    section(f"AGGREGATES flat file ({file_date})")

    try:
        rows = download_and_read(s3, key)
    except FileNotFoundError:
        print(f"  File not found: {key}")
        print(_file_not_found_hint(file_date))
        return
    except Exception as e:
        print(f"  Error: {e}")
        print("  Try a different date with --date YYYY-MM-DD")
        return

    if not rows:
        print("  No data in file.")
        return

    vol_col = None
    for col in rows[0].keys():
        if col.lower() == "volume":
            vol_col = col
            break

    if not vol_col:
        print("  'volume' column not found in file.")
        return

    # Analyze all rows
    fractional_rows = []
    total_decimal = 0.0
    total_int = 0
    total_dollar_decimal = 0.0
    total_dollar_int = 0.0

    for row in rows:
        vol_val = row.get(vol_col, "")
        ticker = row.get("ticker", row.get("sym", "???"))
        close_str = row.get("close", row.get("c", "0"))

        try:
            vol_f = float(vol_val)
        except (ValueError, TypeError):
            continue

        total_decimal += vol_f
        total_int += int(vol_f)

        try:
            close_f = float(close_str)
        except (ValueError, TypeError):
            close_f = 0.0

        total_dollar_decimal += close_f * vol_f
        total_dollar_int += close_f * int(vol_f)

        if vol_f != int(vol_f):
            fractional_rows.append({
                "ticker": ticker,
                "close": close_f,
                "volume": vol_f,
            })

    total = len(rows)
    frac_count = len(fractional_rows)
    print(f"  Rows sampled:           {total}")

    if total > 0 and frac_count > 0:
        pct = frac_count / total * 100
        print(f"  Fractional volume bars: {frac_count} ({pct:.1f}% of sample)")
    else:
        print(f"  Fractional volume bars: {frac_count}")

    if fractional_rows:
        print(f"\n  {'Ticker':<8} {'Close':>10}  {'Volume':>16}")
        print(f"  {'─' * 8} {'─' * 10}  {'─' * 16}")

        for ft in fractional_rows[:10]:
            ticker = ft["ticker"]
            close = f"${ft['close']:,.2f}" if ft["close"] else "N/A"
            vol = f"{ft['volume']:.6f}"
            print(f"  {ticker:<8} {close:>10}  {vol:>16}")

        if len(fractional_rows) > 10:
            print(f"  ... and {len(fractional_rows) - 10} more")

    vol_hidden = total_decimal - total_int
    if total_decimal > 0:
        print(f"\n  Impact across {total} rows:")
        print(f"    Volume: {total_decimal:,.2f} actual,"
              f" {total_int:,} old-reported"
              f"  ({vol_hidden:+,.2f} hidden)")
        if total_dollar_decimal > 0:
            dollar_hidden = total_dollar_decimal - total_dollar_int
            print(f"    Dollars: ${total_dollar_decimal:,.2f} actual,"
                  f" ${total_dollar_int:,.2f} old-reported"
                  f"  (${dollar_hidden:+,.2f} hidden)")

    if save:
        save_rows_to_csv(rows, f"aggs_{file_date.isoformat()}.csv")


def run_flatfiles(file_date, file_type, save=False):
    """Download partial flat files from S3 and analyze fractional precision."""
    banner("Fractional Share Precision \u2014 Flat Files Analysis")
    print(f"  Date:     {file_date.isoformat()}")
    print(f"  Endpoint: {S3_ENDPOINT}")
    print(f"  Bucket:   {S3_BUCKET}")
    rounding_explainer()
    print(f"\n{'=' * W}")

    s3 = get_s3_client()

    if file_type in ("trades", "both"):
        demo_trades(s3, file_date, save=save)
    if file_type in ("aggs", "both"):
        demo_aggs(s3, file_date, save=save)

    print(f"\n{'=' * W}")


# ── CLI entry point ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Massive \u2014 Fractional Share Precision Demos",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # websocket
    ws_parser = subparsers.add_parser(
        "websocket",
        aliases=["ws"],
        help="Stream real-time trades and analyze fractional precision",
    )
    ws_parser.add_argument(
        "tickers",
        nargs="*",
        default=["AAPL"],
        help="Stock tickers to subscribe to (default: AAPL)",
    )
    ws_parser.add_argument(
        "-d", "--duration",
        type=int,
        default=30,
        help="Seconds to collect data before stopping (default: 30)",
    )

    # rest
    rest_parser = subparsers.add_parser(
        "rest",
        help="Fetch all trades for a date and analyze fractional precision",
    )
    rest_parser.add_argument(
        "tickers",
        nargs="*",
        default=["AAPL"],
        help="Stock tickers to analyze (default: AAPL)",
    )
    rest_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Trading date to query (YYYY-MM-DD). Default: most recent business day.",
    )
    rest_parser.add_argument(
        "--save",
        action="store_true",
        help="Export fractional trades to CSV in data/",
    )

    # flatfiles
    ff_parser = subparsers.add_parser(
        "flatfiles",
        aliases=["flat", "ff"],
        help="Download flat files from S3 and analyze fractional precision",
    )
    ff_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to fetch (YYYY-MM-DD). Default: 2 business days ago.",
    )
    ff_parser.add_argument(
        "--type",
        choices=["trades", "aggs", "both"],
        default="both",
        help="Which flat file to analyze (default: both)",
    )
    ff_parser.add_argument(
        "--save",
        action="store_true",
        help="Save downloaded rows to CSV in the current directory",
    )

    args = parser.parse_args()

    if args.command in ("websocket", "ws"):
        tickers = [t.upper() for t in args.tickers]
        run_websocket(tickers, duration=args.duration)

    elif args.command == "rest":
        tickers = [t.upper() for t in args.tickers]
        if args.date:
            try:
                trade_date = date.fromisoformat(args.date)
            except ValueError:
                parser.error(f"Invalid date format: '{args.date}'"
                             " (expected YYYY-MM-DD)")
        else:
            trade_date = most_recent_business_day()
        run_rest(tickers, trade_date, save=args.save)

    elif args.command in ("flatfiles", "flat", "ff"):
        if args.date:
            try:
                file_date = date.fromisoformat(args.date)
            except ValueError:
                parser.error(f"Invalid date format: '{args.date}'"
                             " (expected YYYY-MM-DD)")
        else:
            # Default to 2 business days ago. Flat files are typically
            # published with a one-day delay, so yesterday's file may
            # not exist yet.
            d = date.today()
            skipped = 0
            while skipped < 2:
                d -= timedelta(days=1)
                if d.weekday() < 5:
                    skipped += 1
            file_date = d
        run_flatfiles(file_date, args.type, save=args.save)


if __name__ == "__main__":
    main()
