from __future__ import annotations

import os
from dataclasses import asdict
from typing import Iterable

import streamlit as st

from pdt_console.massive_prices import fetch_last_prices, get_client
from pdt_console.simulator import AccountState, Action, ActionType, simulate_day


DISCLAIMER = (
    "Educational simulation only. This dashboard is not a broker margin engine, "
    "does not model Reg T, portfolio margin, house requirements, or broker-specific rules, "
    "and should not be used to make trading or risk decisions."
)


def _uniq_upper(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        t = raw.strip().upper()
        if not t or t in seen:
            continue
        out.append(t)
        seen.add(t)
    return out


def _scenario_actions(scenario_key: str) -> list[Action]:
    # Prices for BUY/SELL are filled at runtime from Massive.
    if scenario_key == "none":
        return []
    if scenario_key == "buy_1":
        return [Action(type=ActionType.BUY, ticker="AAPL", qty=10)]
    if scenario_key == "buy_sell":
        return [
            Action(type=ActionType.BUY, ticker="AAPL", qty=50),
            Action(type=ActionType.SELL, ticker="AAPL", qty=25),
            Action(type=ActionType.BUY, ticker="MSFT", qty=15),
        ]
    if scenario_key == "scale_in":
        return [
            Action(type=ActionType.BUY, ticker="NVDA", qty=10),
            Action(type=ActionType.BUY, ticker="NVDA", qty=10),
            Action(type=ActionType.BUY, ticker="NVDA", qty=10),
        ]
    if scenario_key == "withdraw_then_trade":
        return [
            Action(type=ActionType.WITHDRAW_CASH, amount=2_000.0),
            Action(type=ActionType.BUY, ticker="AAPL", qty=20),
            Action(type=ActionType.BUY, ticker="TSLA", qty=5),
        ]
    return []


def _fill_live_prices(actions: list[Action], last_prices: dict[str, float]) -> list[Action]:
    filled: list[Action] = []
    for a in actions:
        if a.type in (ActionType.BUY, ActionType.SELL):
            ticker = (a.ticker or "").strip().upper()
            px = float(last_prices.get(ticker, 0.0))
            filled.append(Action(type=a.type, ticker=ticker, qty=a.qty, price=px))
        else:
            filled.append(a)
    return filled


def _render_before_vs_now() -> None:
    st.subheader("Before vs now: PDT vs intraday deficits")
    st.markdown(
        "- **Before (PDT lens)**: You were typically thinking in terms of PDT status and settlement "
        "constraints, with risk framed around day trading limits.\n"
        "- **Now (intraday deficit lens)**: The operational question becomes whether your account "
        "can support your positions as prices move during the day. This dashboard models that as an "
        "**intraday margin deficit** derived from a simplified maintenance requirement.\n"
        "- **Key outputs**: The simulator tracks the **minimum IML** reached today, and the "
        "**maximum intraday margin deficit** implied by that minimum.\n"
    )


def main() -> None:
    st.set_page_config(
        page_title="Intraday Risk Console (Equities)",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Intraday Risk Console (Equities only)")
    st.warning(DISCLAIMER)

    _render_before_vs_now()

    with st.sidebar:
        st.header("Live data (Massive)")
        default_key = os.getenv("MASSIVE_API_KEY", "")
        api_key = st.text_input("Massive API key", type="password", value=default_key)
        st.caption("Prices are polled from Massive using `pdt_console.massive_prices`.")

        st.divider()
        st.header("Auto-refresh")
        enable_refresh = st.toggle("Enable auto-refresh", value=True)
        refresh_s = st.select_slider(
            "Refresh interval (seconds)",
            options=[0, 5, 10, 15, 30, 60],
            value=10,
            help="Uses Streamlit's `st.autorefresh` when available.",
        )

        st.divider()
        st.header("Account")
        starting_cash = st.number_input("Starting cash ($)", min_value=0.0, value=25_000.0, step=500.0)
        maintenance_haircut = st.slider(
            "Maintenance haircut (educational proxy)",
            min_value=0.10,
            max_value=0.60,
            value=0.30,
            step=0.05,
        )
        positions_raw = st.text_area(
            "Starting positions (ticker=qty, one per line)",
            value="AAPL=50\nMSFT=20",
            help="Equities only. Example: AAPL=100",
        )

        st.divider()
        st.header("Scenario")
        scenario = st.selectbox(
            "Choose a scenario",
            options=[
                ("none", "No actions (mark-only)"),
                ("buy_1", "Buy AAPL (small)"),
                ("buy_sell", "Buy/sell mix across tickers"),
                ("scale_in", "Scale into NVDA in 3 steps"),
                ("withdraw_then_trade", "Withdraw cash, then trade"),
            ],
            format_func=lambda x: x[1],
        )[0]

    if enable_refresh and int(refresh_s) > 0:
        autorefresh = getattr(st, "autorefresh", None)
        if callable(autorefresh):
            autorefresh(interval=int(refresh_s) * 1000, key="intraday-risk-refresh")
        else:
            st.info(
                "Auto-refresh is unavailable in this Streamlit version. "
                "Upgrade Streamlit to use `st.autorefresh`, or refresh the page manually."
            )

    # Parse positions
    positions: dict[str, int] = {}
    for line in (positions_raw or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        t, q = raw.split("=", 1)
        ticker = t.strip().upper()
        try:
            qty = int(q.strip())
        except ValueError:
            continue
        if ticker:
            positions[ticker] = qty

    scenario_actions = _scenario_actions(scenario)
    scenario_tickers = _uniq_upper(
        [t for t in positions.keys()]
        + [a.ticker for a in scenario_actions if a.ticker]
    )

    col_left, col_right = st.columns([0.55, 0.45], gap="large")

    with col_left:
        st.subheader("Scenario actions")
        if not scenario_actions:
            st.caption("No actions selected. The simulator will compute IML from the current mark.")
        else:
            st.dataframe(
                [
                    {**asdict(a), "ticker": (a.ticker or "").upper()}
                    for a in scenario_actions
                ],
                use_container_width=True,
                hide_index=True,
            )

    last_quotes = None
    last_prices: dict[str, float] = {}
    prices_error: str | None = None

    if api_key and scenario_tickers:
        try:
            client = get_client(api_key)
            quotes = fetch_last_prices(client, scenario_tickers)
            last_quotes = quotes
            last_prices = {t: q.price for t, q in quotes.items()}
        except Exception as e:  # noqa: BLE001
            prices_error = str(e) or "Unknown error"
    elif not api_key:
        prices_error = "Missing Massive API key."

    with col_right:
        st.subheader("Live market values (polled)")
        if scenario_tickers and prices_error:
            st.error(
                "We could not fetch live prices from Massive. "
                "Check your API key and try again, or wait for the next refresh.",
            )
            with st.expander("Error details"):
                st.code(prices_error)
        elif not scenario_tickers:
            st.caption("Add positions or select a scenario with tickers to fetch live prices.")
        else:
            rows = []
            assert last_quotes is not None
            for t in scenario_tickers:
                q = last_quotes.get(t)
                if not q:
                    continue
                rows.append({"Ticker": t, "Last price": q.price, "Timestamp": q.ts})
            st.dataframe(rows, use_container_width=True, hide_index=True)

    # Simulate using live prices for BUY/SELL steps when present.
    state = AccountState(
        starting_cash=float(starting_cash),
        positions=positions,
        maintenance_haircut=float(maintenance_haircut),
    )

    ready = (not scenario_tickers) or (not prices_error and bool(last_prices))

    st.divider()
    st.subheader("Intraday risk simulation")
    if not ready:
        st.caption("Simulation waiting on live prices.")
        return

    filled_actions = _fill_live_prices(scenario_actions, last_prices)
    result = simulate_day(state, filled_actions)

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Min IML (today)", f"${result.min_iml:,.2f}")
    kpi2.metric("Max intraday margin deficit (today)", f"${result.max_intraday_margin_deficit:,.2f}")
    kpi3.metric("Actions evaluated", str(len(filled_actions) if filled_actions else 0))

    st.caption(
        "IML is an educational proxy for equity buffer above a simplified maintenance requirement. "
        "Negative IML implies an intraday deficit in this simplified model."
    )

    st.line_chart(
        {"IML": result.iml_after_each_action},
        use_container_width=True,
        height=220,
    )

    with st.expander("Inputs used"):
        st.json(
            {
                "account_state": {
                    "starting_cash": state.starting_cash,
                    "positions": dict(state.positions),
                    "maintenance_haircut": state.maintenance_haircut,
                },
                "actions": [asdict(a) for a in filled_actions],
            }
        )


if __name__ == "__main__":
    main()

