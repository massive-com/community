#!/usr/bin/env python3
"""
SEC Filings & Disclosures Demo
===============================
Explores SEC filings data through Massive's filings and disclosures API
endpoints (currently in beta). Search the EDGAR index, read 10-K sections
and 8-K event reports, browse structured risk factors, and explore the
risk factor taxonomy. Compare risk profiles across companies and track
how disclosures change over time.

Usage:
    uv run python main.py index TICKER [--form-type TYPE] [--limit N]
    uv run python main.py 10k TICKER [--section SECTION] [--date DATE]
    uv run python main.py 8k TICKER [--date DATE] [--limit N]
    uv run python main.py risks TICKER [--date DATE] [--limit N]
    uv run python main.py taxonomy [--primary CATEGORY] [--limit N]
    uv run python main.py compare TICKER TICKER [TICKER ...] [--save]
    uv run python main.py timeline TICKER [--filings N] [--save]
"""
import argparse
import json
import os
import sys
import textwrap
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

W = 62


# -- Shared utilities --------------------------------------------------------


def get_api_key():
    """Return the Massive API key or exit."""
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        print("  Error: MASSIVE_API_KEY not set in environment.")
        print("  Add it to your .env file or export it directly.")
        sys.exit(1)
    return key


def get_client():
    """Return an authenticated Massive RESTClient."""
    from massive import RESTClient

    return RESTClient(api_key=get_api_key())


def banner(title):
    """Print a === banner line with a title."""
    print(f"\n{'=' * W}")
    print(f"  {title}")
    print(f"{'=' * W}")


def section(title):
    """Print a --- section divider with a title."""
    print(f"\n  {'-' * (W - 4)}")
    print(f"  {title}")
    print(f"  {'-' * (W - 4)}")


def preview_text(text, max_chars=500):
    """Return a truncated preview of long text."""
    if not text:
        return "(empty)"
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... ({len(text):,} chars total)"


MAX_TABLE_WIDTH = 120


def _format_table(rows, indent="    "):
    """Format pipe-delimited rows into an aligned table.

    If the aligned table would exceed MAX_TABLE_WIDTH characters,
    falls back to a compact key-value format per row.
    """
    # Parse cells from each row
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        # Drop empty trailing cells from trailing pipes
        while cells and not cells[-1]:
            cells.pop()
        parsed.append(cells)

    if not parsed:
        return []

    # Calculate column widths for aligned mode
    num_cols = max(len(r) for r in parsed)
    widths = [0] * num_cols
    for r in parsed:
        for i, cell in enumerate(r):
            if i < num_cols:
                widths[i] = max(widths[i], len(cell))

    total_width = len(indent) + sum(widths) + 2 * (num_cols - 1)

    # If table fits, use aligned columns
    if total_width <= MAX_TABLE_WIDTH:
        output = []
        for row_idx, r in enumerate(parsed):
            parts = []
            for i in range(num_cols):
                cell = r[i] if i < len(r) else ""
                parts.append(cell.ljust(widths[i]))
            line = indent + "  ".join(parts).rstrip()
            output.append(line)
            if row_idx == 0:
                sep_parts = ["-" * w for w in widths]
                output.append(indent + "  ".join(sep_parts))
        return output

    # Wide table: use header row as keys, print each data row as key-value
    headers = parsed[0] if parsed else []
    output = []
    for row_idx, r in enumerate(parsed):
        if row_idx == 0:
            continue
        for i, cell in enumerate(r):
            if not cell:
                continue
            key = headers[i] if i < len(headers) else f"Col {i+1}"
            output.append(f"{indent}{key}: {cell}")
        if row_idx < len(parsed) - 1:
            output.append("")
    return output


