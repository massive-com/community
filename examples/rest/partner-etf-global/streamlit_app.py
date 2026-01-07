"""ETF Health Pulse - Streamlit demo for Massive + ETF Global® partnership.

This single-file app showcases how to layer analytics, momentum detection,
and storytelling on top of Massive's ETF Global® endpoints.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv
from massive import RESTClient
from massive.exceptions import BadResponse


load_dotenv()


def _configure_logger() -> logging.Logger:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("etf_health_pulse")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


LOGGER = _configure_logger()


def _records_from_models(items: Iterable[Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in items:
        data = {
            key: value
            for key, value in vars(item).items()
            if not key.startswith("_")
        }
        records.append(data)
    return records


def _parse_bad_response(exc: BadResponse) -> Dict[str, Any]:
    try:
        return json.loads(str(exc))
    except Exception:
        return {}


def _resolve_api_key() -> Optional[str]:
    try:
        value = st.secrets["MASSIVE_API_KEY"]
        if value:
            return value
    except (StreamlitSecretNotFoundError, KeyError):
        LOGGER.debug("MASSIVE_API_KEY not found in Streamlit secrets")
    return os.getenv("MASSIVE_API_KEY")


@st.cache_resource(show_spinner=False)
def _client(api_key: str) -> RESTClient:
    LOGGER.info("Initializing RESTClient")
    return RESTClient(api_key=api_key, pagination=True)


@st.cache_resource(show_spinner=False)
def _client_no_pagination(api_key: str) -> RESTClient:
    LOGGER.info("Initializing RESTClient (no pagination)")
    return RESTClient(api_key=api_key, pagination=False)


@st.cache_data(ttl=600, show_spinner=False)
def get_latest_available_date(api_key: str, ticker: str) -> Optional[str]:
    """Get the most recent effective_date with available constituents data."""
    try:
        # Use no-pagination client with small limit for speed
        data = list(
            _client_no_pagination(api_key).get_etf_global_constituents(
                composite_ticker=ticker, limit=5, sort="processed_date.desc"
            )
        )
        if data:
            dates = []
            for item in data:
                eff_date = getattr(item, "effective_date", None)
                if eff_date:
                    dates.append(str(eff_date))
            if dates:
                # Sort dates as strings (YYYY-MM-DD format)
                dates.sort(reverse=True)
                return dates[0]
    except Exception as exc:
        LOGGER.debug(f"Could not fetch latest date for {ticker}: {exc}")
    return None


@st.cache_data(ttl=600, show_spinner=False)
def load_constituents_df(
    api_key: str, ticker: str, effective_date: Optional[str]
) -> pd.DataFrame:
    start_time = time.time()
    LOGGER.info(
        "Fetching constituents",
        extra={"ticker": ticker, "effective_date": effective_date},
    )
    kwargs: Dict[str, Any] = {"composite_ticker": ticker, "limit": 100}
    if effective_date:
        kwargs["effective_date"] = effective_date

    api_start = time.time()
    try:
        data = list(_client(api_key).get_etf_global_constituents(**kwargs))
    except Exception as exc:  # pragma: no cover - streamlit only
        LOGGER.exception("Failed to load constituents")
        raise RuntimeError("Unable to load constituents") from exc
    api_time = time.time() - api_start

    LOGGER.info(f"API call completed in {api_time:.2f}s, retrieved {len(data)} records")

    df_start = time.time()
    df = pd.DataFrame(_records_from_models(data))
    if df.empty:
        LOGGER.info(f"DataFrame processing completed in {time.time() - df_start:.2f}s (empty result)")
        return df

    # Convert weight to numeric and sort by weight descending first
    df["weight"] = pd.to_numeric(df.get("weight"), errors="coerce")
    df["weight_pct"] = df["weight"] * 100
    df["market_value"] = pd.to_numeric(df.get("market_value"), errors="coerce")
    
    # Deduplicate by constituent_ticker, keeping the row with highest weight
    if "constituent_ticker" in df.columns:
        duplicates_before = len(df)
        df = df.sort_values("weight", ascending=False).drop_duplicates(
            subset="constituent_ticker", keep="first"
        )
        if len(df) < duplicates_before:
            LOGGER.info(f"Deduplicated {duplicates_before - len(df)} duplicate constituent entries")
    
    df.sort_values("weight", ascending=False, inplace=True)

    # Enforce limit by keeping only top weighted holdings after sorting
    if len(df) > 100:
        df = df.head(100)
        LOGGER.info(f"Constituents sorted and limited to top 100 holdings by weight")

    total_time = time.time() - start_time
    LOGGER.info(f"Constituents loading completed in {total_time:.2f}s (API: {api_time:.2f}s, processing: {time.time() - df_start:.2f}s, final records: {len(df)})")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_fund_flows_df(
    api_key: str, ticker: str, start_date: str, end_date: str
) -> pd.DataFrame:
    start_time = time.time()
    LOGGER.info(
        "Fetching fund flows",
        extra={"ticker": ticker, "start": start_date, "end": end_date},
    )
    kwargs: Dict[str, Any] = {
        "composite_ticker": ticker,
        "effective_date_gte": start_date,
        "effective_date_lte": end_date,
        "limit": 100,
        "sort": "processed_date.desc",
    }

    api_start = time.time()
    data = list(_client(api_key).get_etf_global_fund_flows(**kwargs))
    api_time = time.time() - api_start

    LOGGER.info(f"Fund flows API call completed in {api_time:.2f}s, retrieved {len(data)} records")
    df_start = time.time()
    df = pd.DataFrame(_records_from_models(data))
    if df.empty:
        LOGGER.info(f"Fund flows DataFrame processing completed in {time.time() - df_start:.2f}s (empty result)")
        return df

    # Sort by date descending first to get most recent, then limit
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    df.sort_values("effective_date", ascending=False, inplace=True)

    # Enforce limit by keeping only the most recent flows
    if len(df) > 100:
        df = df.head(100)
        LOGGER.info(f"Fund flows sorted and limited to 100 most recent records")
    
    # Sort ascending for time series display
    df.sort_values("effective_date", ascending=True, inplace=True)
    df["fund_flow"] = pd.to_numeric(df.get("fund_flow"), errors="coerce")
    df["nav"] = pd.to_numeric(df.get("nav"), errors="coerce")
    df["rolling_mean"] = df["fund_flow"].rolling(window=5, min_periods=3).mean()
    df["rolling_std"] = df["fund_flow"].rolling(window=5, min_periods=3).std()
    df["z_score"] = (df["fund_flow"] - df["rolling_mean"]) / df["rolling_std"]
    df["z_score"] = df["z_score"].replace([np.inf, -np.inf], np.nan)

    total_time = time.time() - start_time
    LOGGER.info(f"Fund flows loading completed in {total_time:.2f}s (API: {api_time:.2f}s, processing: {time.time() - df_start:.2f}s, final records: {len(df)})")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_analytics_df(api_key: str, ticker: str, limit: int = 1) -> pd.DataFrame:
    start_time = time.time()
    LOGGER.info("Fetching analytics", extra={"ticker": ticker})

    api_start = time.time()
    try:
        # Fetch more records to ensure we get the latest after sorting
        fetch_limit = max(limit, 20)
        data = list(
            _client_no_pagination(api_key).get_etf_global_analytics(
                composite_ticker=ticker, limit=fetch_limit, sort="processed_date.desc"
            )
        )
        api_time = time.time() - api_start
        LOGGER.info(f"Analytics API call completed in {api_time:.2f}s, retrieved {len(data)} records")
    except Exception as exc:
        api_time = time.time() - api_start
        LOGGER.warning(f"Analytics API call failed after {api_time:.2f}s: {exc}")
        return pd.DataFrame()

    df_start = time.time()
    df = pd.DataFrame(_records_from_models(data))
    if df.empty:
        LOGGER.info(f"Analytics DataFrame processing completed in {time.time() - df_start:.2f}s (empty result)")
        return df

    # Sort by effective_date descending to get most recent first
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    df.sort_values("effective_date", ascending=False, inplace=True)

    # Take only the most recent records after sorting
    if len(df) > limit:
        df = df.head(limit)
        LOGGER.info(f"Analytics sorted and limited to {limit} most recent records")

    total_time = time.time() - start_time
    LOGGER.info(f"Analytics loading completed in {total_time:.2f}s (API: {api_time:.2f}s, processing: {time.time() - df_start:.2f}s, final records: {len(df)})")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_profile_df(api_key: str, ticker: str) -> pd.DataFrame:
    start_time = time.time()
    LOGGER.info("Fetching profiles", extra={"ticker": ticker})

    api_start = time.time()
    try:
        # Fetch multiple records to ensure we get the latest after sorting
        data = list(
            _client_no_pagination(api_key).get_etf_global_profiles(
                composite_ticker=ticker, limit=10, sort="processed_date.desc"
            )
        )
        api_time = time.time() - api_start

        LOGGER.info(f"Profiles API call completed in {api_time:.2f}s, retrieved {len(data)} records")
    except Exception as exc:
        api_time = time.time() - api_start
        LOGGER.warning(f"Profiles API call failed after {api_time:.2f}s: {exc}")
        return pd.DataFrame()

    df_start = time.time()
    df = pd.DataFrame(_records_from_models(data))
    if df.empty:
        LOGGER.info(f"Profiles DataFrame processing completed in {time.time() - df_start:.2f}s (empty result)")
        return df

    # Sort by effective_date or processed_date descending to get most recent first
    date_col = "effective_date" if "effective_date" in df.columns else "processed_date"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        df.sort_values(date_col, ascending=False, inplace=True)
        LOGGER.info(f"Profiles sorted by {date_col} descending")

    # Take only the most recent record
    df = df.head(1)

    total_time = time.time() - start_time
    LOGGER.info(f"Profiles loading completed in {total_time:.2f}s (API: {api_time:.2f}s, processing: {time.time() - df_start:.2f}s, final records: {len(df)})")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_taxonomy_df(api_key: str, ticker: str) -> pd.DataFrame:
    start_time = time.time()
    LOGGER.info("Fetching taxonomy", extra={"ticker": ticker})

    api_start = time.time()
    try:
        # Fetch multiple records to ensure we get the latest after sorting
        data = list(
            _client_no_pagination(api_key).get_etf_global_taxonomies(
                composite_ticker=ticker, limit=10, sort="processed_date.desc"
            )
        )
        api_time = time.time() - api_start

        LOGGER.info(f"Taxonomy API call completed in {api_time:.2f}s, retrieved {len(data)} records")
    except Exception as exc:
        api_time = time.time() - api_start
        LOGGER.warning(f"Taxonomy API call failed after {api_time:.2f}s: {exc}")
        return pd.DataFrame()

    df_start = time.time()
    df = pd.DataFrame(_records_from_models(data))
    if df.empty:
        LOGGER.info(f"Taxonomy DataFrame processing completed in {time.time() - df_start:.2f}s (empty result)")
        return df

    # Sort by effective_date or processed_date descending to get most recent first
    date_col = "effective_date" if "effective_date" in df.columns else "processed_date"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        df.sort_values(date_col, ascending=False, inplace=True)
        LOGGER.info(f"Taxonomy sorted by {date_col} descending")

    # Take only the most recent record
    df = df.head(1)

    total_time = time.time() - start_time
    LOGGER.info(f"Taxonomy loading completed in {total_time:.2f}s (API: {api_time:.2f}s, processing: {time.time() - df_start:.2f}s, final records: {len(df)})")
    return df


def _classification_from_hhi(hhi: float) -> str:
    if hhi < 0.1:
        return "Low concentration"
    if hhi < 0.18:
        return "Moderate concentration"
    return "High concentration"


def derive_highlights(
    constituents: pd.DataFrame,
    flows: pd.DataFrame,
    analytics: pd.DataFrame,
    profile: pd.DataFrame,
) -> List[str]:
    highlights: List[str] = []

    if not constituents.empty and "weight" in constituents:
        weights = constituents["weight"].dropna()
        if not weights.empty:
            hhi = float((weights ** 2).sum())
            top_row = constituents.iloc[0]
            top_weight = top_row.get("weight_pct")
            top_weight_str = (
                f"{top_weight:.2f}%"
                if pd.notna(top_weight)
                else "weight unavailable"
            )
            highlights.append(
                f"{_classification_from_hhi(hhi)}: HHI {hhi:.3f} "
                f"with top holding {top_row.get('constituent_ticker', '—')} "
                f"at {top_weight_str}."
            )

    if not flows.empty:
        recent = flows.tail(3)
        net = recent["fund_flow"].sum()
        z_score = recent["z_score"].iloc[-1] if not recent["z_score"].isna().all() else np.nan
        if net > 0:
            highlights.append(
                f"Inflow momentum: ${net:,.0f} over the last three sessions "
                f"(z-score {z_score:.2f})." if not np.isnan(z_score) else
                f"Inflow momentum: ${net:,.0f} over the last three sessions."
            )
        elif net < 0:
            highlights.append(
                f"Outflows dominating: ${net:,.0f} over the last three sessions "
                f"(z-score {z_score:.2f})." if not np.isnan(z_score) else
                f"Outflows dominating: ${net:,.0f} over the last three sessions."
            )

    if not analytics.empty:
        latest = analytics.iloc[0]
        reward = latest.get("reward_score")
        risk = latest.get("risk_total_score")
        quant_grade = latest.get("quant_grade")
        if reward and reward >= 80:
            highlights.append(f"Reward score {reward:.1f} flags the ETF as top quartile.")
        if risk and risk <= 40:
            highlights.append(f"Risk score {risk:.1f} suggests below-average volatility.")
        if quant_grade:
            highlights.append(f"Quant grade: {quant_grade}.")

    if not profile.empty:
        latest_profile = profile.iloc[0]
        expense = latest_profile.get("net_expenses")
        if expense:
            highlights.append(f"Net expense ratio: {expense * 100:.2f}%.")
        sector_exposure = latest_profile.get("sector_exposure")
        if isinstance(sector_exposure, dict) and sector_exposure:
            top_sector, pct = max(sector_exposure.items(), key=lambda x: x[1])
            highlights.append(
                f"Sector tilt: {top_sector} at {pct * 100:.1f}% of assets."
            )

    return highlights or ["No insights available for the selected parameters."]


def render_constituents_tab(df: pd.DataFrame):
    st.subheader("Exposure Concentration Watch")
    if df.empty:
        st.info("No constituent data returned for this date.")
        return
    hhi = float((df["weight"].dropna() ** 2).sum())
    st.metric(
        label="Holdings Concentration (HHI)",
        value=f"{hhi:.3f}",
        delta=_classification_from_hhi(hhi),
    )
    top10 = df.nlargest(10, "weight_pct")[["constituent_ticker", "weight_pct"]]
    fig = px.bar(
        top10,
        x="weight_pct",
        y="constituent_ticker",
        orientation="h",
        labels={"weight_pct": "Weight (%)", "constituent_ticker": "Ticker"},
    )
    fig.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width="stretch")
    st.write(f"**Top Holdings (showing {min(25, len(df))} of {len(df)} total)**")
    formatted = (
        df[["constituent_ticker", "constituent_name", "weight_pct", "market_value"]]
        .assign(
            weight_pct=lambda x: x["weight_pct"].apply(
                lambda v: f"{v:.2f}%" if pd.notna(v) else "—"
            ),
            market_value=lambda x: x["market_value"].apply(
                lambda v: f"${v:,.0f}" if pd.notna(v) else "—"
            ),
        )
        .head(25)
    )
    st.dataframe(formatted, width="stretch")


def render_flows_tab(df: pd.DataFrame):
    st.subheader("Fund Flow Momentum Detector")
    if df.empty:
        st.info("No fund flows found for the selected window.")
        return
    flow_fig = px.bar(
        df,
        x="effective_date",
        y="fund_flow",
        labels={"fund_flow": "Daily Net Flow (USD)", "effective_date": "Date"},
    )
    flow_fig.update_traces(marker_color=np.where(df["fund_flow"] >= 0, "#16a34a", "#dc2626"))
    nav_fig = px.line(
        df,
        x="effective_date",
        y="nav",
        labels={"nav": "NAV", "effective_date": "Date"},
    )
    st.plotly_chart(flow_fig, width="stretch")
    st.plotly_chart(nav_fig, width="stretch")
    st.write(f"**Fund Flow Details ({len(df)} records)**")
    st.dataframe(
        df[["effective_date", "fund_flow", "nav", "z_score"]]
        .assign(
            effective_date=lambda x: x["effective_date"].dt.strftime("%Y-%m-%d"),
            fund_flow=lambda x: x["fund_flow"].map(lambda v: f"${v:,.0f}"),
            nav=lambda x: x["nav"].map(lambda v: f"${v:,.2f}"),
            z_score=lambda x: x["z_score"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—"),
        ),
        width="stretch"
    )


def render_analytics_tab(df: pd.DataFrame):
    st.subheader("Risk / Reward Scorecard")
    if df.empty:
        st.info("Analytics data not available yet for this ticker.")
        return
    latest = df.iloc[0]
    cols = st.columns(3)
    def fmt(val: Any) -> str:
        try:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return "—"
            return f"{float(val):.1f}"
        except Exception:
            return "—"

    cols[0].metric("Risk Score", fmt(latest.get("risk_total_score")))
    cols[1].metric("Reward Score", fmt(latest.get("reward_score")))
    cols[2].metric("Quant Score", fmt(latest.get("quant_total_score")))
    eff_date = latest.get("effective_date")
    eff_date_str = (
        eff_date.strftime("%Y-%m-%d")
        if isinstance(eff_date, pd.Timestamp) and not pd.isna(eff_date)
        else "N/A"
    )
    st.caption(f"Quant Grade: {latest.get('quant_grade', 'N/A')} on {eff_date_str}")
    radar_fields = {
        "Risk - Liquidity": latest.get("risk_liquidity"),
        "Risk - Volatility": latest.get("risk_volatility"),
        "Risk - Country": latest.get("risk_country"),
        "Reward": latest.get("reward_score"),
        "Quant Tech": latest.get("quant_composite_technical"),
        "Quant Sentiment": latest.get("quant_composite_sentiment"),
    }
    melted = pd.DataFrame(
        [{"Dimension": k, "Score": v} for k, v in radar_fields.items() if v is not None]
    )
    if melted.empty:
        st.info("Additional factor-level details not available.")
    else:
        fig = px.line_polar(melted, r="Score", theta="Dimension", line_close=True)
        fig.update_traces(fill="toself")
        st.plotly_chart(fig, width="stretch")
    
    st.write("**Latest Analytics Record**")
    st.dataframe(df)


def render_profile_tab(profile: pd.DataFrame, taxonomy: pd.DataFrame):
    st.subheader("Profile & Taxonomy Context")
    if profile.empty and taxonomy.empty:
        st.info("Profile and taxonomy data not returned. Check entitlements.")
        return
    if not profile.empty:
        latest = profile.iloc[0]
        cols = st.columns(4)
        cols[0].metric("AUM", f"${(latest.get('aum') or 0):,.0f}")
        expense_ratio = latest.get("net_expenses") or 0
        cols[1].metric("Net Expense Ratio", f"{expense_ratio * 100:.2f}%")
        cols[2].metric("Holdings", f"{(latest.get('num_holdings') or 0):,.0f}")
        cols[3].metric(
            "Avg. Volume", f"{(latest.get('avg_daily_trading_volume') or 0):,.0f}"
        )
        sector_exposure = latest.get("sector_exposure") or {}
        if sector_exposure:
            sector_df = pd.DataFrame(
                {"sector": list(sector_exposure.keys()), "weight": list(sector_exposure.values())}
            )
            fig = px.pie(
                sector_df,
                values="weight",
                names="sector",
                title="Sector Exposure",
            )
            st.plotly_chart(fig, width="stretch")
    if not taxonomy.empty:
        taxonomy_fields = taxonomy.iloc[0][
            [
                "asset_class",
                "focus",
                "weighting_methodology",
                "leverage_style",
                "rebalance_frequency",
                "management_style",
                "primary_benchmark",
            ]
        ].dropna()
        st.write("**Strategy At A Glance**")
        st.json(taxonomy_fields.to_dict())
    if not profile.empty:
        st.write("**Raw Profile Payload**")
        st.json(profile.iloc[0].to_dict())


def main():
    st.set_page_config(
        page_title="ETF Health Pulse",
        page_icon="📊",
        layout="wide",
    )
    st.title("ETF Health Pulse")
    st.caption(
        "Powered by Massive.com v2.0.2 client • ETF Global® partnership data "
        "(/etf-global/v1 endpoints)."
    )

    api_key = _resolve_api_key()
    if not api_key:
        st.error(
            "MASSIVE_API_KEY is missing. Add it to `.env` or Streamlit secrets "
            "before using the dashboard."
        )
        st.stop()

    with st.sidebar:
        st.header("Controls")
        ticker = st.text_input("Composite ticker", value="SPY").strip().upper()
        
        # Initialize session state
        if "latest_date_cache" not in st.session_state:
            st.session_state.latest_date_cache = {}
        if "date_note_cache" not in st.session_state:
            st.session_state.date_note_cache = {}
        if "last_ticker" not in st.session_state:
            st.session_state.last_ticker = None
        
        # Determine default date
        default_date = date.today() - timedelta(days=5)
        date_note = None
        
        # Check if ticker changed
        ticker_changed = ticker and ticker != st.session_state.last_ticker
        
        if ticker_changed:
            st.session_state.last_ticker = ticker
            # Fetch latest date for new ticker (cached, so fast on subsequent renders)
            if ticker not in st.session_state.latest_date_cache:
                try:
                    latest_date_str = get_latest_available_date(api_key, ticker)
                    if latest_date_str:
                        latest_date = pd.to_datetime(latest_date_str).date()
                        default_date = min(latest_date, date.today())
                        st.session_state.latest_date_cache[ticker] = default_date
                        st.session_state.date_note_cache[ticker] = f"Most recent available: {latest_date_str}"
                    else:
                        st.session_state.latest_date_cache[ticker] = default_date
                        st.session_state.date_note_cache[ticker] = None
                except Exception as exc:
                    LOGGER.warning(f"Could not fetch latest date for {ticker}: {exc}")
                    st.session_state.latest_date_cache[ticker] = default_date
                    st.session_state.date_note_cache[ticker] = None
            else:
                default_date = st.session_state.latest_date_cache[ticker]
                date_note = st.session_state.date_note_cache.get(ticker)
        elif ticker and ticker in st.session_state.latest_date_cache:
            default_date = st.session_state.latest_date_cache[ticker]
            date_note = st.session_state.date_note_cache.get(ticker)
        
        # Use ticker in key so widget resets when ticker changes
        holdings_date = st.date_input(
            "Holdings effective date",
            value=default_date,
            max_value=date.today(),
            key=f"holdings_date_{ticker}" if ticker else "holdings_date_default",
        )
        
        if date_note:
            st.caption(f"ℹ️ {date_note}")
        st.caption(
            "**Note:** ETF holdings data typically has a 1-2 business day processing delay. "
            "Today's data may not be available until later in the day or the next business day."
        )
        
        lookback_days = st.slider(
            "Fund flow lookback (days)",
            min_value=7,
            max_value=90,
            value=30,
            step=1,
        )
        start_window = date.today() - timedelta(days=lookback_days)
        st.caption("Adjust filters to refresh the analysis automatically.")

    if not ticker:
        st.info("Enter a ticker to begin.")
        st.stop()

    def fetch_dataset(
        label: str, fetcher: Callable[[], pd.DataFrame]
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        try:
            return fetcher(), None
        except BadResponse as exc:  # pragma: no cover - streamlit only
            LOGGER.warning("Not entitled to %s data: %s", label, exc)
            parsed = _parse_bad_response(exc)
            if parsed.get("status") == "NOT_AUTHORIZED":
                return (
                    pd.DataFrame(),
                    f"{label.title()} data requires ETF Global® add-ons on your Massive account. "
                    "See https://massive.com/partners/etf-global for upgrade options.",
                )
            return (
                pd.DataFrame(),
                parsed.get("message") or f"Unable to load {label} data.",
            )
        except Exception as exc:  # pragma: no cover - streamlit only
            LOGGER.exception("Failed to load %s data", label)
            return (
                pd.DataFrame(),
                f"Unable to load {label} data ({exc}). Please retry in a moment.",
            )
    overall_start = time.time()
    with st.spinner("Fetching Massive ETF Global® data..."):
        constituents_df, constituents_err = fetch_dataset(
            "constituents",
            lambda: load_constituents_df(
                api_key, ticker, holdings_date.isoformat()
            ),
        )
        flows_df, flows_err = fetch_dataset(
            "fund flow",
            lambda: load_fund_flows_df(
                api_key,
                ticker,
                start_window.isoformat(),
                date.today().isoformat(),
            ),
        )
        analytics_df, analytics_err = fetch_dataset(
            "analytics", lambda: load_analytics_df(api_key, ticker, limit=1)
        )
        profile_df, profiles_err = fetch_dataset(
            "profiles", lambda: load_profile_df(api_key, ticker)
        )
        taxonomy_df, taxonomy_err = fetch_dataset(
            "taxonomies", lambda: load_taxonomy_df(api_key, ticker)
        )

    overall_time = time.time() - overall_start
    LOGGER.info(f"All data fetching completed in {overall_time:.2f}s")

    for message in [
        constituents_err,
        flows_err,
        analytics_err,
        profiles_err,
        taxonomy_err,
    ]:
        if message:
            st.warning(message)

    highlights = derive_highlights(
        constituents_df, flows_df, analytics_df, profile_df
    )

    st.subheader("Actionable Highlights")
    for point in highlights:
        st.markdown(f"- {point}")

    tabs = st.tabs(
        [
            "Holdings",
            "Fund Flows",
            "Analytics",
            "Profiles & Taxonomies",
        ]
    )

    with tabs[0]:
        render_constituents_tab(constituents_df)
    with tabs[1]:
        render_flows_tab(flows_df)
    with tabs[2]:
        render_analytics_tab(analytics_df)
    with tabs[3]:
        render_profile_tab(profile_df, taxonomy_df)

    st.divider()
    st.caption(
        "Educational example. Data courtesy of Massive.com + ETF Global®. "
        "Always confirm entitlements and licensing before using in production."
    )


if __name__ == "__main__":
    main()

