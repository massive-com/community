#!/usr/bin/env python3
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from massive import WebSocketClient
from massive.websocket.models import Market

API_KEY = "oex6s6bofvpNKHR47X5pz_zApTrFSp7Q"
RE_FULL = re.compile(r"^([A-Z0-9]+?)(\d{6})([CP])(\d{8})$")


def parse_contract(sym: str):
    s = sym.upper()[2:] if sym.upper().startswith("O:") else sym.upper()
    m = RE_FULL.match(s)
    if not m:
        return s, "N/A", None
    root, _, cp, k = m.groups()
    root = "SPX" if root == "SPXW" else root
    opt_type = "Call" if cp == "C" else "Put"
    strike = int(k) / 1000.0
    return root, opt_type, strike


def et(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("America/New_York")).strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )


def show_trade(sym: str, price: float, size: int, ts: int, exchange=None, conditions=None):
    root, opt_type, strike = parse_contract(sym)
    prem = price * size * 100
    pl = lambda L, V, w=12: f"{(L + ':'):<{w}} {V}"
    print(
        "\n".join(
            [
                "",
                pl("Symbol", root),
                pl("Contract", sym),
                pl("Type", opt_type),
                pl("Price", f"${price:.2f}"),
                pl("Size", f"{size} contracts"),
                pl("Premium", f"${prem:,.2f}"),
                pl("Strike", f"${strike:,.2f}" if strike is not None else "N/A"),
                pl("Exchange", exchange or "N/A"),
                pl("Timestamp", et(ts)),
                pl("Conditions", conditions or "N/A"),
                "",
                "------------------------",
            ]
        ),
        flush=True,
    )


def main():
    raw = input("Minimum Premium in USD (blank = show all): ").strip()
    min_prem = float(raw) if raw else None

    c = WebSocketClient(API_KEY, market=Market.Options)
    c.subscribe("T.*")
    f = "ALL premiums" if min_prem is None else f"≥ ${min_prem:,.0f} premium"
    print(f"[info] connecting to options trade stream (T.*) — filter: {f}", flush=True)

    def handler(msgs):
        for m in msgs:
            price, size = float(m.price), int(m.size)
            prem = price * size * 100
            if min_prem is not None and prem < min_prem:
                continue
            show_trade(
                m.symbol,
                price,
                size,
                int(m.timestamp),
                getattr(m, "exchange", None),
                getattr(m, "conditions", None),
            )

    try:
        c.run(handler)
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


if __name__ == "__main__":
    main()
