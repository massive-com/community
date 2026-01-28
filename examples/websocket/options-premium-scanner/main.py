#!/usr/bin/env python3
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from massive import WebSocketClient
from massive.websocket.models import Market

API_KEY = "oex6s6bofvpNKHR47X5pz_zApTrFSp7Q"

# ========== CHANGE THIS VALUE TO SET MINIMUM PREMIUM FILTER ==========
MIN_PREMIUM_USD = 100_000  # Only show trades with premium >= this amount
# =====================================================================
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
                pl("Premium", f"${prem:,.2f}"),
                pl("Symbol", root),
                pl("Type", opt_type),
                pl("Strike", f"${strike:,.2f}" if strike is not None else "N/A"),
                pl("Price", f"${price:.2f}"),
                pl("Size", f"{size} contracts"),
                pl("Exchange", exchange or "N/A"),
                pl("Conditions", conditions or "N/A"),
                pl("Contract", sym),
                pl("Timestamp", et(ts)),
                "",
                "------------------------",
            ]
        ),
        flush=True,
    )


def main():
    c = WebSocketClient(api_key=API_KEY, market=Market.Options)
    c.subscribe("T.*")
    print(f"[info] connecting to options trade stream (T.*) — filter: ≥ ${MIN_PREMIUM_USD:,.0f} premium", flush=True)

    def handler(msgs):
        for m in msgs:
            price, size = float(m.price), int(m.size)
            prem = price * size * 100
            if prem < MIN_PREMIUM_USD:
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
