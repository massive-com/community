"""
Splits & Dividends Visualizer

Demo of Massive's new stock splits and dividends endpoints (/stocks/v1/splits,
/stocks/v1/dividends) and how they interact with price data and Flat Files.

For a given ticker, this script:
- Fetches recent splits and cash dividends (new endpoints only)
- Prints a corporate-actions summary table
- Builds two charts: (1) adjusted vs unadjusted daily closes (Custom Bars),
  (2) splits + dividends timeline
- Optionally uses Flat File day aggregates (S3) and applies
  historical_adjustment_factor to produce an adjusted CSV

Aligns with Massive docs: new endpoints replace deprecated reference endpoints;
adjustment factors follow Splits/Dividends API guidance for flat-file use.
"""

import argparse
import csv
import gzip
import io
import os
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple, Sequence

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from massive import RESTClient

# Massive Flat Files S3 (see https://massive.com/docs/flat-files/quickstart)
FLATFILES_BUCKET = "flatfiles"
FLATFILES_DAY_AGGS_PREFIX = "us_stocks_sip/day_aggs_v1"
MAX_FLATFILE_DAYS = 31


def _parse_date(date_str: str) -> datetime:
    """Parse API date strings (YYYY-MM-DD) into datetime objects."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def _parse_agg_timestamp(agg: object) -> datetime | None:
    """Best-effort parse of an aggregate bar timestamp into a datetime."""
    # Try common attribute names first
    ts = getattr(agg, "timestamp", None)
    if ts is None:
        ts = getattr(agg, "t", None)

    if isinstance(ts, (int, float)):
        # Unix ms
        return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    return None


def _get_agg_close(agg: object) -> float | None:
    """Best-effort retrieval of close price from an aggregate bar."""
    for attr in ("close", "c"):
        val = getattr(agg, attr, None)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def fetch_corporate_actions(
    client: RESTClient,
    ticker: str,
    max_splits: int = 5,
    max_dividends: int = 12,
) -> Tuple[List[object], List[object]]:
    """Fetch recent splits and dividends for a ticker using the new endpoints."""
    splits: List[object] = []
    dividends: List[object] = []

    # New Splits endpoint: /stocks/v1/splits
    if max_splits > 0:
        for s in client.list_stocks_splits(
            ticker=ticker,
            limit=max_splits,
            sort="execution_date.asc",
        ):
            splits.append(s)

    # New Dividends endpoint: /stocks/v1/dividends
    if max_dividends > 0:
        for d in client.list_stocks_dividends(
            ticker=ticker,
            limit=max_dividends,
            sort="ex_dividend_date.asc",
        ):
            dividends.append(d)

    return splits, dividends


def fetch_adjusted_and_unadjusted_aggs(
    client: RESTClient,
    ticker: str,
    from_date: str,
    to_date: str,
) -> Tuple[List[object], List[object]]:
    """
    Fetch daily aggregates for a ticker over a date range, once with
    adjusted=False and once with adjusted=True, using the Custom Bars (OHLC)
    endpoint (/v2/aggs/...).
    """
    unadjusted: List[object] = []
    adjusted: List[object] = []

    for a in client.list_aggs(
        ticker,
        1,
        "day",
        from_date,
        to_date,
        adjusted=False,
        limit=50000,
        sort="asc",
    ):
        unadjusted.append(a)

    for a in client.list_aggs(
        ticker,
        1,
        "day",
        from_date,
        to_date,
        adjusted=True,
        limit=50000,
        sort="asc",
    ):
        adjusted.append(a)

    return unadjusted, adjusted


def print_summary(ticker: str, splits: Iterable[object], dividends: Iterable[object]) -> None:
    """Print a concise text summary of splits & dividends for quick inspection."""
    splits = list(splits)
    dividends = list(dividends)

    print(f"\n📈 Corporate actions overview for {ticker}")
    print("-" * 72)

    if splits:
        print("\n🔀 Stock splits (new Splits endpoint)")
        print(f"{'Date':<12} {'Type':<14} {'Ratio':<10} {'Adj Factor':<12}")
        print("-" * 52)
        for s in splits:
            execution_date = getattr(s, "execution_date", "?")
            adjustment_type = getattr(s, "adjustment_type", "unknown")
            split_from = getattr(s, "split_from", None)
            split_to = getattr(s, "split_to", None)
            ratio_str = f"{split_to}:{split_from}" if split_from and split_to else "-"
            factor = getattr(s, "historical_adjustment_factor", None)
            factor_str = f"{factor:.6f}" if isinstance(factor, (int, float)) else "-"
            print(f"{execution_date:<12} {adjustment_type:<14} {ratio_str:<10} {factor_str:<12}")
    else:
        print("\n🔀 Stock splits: none found in the requested window.")

    if dividends:
        print("\n💰 Cash dividends (new Dividends endpoint)")
        print(f"{'Ex-Date':<12} {'Type':<12} {'Freq':<6} {'Cash':<10} {'Adj Factor':<12}")
        print("-" * 64)
        for d in dividends:
            ex_date = getattr(d, "ex_dividend_date", "?")
            dist_type = getattr(d, "distribution_type", "unknown")
            frequency = getattr(d, "frequency", None)
            freq_str = str(frequency) if frequency is not None else "-"
            cash = getattr(d, "cash_amount", None)
            cash_str = f"{cash:.4f}" if isinstance(cash, (int, float)) else "-"
            factor = getattr(d, "historical_adjustment_factor", None)
            factor_str = f"{factor:.6f}" if isinstance(factor, (int, float)) else "-"
            print(f"{ex_date:<12} {dist_type:<12} {freq_str:<6} {cash_str:<10} {factor_str:<12}")
    else:
        print("\n💰 Cash dividends: none found in the requested window.")

    print()


def plot_actions_chart(
    ticker: str,
    splits: Iterable[object],
    dividends: Iterable[object],
    output_dir: Path,
) -> Path:
    """
    Build a simple two-panel chart:

    - Top: stock split ratios over time (e.g., 2:1, 7:1, 4:1)
    - Bottom: dividend cash amounts over time, colored by distribution_type

    The chart is saved as a PNG and the path is returned.
    """
    splits = list(splits)
    dividends = list(dividends)

    if not splits and not dividends:
        raise RuntimeError("No splits or dividends to plot — nothing to visualize.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ticker.lower()}_splits_dividends.png"

    plt.style.use("seaborn-v0_8")
    fig, (ax_splits, ax_divs) = plt.subplots(
        2,
        1,
        figsize=(10, 6),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 3]},
    )

    # --- Splits panel -------------------------------------------------------
    if splits:
        split_dates = [_parse_date(getattr(s, "execution_date")) for s in splits]
        split_ratios = []
        split_labels = []
        for s in splits:
            split_from = getattr(s, "split_from", None) or 1.0
            split_to = getattr(s, "split_to", None) or 1.0
            split_ratios.append(float(split_to) / float(split_from))
            split_labels.append(f"{int(split_to)}:{int(split_from)}")

        markerline, stemlines, baseline = ax_splits.stem(
            split_dates,
            split_ratios,
            linefmt="C0-",
            markerfmt="C0o",
            basefmt=" ",
        )
        markerline.set_markersize(8)

        for date, ratio, label in zip(split_dates, split_ratios, split_labels):
            ax_splits.text(
                date,
                ratio + 0.1,
                label,
                ha="center",
                va="bottom",
                fontsize=8,
            )

        ax_splits.set_ylabel("Split ratio\n(new:old)")
        ax_splits.set_title(f"{ticker} stock splits (new Splits endpoint)")
    else:
        ax_splits.text(
            0.5,
            0.5,
            "No recent splits",
            ha="center",
            va="center",
            transform=ax_splits.transAxes,
            fontsize=10,
            color="gray",
        )
        ax_splits.set_ylabel("Split ratio")

    # --- Dividends panel ----------------------------------------------------
    if dividends:
        div_dates = [_parse_date(getattr(d, "ex_dividend_date")) for d in dividends]
        cash_amounts = [
            getattr(d, "split_adjusted_cash_amount", None)
            or getattr(d, "cash_amount", 0.0)
            for d in dividends
        ]
        dist_types = [getattr(d, "distribution_type", "unknown") for d in dividends]

        # Map distribution_type to colors for a quick visual legend
        type_colors = {
            "recurring": "C2",
            "special": "C3",
            "supplemental": "C4",
            "irregular": "C1",
            "unknown": "C7",
        }
        colors = [type_colors.get(t, "C7") for t in dist_types]

        ax_divs.bar(div_dates, cash_amounts, width=15, color=colors, alpha=0.9)

        ax_divs.set_ylabel("Cash dividend\n(per share)")
        ax_divs.set_title(f"{ticker} cash dividends (new Dividends endpoint)")

        # Build a small legend for distribution types actually present
        seen_types = {}
        for t, c in zip(dist_types, colors):
            if t not in seen_types:
                seen_types[t] = c
        handles = [
            plt.Line2D(
                [0],
                [0],
                color=c,
                lw=6,
                label=t,
            )
            for t, c in seen_types.items()
        ]
        if handles:
            ax_divs.legend(
                handles=handles,
                title="distribution_type",
                loc="upper left",
                fontsize=8,
            )
    else:
        ax_divs.text(
            0.5,
            0.5,
            "No recent dividends",
            ha="center",
            va="center",
            transform=ax_divs.transAxes,
            fontsize=10,
            color="gray",
        )
        ax_divs.set_ylabel("Dividend")

    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


def plot_adjusted_vs_unadjusted_chart(
    ticker: str,
    unadjusted: Iterable[object],
    adjusted: Iterable[object],
    output_dir: Path,
) -> Path:
    """
    Plot adjusted vs unadjusted daily close prices using the Custom Bars (OHLC)
    endpoint. This visually highlights how split- and dividend-adjusted series
    differ from raw prices over the same window.
    """
    unadjusted = list(unadjusted)
    adjusted = list(adjusted)

    if not unadjusted or not adjusted:
        raise RuntimeError("No aggregate bars returned to plot — nothing to visualize.")

    # Build (x, y) pairs for each series
    def _series_from_aggs(bars: List[object]) -> Tuple[List[datetime], List[float]]:
        xs: List[datetime] = []
        ys: List[float] = []
        for bar in bars:
            close = _get_agg_close(bar)
            ts = _parse_agg_timestamp(bar)
            if close is None or ts is None:
                continue
            xs.append(ts)
            ys.append(close)
        return xs, ys

    x_unadj, y_unadj = _series_from_aggs(unadjusted)
    x_adj, y_adj = _series_from_aggs(adjusted)

    if not x_unadj or not x_adj:
        raise RuntimeError("Could not extract close prices from aggregate bars.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ticker.lower()}_adjusted_vs_unadjusted.png"

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(10, 4))

    ax.plot(x_unadj, y_unadj, label="Unadjusted close", color="C1", alpha=0.7, linestyle="--")
    ax.plot(x_adj, y_adj, label="Adjusted close", color="C0", alpha=0.9)

    ax.set_title(f"{ticker} adjusted vs unadjusted daily closes")
    ax.set_ylabel("Price")
    ax.legend(loc="best", fontsize=8)

    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


def _first_factor_after(
    base_date: date,
    events: Iterable[object],
    date_attr: str,
) -> float:
    """
    For a given date, find the first event whose date field is AFTER that date
    and return its historical_adjustment_factor. If none found, return 1.0.

    This mirrors the guidance from the Splits and Dividends docs for applying
    factors to flat-file historical prices.
    """
    best_event_date: date | None = None
    best_factor: float = 1.0

    for ev in events:
        raw = getattr(ev, date_attr, None)
        if not raw:
            continue
        try:
            ev_date = datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            continue

        if ev_date <= base_date:
            continue

        if best_event_date is None or ev_date < best_event_date:
            factor = getattr(ev, "historical_adjustment_factor", None)
            if isinstance(factor, (int, float)):
                best_event_date = ev_date
                best_factor = float(factor)

    return best_factor


def _build_flatfile_adjusted_rows(
    date_close_pairs: Sequence[Tuple[date, float]],
    splits: List[object],
    dividends: List[object],
) -> List[Tuple[str, float, float, float, float, float]]:
    """Apply historical_adjustment_factor to (date, close) pairs; return rows for CSV."""
    out: List[Tuple[str, float, float, float, float, float]] = []
    for base_date, close in date_close_pairs:
        split_factor = _first_factor_after(base_date, splits, "execution_date") if splits else 1.0
        div_factor = _first_factor_after(base_date, dividends, "ex_dividend_date") if dividends else 1.0
        total_factor = split_factor * div_factor
        adjusted_close = close * total_factor
        out.append(
            (
                base_date.strftime("%Y-%m-%d"),
                close,
                adjusted_close,
                split_factor,
                div_factor,
                total_factor,
            )
        )
    out.sort(key=lambda r: r[0])
    return out


def write_flatfile_adjustments_csv(
    ticker: str,
    splits: Iterable[object],
    dividends: Iterable[object],
    output_dir: Path,
    *,
    unadjusted: Iterable[object] | None = None,
    unadjusted_rows: Sequence[Tuple[date, float]] | None = None,
) -> Path:
    """
    Apply historical_adjustment_factor and write output/<ticker>_flatfile_adjusted.csv.

    Data source (one required):
    - unadjusted: REST aggregate bars (objects with timestamp + close).
    - unadjusted_rows: list of (date, close) from e.g. a Flat File CSV.
    """
    splits = list(splits)
    dividends = list(dividends)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ticker.lower()}_flatfile_adjusted.csv"

    if unadjusted_rows is not None:
        rows = _build_flatfile_adjusted_rows(unadjusted_rows, splits, dividends)
    elif unadjusted is not None:
        date_close_pairs: List[Tuple[date, float]] = []
        for bar in unadjusted:
            ts = _parse_agg_timestamp(bar)
            close = _get_agg_close(bar)
            if ts is not None and close is not None:
                date_close_pairs.append((ts.date(), close))
        if not date_close_pairs:
            raise RuntimeError("No unadjusted aggregates available for flat-file example.")
        rows = _build_flatfile_adjusted_rows(date_close_pairs, splits, dividends)
    else:
        raise RuntimeError("Provide either unadjusted (REST bars) or unadjusted_rows (date, close) pairs.")

    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "close_unadjusted",
                "close_adjusted_flatfile",
                "split_factor",
                "dividend_factor",
                "total_factor",
            ]
        )
        writer.writerows(rows)

    return output_path


def load_flatfile_unadjusted_csv(csv_path: Path) -> List[Tuple[date, float]]:
    """
    Read a Flat File day-aggregates CSV (e.g. from --download-flatfile).
    Returns list of (trading_date, close). Expects columns: close, window_start (nanoseconds).
    """
    pairs: List[Tuple[date, float]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            close_raw = row.get("close")
            window_start_raw = row.get("window_start")
            if not close_raw or not window_start_raw:
                continue
            try:
                close = float(close_raw)
                ns = int(window_start_raw)
                sec = ns / 1e9
                base_date = datetime.fromtimestamp(sec, tz=timezone.utc).date()
                pairs.append((base_date, close))
            except (ValueError, TypeError):
                continue
    return pairs


def build_client() -> RESTClient:
    """Create a REST client using MASSIVE_API_KEY from the environment."""
    load_dotenv()
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        raise RuntimeError("MASSIVE_API_KEY not set in environment.")
    return RESTClient(api_key=api_key, pagination=False)


def _get_flatfiles_s3_client():
    """Build an S3 client for Massive Flat Files (endpoint + credentials from env)."""
    load_dotenv()
    access_key = os.getenv("MASSIVE_FLATFILES_ACCESS_KEY_ID")
    secret_key = os.getenv("MASSIVE_FLATFILES_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise RuntimeError(
            "Flat Files credentials not set. Add MASSIVE_FLATFILES_ACCESS_KEY_ID and "
            "MASSIVE_FLATFILES_SECRET_ACCESS_KEY to your .env (see .env.example). "
            "Get S3 keys from https://massive.com/dashboard/keys"
        )
    endpoint = os.getenv("MASSIVE_FLATFILES_ENDPOINT_URL", "https://files.massive.com")

    import boto3
    from botocore.config import Config

    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return session.client(
        "s3",
        endpoint_url=endpoint,
        config=Config(signature_version="s3v4"),
    )


def download_flatfile_day_aggs(
    ticker: str,
    from_date: str,
    to_date: str,
    out_dir: Path,
) -> Path:
    """
    Download Massive Stocks Day Aggregates flat files from S3 for the given date
    range, filter to a single ticker, and write data/<ticker>_unadjusted.csv.

    Uses credentials from .env: MASSIVE_FLATFILES_ACCESS_KEY_ID and
    MASSIVE_FLATFILES_SECRET_ACCESS_KEY. See https://massive.com/docs/flat-files/quickstart.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ticker.lower()}_unadjusted.csv"

    from_d = datetime.strptime(from_date, "%Y-%m-%d").date()
    to_d = datetime.strptime(to_date, "%Y-%m-%d").date()
    if (to_d - from_d).days > MAX_FLATFILE_DAYS:
        raise RuntimeError(
            f"Date range is larger than {MAX_FLATFILE_DAYS} days. "
            f"Use a shorter --flatfile-from-date / --flatfile-to-date range."
        )

    s3 = _get_flatfiles_s3_client()
    all_rows: List[dict] = []
    header: List[str] | None = None

    current = from_d
    while current <= to_d:
        year = current.year
        month = current.month
        key = f"{FLATFILES_DAY_AGGS_PREFIX}/{year}/{month:02d}/{current.isoformat()}.csv.gz"
        try:
            resp = s3.get_object(Bucket=FLATFILES_BUCKET, Key=key)
            body = resp["Body"].read()
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "NoSuchKey":
                current += timedelta(days=1)
                continue
            raise RuntimeError(f"Failed to download s3://{FLATFILES_BUCKET}/{key}: {e}") from e

        with gzip.open(io.BytesIO(body), "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if header is None and reader.fieldnames:
                header = list(reader.fieldnames)
            for row in reader:
                if row.get("ticker") == ticker:
                    all_rows.append(row)

        current += timedelta(days=1)

    if not all_rows or not header:
        raise RuntimeError(
            f"No day-aggregate rows found for {ticker} between {from_date} and {to_date}. "
            "Check ticker and that Flat Files day aggregates are available for your plan."
        )

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_rows)

    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Visualize stock splits and dividends for a ticker using "
            "Massive's new corporate actions endpoints."
        )
    )
    parser.add_argument(
        "--ticker",
        "-t",
        default="AAPL",
        help="Ticker symbol to analyze (default: AAPL).",
    )
    parser.add_argument(
        "--max-splits",
        type=int,
        default=5,
        help="Maximum number of splits to fetch (default: 5).",
    )
    parser.add_argument(
        "--max-dividends",
        type=int,
        default=16,
        help="Maximum number of dividends to fetch (default: 16).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("output"),
        help="Directory to save the chart PNG into (default: ./output).",
    )
    parser.add_argument(
        "--mode",
        choices=["both", "actions", "adjusted-bars"],
        default="both",
        help=(
            "Which chart to generate: 'adjusted-bars' for adjusted vs unadjusted "
            "daily closes, 'actions' for the splits/dividends timeline, or "
            "'both' (default) for both charts."
        ),
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        help="Start date for aggregates (YYYY-MM-DD). Defaults to 1 year ago.",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        help="End date for aggregates (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--download-flatfile",
        action="store_true",
        help="Download Stocks Day Aggregates from Massive Flat Files (S3) for --ticker "
             "over --flatfile-from-date to --flatfile-to-date, then exit. Writes data/<ticker>_unadjusted.csv.",
    )
    parser.add_argument(
        "--flatfile-from-date",
        metavar="YYYY-MM-DD",
        help="Start date for Flat Files download (with --download-flatfile). Default: 7 days before --flatfile-to-date.",
    )
    parser.add_argument(
        "--flatfile-to-date",
        metavar="YYYY-MM-DD",
        help="End date for Flat Files download (with --download-flatfile). Default: yesterday.",
    )
    parser.add_argument(
        "--flatfile-datadir",
        type=Path,
        default=Path("data"),
        help="Directory for downloaded flat-file CSV (default: data).",
    )
    parser.add_argument(
        "--use-flatfile",
        nargs="?",
        const=True,
        default=None,
        metavar="PATH",
        help="Use Flat File CSV as source for the adjusted CSV: download to data/<ticker>_unadjusted.csv if missing, "
             "then apply historical_adjustment_factor and write output/<ticker>_flatfile_adjusted.csv. "
             "Optional PATH overrides default (flatfile-datadir/<ticker>_unadjusted.csv).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker = args.ticker.upper()

    # Optional: download Flat Files day aggregates from S3, then exit
    if args.download_flatfile:
        load_dotenv()
        to_d = args.flatfile_to_date or (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        from_d = args.flatfile_from_date or (datetime.strptime(to_d, "%Y-%m-%d").date() - timedelta(days=7)).strftime("%Y-%m-%d")
        try:
            path = download_flatfile_day_aggs(
                ticker=ticker,
                from_date=from_d,
                to_date=to_d,
                out_dir=args.flatfile_datadir,
            )
            print(f"📄 Downloaded Flat Files day aggregates for {ticker} to: {path}")
            print("   Use this CSV with the rest of the demo (historical_adjustment_factor, etc.).")
        except RuntimeError as e:
            print(f"⚠  {e}")
        return

    client = build_client()
    splits, dividends = fetch_corporate_actions(
        client,
        ticker=ticker,
        max_splits=args.max_splits,
        max_dividends=args.max_dividends,
    )

    print_summary(ticker, splits, dividends)

    try:
        do_actions = args.mode in ("both", "actions")
        do_adjusted = args.mode in ("both", "adjusted-bars")

        if do_actions:
            actions_path = plot_actions_chart(
                ticker=ticker,
                splits=splits,
                dividends=dividends,
                output_dir=args.outdir,
            )
            print(f"🖼  Saved corporate actions chart to: {actions_path}")

        if do_adjusted:
            # Adjusted vs unadjusted daily closes using Custom Bars (OHLC)
            today = date.today()

            # Chart date range: explicit --from-date/--to-date wins; else use flat-file range if set (so charts match flat-file window)
            to_date = args.to_date or args.flatfile_to_date or today.strftime("%Y-%m-%d")
            if args.from_date:
                from_date = args.from_date
            elif args.flatfile_from_date:
                from_date = args.flatfile_from_date
            else:
                # Default: 1 year ending at latest split, or 1 year ago
                if splits:
                    latest_split = splits[-1]
                    latest_date_str = getattr(latest_split, "execution_date", None)
                    try:
                        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()  # type: ignore[arg-type]
                        from_date = (latest_date - timedelta(days=365)).strftime("%Y-%m-%d")
                    except Exception:
                        from_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
                else:
                    from_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")

            unadjusted, adjusted = fetch_adjusted_and_unadjusted_aggs(
                client,
                ticker=ticker,
                from_date=from_date,
                to_date=to_date,
            )
            adj_chart_path = plot_adjusted_vs_unadjusted_chart(
                ticker=ticker,
                unadjusted=unadjusted,
                adjusted=adjusted,
                output_dir=args.outdir,
            )
            print(f"🖼  Saved adjusted vs unadjusted chart to: {adj_chart_path}")

            # Emit a flat-file style CSV that applies historical_adjustment_factor.
            # Source: --use-flatfile CSV if set, else REST unadjusted bars.
            try:
                if args.use_flatfile is not None:
                    flatfile_path = Path(args.use_flatfile) if isinstance(args.use_flatfile, str) else args.flatfile_datadir / f"{ticker.lower()}_unadjusted.csv"
                    if not flatfile_path.exists():
                        to_d = args.flatfile_to_date or (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                        from_d = args.flatfile_from_date or (datetime.strptime(to_d, "%Y-%m-%d").date() - timedelta(days=7)).strftime("%Y-%m-%d")
                        flatfile_path = download_flatfile_day_aggs(ticker=ticker, from_date=from_d, to_date=to_d, out_dir=args.flatfile_datadir)
                        print(f"📄 Downloaded Flat File for {ticker} to: {flatfile_path}")
                    flatfile_rows = load_flatfile_unadjusted_csv(flatfile_path)
                    if not flatfile_rows:
                        print(f"⚠  No rows in {flatfile_path}; skipping flat-file adjusted CSV.")
                    else:
                        csv_path = write_flatfile_adjustments_csv(
                            ticker=ticker,
                            splits=splits,
                            dividends=dividends,
                            output_dir=args.outdir,
                            unadjusted_rows=flatfile_rows,
                        )
                        print(f"📄 Wrote flat-file adjusted CSV (from Flat File) to: {csv_path}")
                else:
                    csv_path = write_flatfile_adjustments_csv(
                        ticker=ticker,
                        splits=splits,
                        dividends=dividends,
                        output_dir=args.outdir,
                        unadjusted=unadjusted,
                    )
                    print(f"📄 Wrote flat-file adjusted CSV to: {csv_path}")
            except RuntimeError as e:
                print(f"⚠  Could not write flat-file CSV: {e}")

        print("   Open the generated PNG(s) in your image viewer to explore the series.")
    except RuntimeError as exc:
        # No data to plot – still a valid run, just no visualization.
        print(f"⚠  {exc}")


if __name__ == "__main__":
    main()