def wrap_and_indent(text, width=54, indent="    "):
    """Wrap text to width and indent each line.

    Respects existing line breaks. Consecutive pipe-delimited lines
    are grouped and formatted as aligned tables. Section headers
    (lines starting with "Item") get a blank line before them.
    """
    lines = text.split("\n")
    output = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            output.append("")
            i += 1
            continue

        # Add visual break before Item headers
        if line.startswith("Item ") and output:
            output.append("")
            output.append("")

        # Numbered list items get a blank line before them
        if _is_numbered_item(line) and output and output[-1] != "":
            output.append("")

        # Collect consecutive pipe-delimited lines into a table
        if "|" in line:
            table_rows = []
            while i < len(lines) and "|" in lines[i]:
                table_rows.append(lines[i].strip())
                i += 1
            output.append("")
            output.extend(_format_table(table_rows, indent=indent))
            output.append("")
            continue

        # Regular text: wrap to width
        wrapped = textwrap.wrap(line, width=width)
        for w in wrapped:
            output.append(indent + w)
        i += 1

    return "\n".join(output)


def _is_numbered_item(line):
    """Check if a line starts with a numbered list pattern like (1), (2), (10)."""
    if line.startswith("("):
        close = line.find(")")
        if close > 1 and line[1:close].isdigit():
            return True
    return False


