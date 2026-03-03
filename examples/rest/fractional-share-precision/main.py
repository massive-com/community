#!/usr/bin/env python3
"""
Fractional Share Precision Demo
================================
Demonstrates the new decimal precision fields across Massive APIs:

  WebSocket:   ds, dv, dav   — real-time streaming
  REST:        decimal_size, dv, dav, decimal_volume — point-in-time
  Flat Files:  size, volume   — now decimal in CSVs from S3

Usage:
    uv run python main.py websocket [TICKERS...] [-d SECONDS]   (saves to data/)
    uv run python main.py rest [TICKERS...]
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


# ── WebSocket demo ──────────────────────────────────────────────


def run_websocket(tickers, duration=30):
    """Stream real-time trades and aggregates, save results when done."""
    from massive import WebSocketClient
    from massive.websocket.models import Market

    api_key = get_api_key()

    trade_count = 0
    agg_count = 0
    fractional_trades = []
    agg_samples = []
    total_volume_ds = 0.0
    total_volume_s = 0
    total_dollar_ds = 0.0
    total_dollar_s = 0.0
    start_time = time.monotonic()

    def handle_messages(raw_data):
        nonlocal trade_count, agg_count, total_volume_ds, total_volume_s, total_dollar_ds, total_dollar_s

        msgs = json.loads(raw_data)
        for msg in msgs:
            ev = msg.get("ev")

            if ev == "T":
                trade_count += 1
                ds = msg.get("ds")
                s = msg.get("s")
                if isinstance(ds, str):
                    ds = ds.strip()
                    msg["ds"] = ds
                if ds is not None and s is not None:
                    try:
                        ds_f = float(ds)
                        s_i = int(s)
                        total_volume_ds += ds_f
                        total_volume_s += s_i
                        p = msg.get("p")
                        if p is not None:
                            total_dollar_ds += p * ds_f
                            total_dollar_s += p * s_i
                    except (ValueError, TypeError):
                        pass
                    if float(ds) != float(s):
                        fractional_trades.append(msg)

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
                              "size_int", "size_decimal"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for t in fractional_trades:
                    writer.writerow({
                        "time": fmt_time(t.get("t")),
                        "ticker": t.get("sym", ""),
                        "price": t.get("p", ""),
                        "size_int": t.get("s", ""),
                        "size_decimal": t.get("ds", ""),
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

    banner("Massive WebSocket — Fractional Share Precision Demo")
    print(f"  Tickers:  {', '.join(tickers)}")
    print(f"  Duration: {duration}s")
    print("  Feeds:    Trades (T) + Aggregates (A)")
    print()
    print("  New decimal fields vs old integer fields:")
    print("    Trades: ds  vs s   (exact quantity)")
    print("    Aggs:   dv  vs v   (exact volume)")
    print("            dav vs av  (exact daily accumulated volume)")
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

    # ── Summary + save ──
    print("\n")
    banner("Fractional Share Precision — Results")
    print(f"  Trades received:     {trade_count}")
    print(f"  Aggregates received: {agg_count}")

    if fractional_trades and trade_count > 0:
        pct = len(fractional_trades) / trade_count * 100
        print(f"  Fractional trades:   {len(fractional_trades)}"
              f" ({pct:.1f}% of total)")
    print()

    if fractional_trades:
        print(f"  {'Time':<13} {'Sym':<6} {'Price':>10}"
              f"  {'s':>5}  {'ds':>12}")
        print(f"  {'─' * 13} {'─' * 6} {'─' * 10}"
              f"  {'─' * 5}  {'─' * 12}")
        for t in fractional_trades[:10]:
            ts = fmt_time(t.get("t"))
            sym = t.get("sym", "???")
            p = t.get("p")
            price = f"${p:,.2f}" if p is not None else "N/A"
            s = str(t.get("s", ""))
            ds = t.get("ds", "N/A")
            print(f"  {ts:<13} {sym:<6} {price:>10}"
                  f"  {s:>5}  {ds:>12}")
        if len(fractional_trades) > 10:
            print(f"  ... and {len(fractional_trades) - 10} more (see CSV)")

    # ── Impact analysis ──
    if total_volume_ds > 0:
        section("Impact analysis")
        vol_hidden = total_volume_ds - total_volume_s
        pct_hidden = (vol_hidden / total_volume_ds) * 100

        print(f"  Shares:  {total_volume_ds:,.2f} actual,"
              f" {total_volume_s:,} reported"
              f"  ({vol_hidden:,.2f} hidden, {pct_hidden:.2f}%)")
        if total_dollar_ds > 0:
            dollar_hidden = total_dollar_ds - total_dollar_s
            print(f"  Dollars: ${total_dollar_ds:,.2f} actual,"
                  f" ${total_dollar_s:,.2f} reported"
                  f"  (${dollar_hidden:,.2f} hidden)")

    saved = save_results()
    if saved:
        section("Saved files")
        for path, desc in saved:
            print(f"  {path}")
            print(f"    {desc}")
    else:
        print("  No data to save (no fractional trades or aggs captured).")

    print(f"\n{'=' * W}")


# ── REST demo ───────────────────────────────────────────────────


def run_rest(tickers):
    """Fetch last trade, snapshot v2, and snapshot v3 for each ticker."""
    from massive import RESTClient

    api_key = get_api_key()

    client = RESTClient(
        api_key=api_key,
        connect_timeout=30,
        read_timeout=60,
    )

    banner("Massive REST API — Fractional Share Precision Demo")

    for ticker in tickers:

        # ── Last Trade ──
        section(f"LAST TRADE: {ticker}")

        print(f"  Fetching /v2/last/trade/{ticker} ...")
        trade = client.get_last_trade(ticker)

        price = f"${trade.price:,.4f}" if trade.price is not None else "N/A"
        size = trade.size if trade.size is not None else "N/A"
        decimal_size = (
            trade.fractional_shares
            if trade.fractional_shares is not None
            else "N/A"
        )

        print(f"\n  {'Field':<22} {'Value':>20}")
        print(f"  {'─' * 22} {'─' * 20}")
        print(f"  {'price':<22} {price:>20}")
        print(f"  {'size (int)':<22} {str(size):>20}")
        print(f"  {'decimal_size':<22} {decimal_size:>20}")

        if decimal_size != "N/A" and size is not None:
            try:
                ds_f = float(decimal_size)
                s_f = float(size)
                if ds_f != s_f:
                    hidden_qty = ds_f - s_f
                    price_f = trade.price if trade.price is not None else 0
                    hidden_dollar = abs(hidden_qty) * price_f
                    print(f"\n  Precision gap:")
                    print(f"    Actual quantity:    {decimal_size}")
                    print(f"    Reported as (int):  {size}")
                    print(f"    Hidden quantity:    {hidden_qty:+.6f}")
                    print(f"    Dollar impact:     ${hidden_dollar:,.2f}")
            except ValueError:
                pass

        # ── Snapshot v2 ──
        section(f"SNAPSHOT v2: {ticker}")

        print(f"  Fetching /v2/snapshot/.../tickers/{ticker} ...")
        resp = client.get_snapshot_ticker("stocks", ticker, raw=True)
        data = json.loads(resp.data.decode("utf-8"))
        snap = data.get("ticker", {})

        day = snap.get("day", {})
        minute = snap.get("min", {})
        prev = snap.get("prevDay", {})

        def show_vol(label, vol_section, ref_price=None):
            v = vol_section.get("v")
            dv = vol_section.get("dv")
            av = vol_section.get("av")
            dav = vol_section.get("dav")

            print(f"\n  {label}:")
            print(f"  {'Field':<22} {'Value':>24}")
            print(f"  {'─' * 22} {'─' * 24}")
            v_str = f"{v:,.0f}" if v is not None else "N/A"
            print(f"  {'v (int volume)':<22} {v_str:>24}")
            dv_str = str(dv) if dv is not None else "N/A"
            print(f"  {'dv (decimal vol.)':<22} {dv_str:>24}")
            if av is not None or dav is not None:
                av_str = f"{av:,.0f}" if av is not None else "N/A"
                print(f"  {'av (int acc. vol.)':<22} {av_str:>24}")
                dav_str = str(dav) if dav is not None else "N/A"
                print(f"  {'dav (decimal acc.)':<22} {dav_str:>24}")

            # Volume hidden
            if dv is not None and v is not None:
                try:
                    dv_f = float(dv)
                    gap = dv_f - float(v)
                    pct = (gap / dv_f * 100) if dv_f else 0
                    dollar_str = ""
                    if ref_price is not None and ref_price > 0:
                        dollar_str = f" (~${gap * ref_price:,.2f} at ${ref_price:,.2f}/share)"
                    print(f"  {'Volume hidden':<22} {gap:.6f} shares{dollar_str}")
                except (ValueError, TypeError):
                    pass

        # Use VWAP from each bar as reference price, fall back to trade price
        trade_price = trade.price if trade.price is not None else None
        day_ref = day.get("vw") or trade_price
        min_ref = minute.get("vw") or trade_price
        prev_ref = prev.get("vw") or trade_price

        show_vol("Day bar", day, ref_price=day_ref)
        show_vol("Minute bar", minute, ref_price=min_ref)
        show_vol("Previous day", prev, ref_price=prev_ref)

        # ── Snapshot v3 ──
        section(f"SNAPSHOT v3: {ticker}")

        print(f"  Fetching /v3/snapshot?ticker.any_of={ticker} ...")
        v3_resp = client.list_universal_snapshots(
            ticker_any_of=[ticker], raw=True
        )
        v3_data = json.loads(v3_resp.data.decode("utf-8"))
        v3_results = v3_data.get("results", [])

        if v3_results:
            v3_snap = v3_results[0]
            session = v3_snap.get("session", {})
            v = session.get("volume")
            dv = session.get("decimal_volume")

            print(f"\n  {'Field':<26} {'Value':>24}")
            print(f"  {'─' * 26} {'─' * 24}")
            v_str = f"{v:,.0f}" if v is not None else "N/A"
            print(f"  {'volume (number)':<26} {v_str:>24}")
            dv_str = str(dv) if dv is not None else "N/A"
            print(f"  {'decimal_volume (string)':<26} {dv_str:>24}")

            if dv is not None and v is not None:
                try:
                    dv_f = float(dv)
                    gap = dv_f - float(v)
                    pct = (gap / dv_f * 100) if dv_f else 0
                    close_price = session.get("close")
                    dollar_str = ""
                    if close_price is not None and close_price > 0:
                        dollar_str = f" (~${gap * close_price:,.2f} at ${close_price:,.2f}/share)"
                    print(f"\n  Volume hidden: {gap:.6f} shares{dollar_str}")
                except (ValueError, TypeError):
                    print(f"\n  volume truncates to {v:,.0f}"
                          f", decimal_volume shows exact: {dv}")
        else:
            print(f"  No v3 snapshot data for {ticker}.")

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
    """Show that the trades flat file size field now has decimal values."""
    year = file_date.strftime("%Y")
    month = file_date.strftime("%m")
    key = (f"us_stocks_sip/trades_v1/"
           f"{year}/{month}/{file_date.isoformat()}.csv.gz")

    section("TRADES flat file: size field is now decimal")

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

    print(f"  File columns: {list(rows[0].keys())}")
    print("\n  Showing rows where size has decimal precision:\n")

    size_col = None
    for col in rows[0].keys():
        if col.lower() == "size":
            size_col = col
            break

    if not size_col:
        print("  'size' column not found in file.")
        return

    print(f"  {'ticker':<8} {'price':>10}  {'size':>14}")
    print(f"  {'─' * 8} {'─' * 10}  {'─' * 14}")

    shown = 0
    fractional = 0
    total_decimal = 0.0
    total_int = 0
    total_dollar_decimal = 0.0
    total_dollar_int = 0.0
    for row in rows:
        size_val = row.get(size_col, "")
        ticker = row.get("ticker", row.get("sym", "???"))
        price = row.get("price", row.get("p", "N/A"))

        try:
            size_f = float(size_val)
            total_decimal += size_f
            total_int += int(size_f)
            if size_f != int(size_f):
                fractional += 1
            try:
                price_f = float(price)
                total_dollar_decimal += price_f * size_f
                total_dollar_int += price_f * int(size_f)
            except (ValueError, TypeError):
                pass
        except (ValueError, TypeError):
            pass

        if shown < 20:
            try:
                p_str = f"${float(price):,.2f}"
            except (ValueError, TypeError):
                p_str = str(price)
            print(f"  {ticker:<8} {p_str:>10}  {size_val:>14}")
            shown += 1

    if fractional:
        print(f"\n  {fractional} of {len(rows)} rows have"
              " fractional size values.")

    vol_hidden = total_decimal - total_int
    pct = (vol_hidden / total_decimal * 100) if total_decimal else 0
    print(f"\n  Impact across {len(rows)} rows:")
    print(f"    Volume: {total_decimal:,.2f} shares actual,"
          f" {total_int:,} reported"
          f"  ({vol_hidden:,.2f} hidden, {pct:.2f}%)")
    if total_dollar_decimal > 0:
        dollar_hidden = total_dollar_decimal - total_dollar_int
        print(f"    Dollars: ${total_dollar_decimal:,.2f} actual,"
              f" ${total_dollar_int:,.2f} reported"
              f"  (${dollar_hidden:,.2f} hidden)")

    if save:
        save_rows_to_csv(rows, f"trades_{file_date.isoformat()}.csv")


def demo_aggs(s3, file_date, save=False):
    """Show that the aggregates flat file volume field has decimal values."""
    year = file_date.strftime("%Y")
    month = file_date.strftime("%m")
    key = (f"us_stocks_sip/minute_aggs_v1/"
           f"{year}/{month}/{file_date.isoformat()}.csv.gz")

    section("AGGREGATES flat file: volume field is now decimal")

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

    print(f"  File columns: {list(rows[0].keys())}")

    vol_col = None
    for col in rows[0].keys():
        if col.lower() == "volume":
            vol_col = col
            break

    if not vol_col:
        print("  'volume' column not found in file.")
        return

    print(f"\n  {'ticker':<8} {'close':>10}  {'volume':>16}")
    print(f"  {'─' * 8} {'─' * 10}  {'─' * 16}")

    shown = 0
    fractional = 0
    total_decimal = 0.0
    total_int = 0
    total_dollar_decimal = 0.0
    total_dollar_int = 0.0
    for row in rows:
        vol_val = row.get(vol_col, "")
        ticker = row.get("ticker", row.get("sym", "???"))
        close = row.get("close", row.get("c", "N/A"))

        try:
            vol_f = float(vol_val)
            total_decimal += vol_f
            total_int += int(vol_f)
            if vol_f != int(vol_f):
                fractional += 1
            try:
                close_f = float(close)
                total_dollar_decimal += close_f * vol_f
                total_dollar_int += close_f * int(vol_f)
            except (ValueError, TypeError):
                pass
        except (ValueError, TypeError):
            pass

        if shown < 20:
            try:
                c_str = f"${float(close):,.2f}"
            except (ValueError, TypeError):
                c_str = str(close)
            print(f"  {ticker:<8} {c_str:>10}  {vol_val:>16}")
            shown += 1

    if fractional:
        print(f"\n  {fractional} of {len(rows)} rows have"
              " fractional volume values.")

    vol_hidden = total_decimal - total_int
    pct = (vol_hidden / total_decimal * 100) if total_decimal else 0
    print(f"\n  Impact across {len(rows)} rows:")
    print(f"    Volume: {total_decimal:,.2f} shares actual,"
          f" {total_int:,} reported"
          f"  ({vol_hidden:,.2f} hidden, {pct:.2f}%)")
    if total_dollar_decimal > 0:
        dollar_hidden = total_dollar_decimal - total_dollar_int
        print(f"    Dollars: ${total_dollar_decimal:,.2f} actual,"
              f" ${total_dollar_int:,.2f} reported"
              f"  (${dollar_hidden:,.2f} hidden)")

    if save:
        save_rows_to_csv(rows, f"aggs_{file_date.isoformat()}.csv")


def run_flatfiles(file_date, file_type, save=False):
    """Download partial flat files from S3 and display decimal fields."""
    banner("Massive Flat Files — Fractional Share Precision Demo")
    print(f"  Date:     {file_date.isoformat()}")
    print(f"  Endpoint: {S3_ENDPOINT}")
    print(f"  Bucket:   {S3_BUCKET}")
    print()
    print("  Fields that changed from integer to decimal:")
    print("    Trades:     size   (e.g. '0.500000')")
    print("    Aggregates: volume (e.g. '150.000000')")
    print(f"{'=' * W}")

    s3 = get_s3_client()

    if file_type in ("trades", "both"):
        demo_trades(s3, file_date, save=save)
    if file_type in ("aggs", "both"):
        demo_aggs(s3, file_date, save=save)

    print(f"\n{'=' * W}")


# ── CLI entry point ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Massive — Fractional Share Precision Demos",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # websocket
    ws_parser = subparsers.add_parser(
        "websocket",
        aliases=["ws"],
        help="Stream real-time trades and aggregates via WebSocket",
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
        help="Fetch last trade, snapshot v2, and snapshot v3 via REST",
    )
    rest_parser.add_argument(
        "tickers",
        nargs="*",
        default=["AAPL"],
        help="Stock tickers (default: AAPL)",
    )

    # flatfiles
    ff_parser = subparsers.add_parser(
        "flatfiles",
        aliases=["flat", "ff"],
        help="Download partial flat files from S3 and show decimal fields",
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
        help="Which flat file to demo (default: both)",
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
        run_rest(tickers)

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
