from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from massive import Massive  # type: ignore
except ImportError:  # pragma: no cover
    from massive import RESTClient as Massive  # type: ignore


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    ts: str | None = None


def get_client(api_key: str) -> Massive:
    return Massive(api_key=api_key)


def fetch_last_prices(client: Massive, tickers: Iterable[str]) -> dict[str, Quote]:
    """
    Fetch the latest available prices for a list of equities tickers.

    Notes:
    - This returns a simple app-friendly shape: { "AAPL": Quote(...), ... }.
    - Keep network calls out of unit tests; this module is intended for runtime use.
    """
    tickers_list = [t.strip().upper() for t in tickers if t and t.strip()]
    if not tickers_list:
        return {}

    out: dict[str, Quote] = {}

    for ticker in tickers_list:
        row = client.get_last_quote(ticker)

        bid = getattr(row, "bid_price", None)
        ask = getattr(row, "ask_price", None)
        if bid is not None and ask is not None:
            price = (float(bid) + float(ask)) / 2.0
        elif bid is not None:
            price = float(bid)
        elif ask is not None:
            price = float(ask)
        else:
            continue

        ts = (
            getattr(row, "sip_timestamp", None)
            or getattr(row, "participant_timestamp", None)
            or getattr(row, "trf_timestamp", None)
        )

        out[ticker] = Quote(ticker=ticker, price=price, ts=None if ts is None else str(ts))

    return out