def save_json(data, filename):
    """Save results to a JSON file in data/ directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Saved to {path}")
    return path


# -- index subcommand --------------------------------------------------------


def run_index(ticker, form_type=None, limit=10, save=False):
    """Search the SEC EDGAR filing index for a ticker."""
    client = get_client()

    banner("SEC EDGAR Filing Index")
    print(f"  Ticker:    {ticker}")
    if form_type:
        print(f"  Form type: {form_type}")
    print(f"  Limit:     {limit}")
    print(f"{'=' * W}")

    params = {"ticker": ticker, "limit": limit, "sort": "filing_date.desc"}
    if form_type:
        params["form_type"] = form_type

    results = client._get("/stocks/filings/vX/index", params=params,
                          result_key="results")

    if not results:
        print("\n  No filings found.")
        print(f"\n{'=' * W}")
        return

    print(f"\n  Found {len(results)} filing(s):\n")
    print(f"  {'Date':<12} {'Form':<10} {'Issuer':<30}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 30}")

    for r in results:
        filing_date = r.get("filing_date", "N/A")
        form = r.get("form_type", "N/A")
        issuer = r.get("issuer_name", "N/A")
        if len(issuer) > 30:
            issuer = issuer[:27] + "..."
        print(f"  {filing_date:<12} {form:<10} {issuer:<30}")

    # Show filing URLs for first few results
    section("Filing URLs (first 3)")
    for r in results[:3]:
        url = r.get("filing_url", "")
        form = r.get("form_type", "")
        filing_date = r.get("filing_date", "")
        if url:
            print(f"  {form} ({filing_date})")
            print(f"    {url}")

    if len(results) > 3:
        print(f"\n  ... and {len(results) - 3} more (use --save to export all)")

    if save:
        save_json(results, f"index_{ticker}_{form_type or 'all'}.json")

    print(f"\n{'=' * W}")


# -- 10k subcommand ----------------------------------------------------------


def run_10k(ticker, section_name="risk_factors", filing_date=None,
            limit=1, full=False, save=False):
    """Fetch 10-K section text (risk factors or business description)."""
    client = get_client()

    banner("10-K Section Content")
    print(f"  Ticker:  {ticker}")
    print(f"  Section: {section_name}")
    if filing_date:
        print(f"  On or before: {filing_date}")
    print(f"{'=' * W}")

    params = {
        "ticker": ticker,
        "section": section_name,
        "limit": limit,
        "sort": "filing_date.desc",
    }
    if filing_date:
        params["filing_date.lte"] = filing_date

    results = client._get("/stocks/filings/10-K/vX/sections", params=params,
                          result_key="results")

    if not results:
        print("\n  No 10-K sections found for this ticker and section.")
        print(f"\n{'=' * W}")
        return

    for r in results:
        filing_date_val = r.get("filing_date", "N/A")
        period = r.get("period_end", "N/A")
        text = r.get("text", "")
        url = r.get("filing_url", "")

        section(f"Filed {filing_date_val} (period ending {period})")
        if url:
            print(f"  Source: {url}")
        print()

        if full:
            print(wrap_and_indent(text.strip()))
        else:
            preview = preview_text(text, max_chars=800)
            print(wrap_and_indent(preview))

            if len(text) > 800:
                print(f"\n    [{len(text):,} characters total."
                      " Use --full to print or --save to export.]")

    if save:
        save_json(results, f"10k_{ticker}_{section_name}.json")

    print(f"\n{'=' * W}")


# -- 8k subcommand -----------------------------------------------------------


def run_8k(ticker, filing_date=None, limit=3, full=False, save=False):
    """Fetch 8-K current report text."""
    client = get_client()

    banner("8-K Current Reports")
    print(f"  Ticker: {ticker}")
    if filing_date:
        print(f"  On or before: {filing_date}")
    print(f"  Limit:  {limit}")
    print(f"{'=' * W}")

    params = {
        "ticker": ticker,
        "limit": limit,
        "sort": "filing_date.desc",
    }
    if filing_date:
        params["filing_date.lte"] = filing_date

    results = client._get("/stocks/filings/8-K/vX/text", params=params,
                          result_key="results")

    if not results:
        print("\n  No 8-K text found for this ticker.")
        print("  The 8-K text endpoint is in beta and does not yet have")
        print("  parsed content for all filers. The filing may exist in")
        print("  the index (try: main.py index TICKER --form-type 8-K)")
        print("  before parsed text is available here.")
        print(f"\n{'=' * W}")
        return

    print(f"\n  Found {len(results)} report(s):")

    for r in results:
        filing_date_val = r.get("filing_date", "N/A")
        form = r.get("form_type", "8-K")
        accession = r.get("accession_number", "N/A")
        text = r.get("items_text", "")
        url = r.get("filing_url", "")

        section(f"{form} filed {filing_date_val}")
        print(f"  Accession: {accession}")
        if url:
            print(f"  Source:    {url}")
        print()

        if full:
            print(wrap_and_indent(text.strip()))
        else:
            preview = preview_text(text, max_chars=600)
            print(wrap_and_indent(preview))

            if len(text) > 600:
                print(f"\n    [{len(text):,} characters total."
                      " Use --full to print or --save to export.]")

    if save:
        save_json(results, f"8k_{ticker}.json")

    print(f"\n{'=' * W}")


# -- risks subcommand --------------------------------------------------------


def run_risks(ticker, filing_date=None, limit=10, save=False):
    """Fetch structured risk factor disclosures via the SDK."""
    client = get_client()

    banner("Structured Risk Factors")
    print(f"  Ticker: {ticker}")
    if filing_date:
        print(f"  On or before: {filing_date}")
    print(f"  Limit:  {limit}")
    print(f"{'=' * W}")

    kwargs = {"ticker": ticker, "limit": limit, "sort": "filing_date.desc"}
    if filing_date:
        kwargs["filing_date_lte"] = filing_date

    results = []
    for rf in client.list_stocks_filings_risk_factors(**kwargs):
        results.append(rf)

    if not results:
        print("\n  No risk factors found for this ticker.")
        print(f"\n{'=' * W}")
        return

    print(f"\n  Found {len(results)} risk factor(s):")

    # Group by filing date for cleaner output
    by_date = {}
    for r in results:
        d = r.filing_date or "Unknown"
        by_date.setdefault(d, []).append(r)

    for filing_dt, risks in by_date.items():
        section(f"Filing date: {filing_dt}")

        for i, r in enumerate(risks, 1):
            primary = r.primary_category or "N/A"
            secondary = r.secondary_category or ""
            tertiary = r.tertiary_category or ""
            text = r.supporting_text or ""

            cat_parts = [primary]
            if secondary:
                cat_parts.append(secondary)
            if tertiary:
                cat_parts.append(tertiary)
            category = " > ".join(cat_parts)

            print(f"\n  {i}. {category}")
            if text:
                preview = preview_text(text, max_chars=200)
                print(wrap_and_indent(preview, width=50, indent="     "))

    if save:
        raw = [
            {
                "ticker": r.ticker,
                "cik": r.cik,
                "filing_date": r.filing_date,
                "primary_category": r.primary_category,
                "secondary_category": r.secondary_category,
                "tertiary_category": r.tertiary_category,
                "supporting_text": r.supporting_text,
            }
            for r in results
        ]
        save_json(raw, f"risks_{ticker}.json")

    print(f"\n{'=' * W}")


# -- taxonomy subcommand -----------------------------------------------------


def run_taxonomy(primary=None, secondary=None, limit=20, save=False):
    """Browse the risk factor taxonomy via the SDK."""
    client = get_client()

    banner("Risk Factor Taxonomy")
    if primary:
        print(f"  Primary: {primary}")
    if secondary:
        print(f"  Secondary: {secondary}")
    print(f"  Limit: {limit}")
    print(f"{'=' * W}")

    kwargs = {"limit": limit}
    if primary:
        kwargs["primary_category"] = primary
    if secondary:
        kwargs["secondary_category"] = secondary

    results = []
    for entry in client.list_stocks_taxonomies_risk_factors(**kwargs):
        results.append(entry)

    if not results:
        print("\n  No taxonomy entries found.")
        print(f"\n{'=' * W}")
        return

    count = len(results)
    print(f"\n  Found {count} categor{'y' if count == 1 else 'ies'}:\n")

    # Group by primary category for readability
    by_primary = {}
    for r in results:
        p = r.primary_category or "Unknown"
        by_primary.setdefault(p, []).append(r)

    for primary_cat, entries in by_primary.items():
        print(f"  [{primary_cat}]")

        for e in entries:
            sec = e.secondary_category or ""
            ter = e.tertiary_category or ""
            desc = e.description or ""

            if ter:
                label = f"    {sec} > {ter}"
            elif sec:
                label = f"    {sec}"
            else:
                label = "    (top-level)"

            print(label)
            if desc:
                short_desc = desc[:78] + "..." if len(desc) > 78 else desc
                print(f"      {short_desc}")
        print()

    if save:
        raw = [
            {
                "taxonomy": e.taxonomy,
                "primary_category": e.primary_category,
                "secondary_category": e.secondary_category,
                "tertiary_category": e.tertiary_category,
                "description": e.description,
            }
            for e in results
        ]
        save_json(raw, "taxonomy_risk_factors.json")

    print(f"{'=' * W}")


# -- Shared risk-factor helper ------------------------------------------------


def _fetch_risks_by_date(client, ticker, limit=1000):
    """Fetch all risk factors for a ticker, grouped by filing date.

    Returns an ordered dict of {filing_date: [risk_factor, ...]} with the
    most recent filing date first.
    """
    results = list(
        client.list_stocks_filings_risk_factors(
            ticker=ticker, limit=limit, sort="filing_date.desc",
        )
    )
    by_date = {}
    for r in results:
        d = r.filing_date or "Unknown"
        by_date.setdefault(d, []).append(r)
    return by_date


# -- compare subcommand ------------------------------------------------------


def run_compare(tickers, save=False):
    """Compare risk factor profiles across two or more companies."""
    client = get_client()

    banner("Risk Factor Comparison")
    print(f"  Tickers: {', '.join(tickers)}")
    print(f"{'=' * W}")

    # Fetch most recent filing's risk factors for each ticker
    ticker_data = {}
    for t in tickers:
        by_date = _fetch_risks_by_date(client, t)
        if not by_date:
            print(f"\n  No risk factors found for {t}. Skipping.")
            continue
        latest_date = next(iter(by_date))
        ticker_data[t] = {
            "date": latest_date,
            "risks": by_date[latest_date],
        }

    if len(ticker_data) < 2:
        print("\n  Need risk factor data for at least 2 tickers to compare.")
        print(f"\n{'=' * W}")
        return

    # Show which filing dates are being compared
    for t, info in ticker_data.items():
        print(f"  {t}: {len(info['risks'])} risk factors "
              f"(filed {info['date']})")

    # -- Category distribution table --
    all_primaries = sorted(
        {r.primary_category for info in ticker_data.values()
         for r in info["risks"] if r.primary_category}
    )

    section("Category distribution")

    # Build counts
    counts = {}
    for t, info in ticker_data.items():
        counts[t] = defaultdict(int)
        for r in info["risks"]:
            if r.primary_category:
                counts[t][r.primary_category] += 1

    # Print table header
    col_w = max(len(t) for t in ticker_data) + 2
    cat_w = max((len(c) for c in all_primaries), default=20)
    cat_w = max(cat_w, 8)

    header = f"  {'Category':<{cat_w}}"
    for t in ticker_data:
        header += f"  {t:>{col_w}}"
    print(f"\n{header}")
    print(f"  {'-' * cat_w}" + f"  {'-' * col_w}" * len(ticker_data))

    for cat in all_primaries:
        row = f"  {cat:<{cat_w}}"
        for t in ticker_data:
            row += f"  {counts[t].get(cat, 0):>{col_w}}"
        print(row)

    # Totals
    print(f"  {'-' * cat_w}" + f"  {'-' * col_w}" * len(ticker_data))
    totals_row = f"  {'Total':<{cat_w}}"
    for t in ticker_data:
        totals_row += f"  {sum(counts[t].values()):>{col_w}}"
    print(totals_row)

    # -- Shared risk themes (secondary categories in all tickers) --
    secondary_sets = {}
    for t, info in ticker_data.items():
        secondary_sets[t] = {
            r.secondary_category for r in info["risks"]
            if r.secondary_category
        }

    shared = set.intersection(*secondary_sets.values())
    if shared:
        section("Shared risk themes")
        print(f"  Secondary categories disclosed by all {len(ticker_data)} "
              "companies:\n")
        for cat in sorted(shared):
            print(f"    {cat}")

    # -- Unique to each ticker --
    all_secondaries = set.union(*secondary_sets.values())
    has_unique = False
    unique_data = {}
    for t in ticker_data:
        others = set.union(*(s for k, s in secondary_sets.items() if k != t))
        unique = secondary_sets[t] - others
        if unique:
            if not has_unique:
                section("Unique to each company")
                has_unique = True
            unique_data[t] = sorted(unique)
            print(f"\n  {t} only:")
            for cat in unique_data[t]:
                print(f"    {cat}")

    if not has_unique:
        section("Unique to each company")
        print("  No secondary categories are unique to a single company.")

    if save:
        export = {
            "tickers": list(ticker_data.keys()),
            "filing_dates": {t: info["date"]
                            for t, info in ticker_data.items()},
            "category_counts": {
                t: dict(counts[t]) for t in ticker_data
            },
            "shared_themes": sorted(shared),
            "unique": {t: sorted(u) for t, u in unique_data.items()}
            if has_unique else {},
        }
        save_json(export, f"compare_{'_'.join(ticker_data.keys())}.json")

    print(f"\n{'=' * W}")


# -- timeline subcommand -----------------------------------------------------


def run_timeline(ticker, filings=2, save=False):
    """Track how a company's risk factor disclosures change over time."""
    client = get_client()

    banner("Risk Factor Timeline")
    print(f"  Ticker:  {ticker}")
    print(f"  Filings: {filings}")
    print(f"{'=' * W}")

    by_date = _fetch_risks_by_date(client, ticker)

    if not by_date:
        print("\n  No risk factors found for this ticker.")
        print(f"\n{'=' * W}")
        return

    # Take only the requested number of filings
    dates = list(by_date.keys())[:filings]

    if len(dates) == 1:
        d = dates[0]
        risks = by_date[d]
        print(f"\n  Only one filing found ({d}) with "
              f"{len(risks)} risk factors.")
        print("  Need at least 2 filings to show changes over time.")

        # Still show a summary
        primary_counts = defaultdict(int)
        for r in risks:
            if r.primary_category:
                primary_counts[r.primary_category] += 1

        section(f"Summary ({d})")
        for cat in sorted(primary_counts):
            print(f"  {cat}: {primary_counts[cat]}")
        print(f"  Total: {sum(primary_counts.values())}")

        print(f"\n{'=' * W}")
        return

    # -- Category counts table across filing dates --
    section("Category counts by filing")

    all_primaries = sorted(
        {r.primary_category for d in dates for r in by_date[d]
         if r.primary_category}
    )

    counts_by_date = {}
    for d in dates:
        counts_by_date[d] = defaultdict(int)
        for r in by_date[d]:
            if r.primary_category:
                counts_by_date[d][r.primary_category] += 1

    date_w = max(len(d) for d in dates)
    date_w = max(date_w, 6)
    cat_w = max((len(c) for c in all_primaries), default=20)
    cat_w = max(cat_w, 8)

    header = f"  {'Category':<{cat_w}}"
    for d in dates:
        header += f"  {d:>{date_w}}"
    header += f"  {'Change':>8}"
    print(f"\n{header}")
    print(f"  {'-' * cat_w}" + f"  {'-' * date_w}" * len(dates)
          + f"  {'-' * 8}")

    for cat in all_primaries:
        row = f"  {cat:<{cat_w}}"
        for d in dates:
            row += f"  {counts_by_date[d].get(cat, 0):>{date_w}}"
        # Change = newest - second newest
        newest = counts_by_date[dates[0]].get(cat, 0)
        prior = counts_by_date[dates[1]].get(cat, 0)
        delta = newest - prior
        sign = "+" if delta > 0 else ""
        row += f"  {sign}{delta:>7}" if delta != 0 else f"  {'--':>8}"
        print(row)

    # Totals
    print(f"  {'-' * cat_w}" + f"  {'-' * date_w}" * len(dates)
          + f"  {'-' * 8}")
    totals_row = f"  {'Total':<{cat_w}}"
    for d in dates:
        totals_row += f"  {sum(counts_by_date[d].values()):>{date_w}}"
    newest_total = sum(counts_by_date[dates[0]].values())
    prior_total = sum(counts_by_date[dates[1]].values())
    delta_total = newest_total - prior_total
    sign = "+" if delta_total > 0 else ""
    totals_row += (f"  {sign}{delta_total:>7}"
                   if delta_total != 0 else f"  {'--':>8}")
    print(totals_row)

    # -- Changes between consecutive filings --
    changes_export = []
    for i in range(len(dates) - 1):
        newer, older = dates[i], dates[i + 1]

        newer_sec = {
            r.secondary_category for r in by_date[newer]
            if r.secondary_category
        }
        older_sec = {
            r.secondary_category for r in by_date[older]
            if r.secondary_category
        }

        added = sorted(newer_sec - older_sec)
        removed = sorted(older_sec - newer_sec)
        unchanged = len(newer_sec & older_sec)

        section(f"Changes: {older} -> {newer}")

        if added:
            print(f"\n  Added ({len(added)}):")
            for cat in added:
                print(f"    + {cat}")

        if removed:
            print(f"\n  Removed ({len(removed)}):")
            for cat in removed:
                print(f"    - {cat}")

        if not added and not removed:
            print("\n  No secondary categories added or removed.")

        print(f"\n  Unchanged: {unchanged} secondary "
              f"categor{'y' if unchanged == 1 else 'ies'}")

        changes_export.append({
            "from": older,
            "to": newer,
            "added": added,
            "removed": removed,
            "unchanged_count": unchanged,
        })

    if save:
        export = {
            "ticker": ticker,
            "filing_dates": dates,
            "category_counts": {
                d: dict(counts_by_date[d]) for d in dates
            },
            "changes": changes_export,
        }
        save_json(export, f"timeline_{ticker}.json")

    print(f"\n{'=' * W}")


# -- CLI entry point ----------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Massive: SEC Filings & Disclosures Demo (Beta). "
            "Explore SEC filings through five REST endpoints."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # index
    idx = subparsers.add_parser(
        "index",
        help="Search the SEC EDGAR filing index",
    )
    idx.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    idx.add_argument(
        "--form-type",
        help="Filter by form type (e.g. 10-K, 8-K, 10-Q, S-1, 4)",
    )
    idx.add_argument(
        "--limit", type=int, default=10,
        help="Max results (default: 10)",
    )
    idx.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    # 10k
    tenk = subparsers.add_parser(
        "10k",
        help="Fetch 10-K section content (risk factors, business)",
    )
    tenk.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    tenk.add_argument(
        "--section", default="risk_factors",
        choices=["risk_factors", "business"],
        help="Section to fetch (default: risk_factors)",
    )
    tenk.add_argument(
        "--date",
        help="Filing date upper bound (YYYY-MM-DD, fetches on or before)",
    )
    tenk.add_argument(
        "--limit", type=int, default=1,
        help="Number of filings to return (default: 1, most recent)",
    )
    tenk.add_argument(
        "--full", action="store_true",
        help="Print full section text instead of a preview",
    )
    tenk.add_argument(
        "--save", action="store_true",
        help="Save full text to JSON in data/",
    )

    # 8k
    eightk = subparsers.add_parser(
        "8k",
        help="Fetch 8-K current report text",
    )
    eightk.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    eightk.add_argument(
        "--date",
        help="Filing date upper bound (YYYY-MM-DD, on or before)",
    )
    eightk.add_argument(
        "--limit", type=int, default=3,
        help="Max results (default: 3)",
    )
    eightk.add_argument(
        "--full", action="store_true",
        help="Print full filing text instead of a preview",
    )
    eightk.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    # risks
    risk_parser = subparsers.add_parser(
        "risks",
        help="Fetch structured risk factor disclosures",
    )
    risk_parser.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    risk_parser.add_argument(
        "--date",
        help="Filing date upper bound (YYYY-MM-DD, on or before)",
    )
    risk_parser.add_argument(
        "--limit", type=int, default=10,
        help="Max results (default: 10)",
    )
    risk_parser.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    # taxonomy
    tax = subparsers.add_parser(
        "taxonomy",
        aliases=["tax"],
        help="Browse the risk factor taxonomy",
    )
    tax.add_argument(
        "--primary",
        help="Filter by primary category name",
    )
    tax.add_argument(
        "--secondary",
        help="Filter by secondary category name",
    )
    tax.add_argument(
        "--limit", type=int, default=20,
        help="Max results (default: 20)",
    )
    tax.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    # compare
    cmp_parser = subparsers.add_parser(
        "compare",
        aliases=["cmp"],
        help="Compare risk factor profiles across companies",
    )
    cmp_parser.add_argument(
        "tickers", nargs="+",
        help="Two or more stock tickers (e.g. AAPL MSFT GOOGL)",
    )
    cmp_parser.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    # timeline
    tl_parser = subparsers.add_parser(
        "timeline",
        aliases=["tl"],
        help="Track risk factor changes across filing periods",
    )
    tl_parser.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    tl_parser.add_argument(
        "--filings", type=int, default=2,
        help="Number of filing periods to compare (default: 2)",
    )
    tl_parser.add_argument(
        "--save", action="store_true",
        help="Save results to JSON in data/",
    )

    args = parser.parse_args()

    if args.command == "index":
        run_index(
            args.ticker.upper(),
            form_type=args.form_type,
            limit=args.limit,
            save=args.save,
        )

    elif args.command == "10k":
        run_10k(
            args.ticker.upper(),
            section_name=args.section,
            filing_date=args.date,
            limit=args.limit,
            full=args.full,
            save=args.save,
        )

    elif args.command == "8k":
        run_8k(
            args.ticker.upper(),
            filing_date=args.date,
            limit=args.limit,
            full=args.full,
            save=args.save,
        )

    elif args.command == "risks":
        run_risks(
            args.ticker.upper(),
            filing_date=args.date,
            limit=args.limit,
            save=args.save,
        )

    elif args.command in ("taxonomy", "tax"):
        run_taxonomy(
            primary=args.primary,
            secondary=args.secondary,
            limit=args.limit,
            save=args.save,
        )

    elif args.command in ("compare", "cmp"):
        if len(args.tickers) < 2:
            parser.error("compare requires at least 2 tickers")
        run_compare(
            [t.upper() for t in args.tickers],
            save=args.save,
        )

    elif args.command in ("timeline", "tl"):
        run_timeline(
            args.ticker.upper(),
            filings=args.filings,
            save=args.save,
        )


if __name__ == "__main__":
    main()
