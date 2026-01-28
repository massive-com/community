"""Benzinga Dashboard - Streamlit demo for Massive + Benzinga partnership.

This single-file app showcases all currently available Benzinga endpoints 
offered by Massive. All endpoints provide real-time data.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv
from massive import RESTClient
from massive.exceptions import BadResponse


load_dotenv()


def _configure_logger() -> logging.Logger:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("benzinga_dashboard")
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


def _resolve_api_key() -> Optional[str]:
    try:
        value = st.secrets["MASSIVE_API_KEY"]
        if value:
            return value
    except (StreamlitSecretNotFoundError, KeyError):
        LOGGER.debug("MASSIVE_API_KEY not found in Streamlit secrets")
    return os.getenv("MASSIVE_API_KEY")


@st.cache_resource(show_spinner=False)
def _get_client(api_key: str) -> RESTClient:
    """Get cached REST client without pagination."""
    return RESTClient(api_key=api_key, pagination=False)


def _model_to_dict(item: Any) -> Dict[str, Any]:
    """Convert a model object to a dictionary."""
    return {
        key: value
        for key, value in vars(item).items()
        if not key.startswith("_")
    }


def _fetch_benzinga_data_from_method(
    api_key: str,
    method_name: str,
    **kwargs
) -> pd.DataFrame:
    """Fetch Benzinga data using a client method."""
    try:
        client = _get_client(api_key)
        method = getattr(client, method_name)
        data = list(method(**kwargs))
        records = [_model_to_dict(item) for item in data]
        return pd.DataFrame(records)
    except BadResponse as exc:
        LOGGER.warning(f"API error for {method_name}: {exc}")
        return pd.DataFrame()
    except Exception as exc:
        LOGGER.exception(f"Failed to fetch {method_name}: {exc}")
        return pd.DataFrame()


# ============================================================================
# Data Fetching Functions
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_analyst_details(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    """Fetch analyst details."""
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_analysts", limit=limit
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_analyst_insights(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    """Fetch analyst insights."""
    kwargs = {"limit": limit, "sort": "last_updated.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_analyst_insights", **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_analyst_ratings(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Fetch analyst ratings."""
    kwargs = {"limit": limit, "sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_ratings", **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_bulls_bears_say(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    """Fetch bulls and bears say."""
    kwargs = {"limit": limit, "sort": "last_updated.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_bulls_bears_say", **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_consensus_ratings(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    """Fetch consensus ratings."""
    # Note: list_benzinga_consensus_ratings requires ticker as a required parameter
    if not ticker:
        return pd.DataFrame()
    kwargs = {"limit": limit}
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_consensus_ratings", ticker=ticker, **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_corporate_guidance(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Fetch corporate guidance."""
    kwargs = {"limit": limit, "sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_guidance", **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_earnings(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Fetch earnings data."""
    kwargs = {"limit": limit, "sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_earnings", **kwargs
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_firm_details(api_key: str, limit: int = 100) -> pd.DataFrame:
    """Fetch firm details."""
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_firms", limit=limit
    )


@st.cache_data(ttl=60, show_spinner=False)
def fetch_news(
    api_key: str,
    ticker: Optional[str] = None,
    published_gte: Optional[str] = None,
    published_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Fetch news articles."""
    kwargs = {"limit": limit, "sort": "published.desc"}
    if ticker:
        kwargs["tickers"] = ticker
    if published_gte:
        kwargs["published_gte"] = published_gte
    if published_lte:
        kwargs["published_lte"] = published_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_news_v2", **kwargs
    )


# ============================================================================
# Rendering Functions
# ============================================================================

def _render_empty_state(message: str) -> None:
    """Helper to render empty state message."""
    st.info(message)


def render_analyst_details_tab(api_key: str, ticker: Optional[str]):
    st.subheader("Analyst Details")
    st.caption("Real-time structured data on financial analysts, including names, affiliated firms, and historical rating activity")
    
    df = fetch_analyst_details(api_key, ticker)
    if df.empty:
        _render_empty_state("No analyst details found.")
        return
    
    st.metric("Total Analysts", len(df))
    
    if "firm" in df.columns:
        firm_counts = df["firm"].value_counts().head(10)
        if not firm_counts.empty:
            fig = px.bar(
                x=firm_counts.values,
                y=firm_counts.index,
                orientation="h",
                labels={"x": "Number of Analysts", "y": "Firm"},
                title="Top 10 Firms by Analyst Count"
            )
            st.plotly_chart(fig, width='stretch')
    
    st.dataframe(df, width='stretch')


def render_analyst_insights_tab(api_key: str, ticker: Optional[str]):
    st.subheader("Analyst Insights")
    st.caption("Real-time insights from financial analysts, including ratings, price targets, and rationale")
    
    df = fetch_analyst_insights(api_key, ticker)
    if df.empty:
        _render_empty_state("No analyst insights found.")
        return
    
    st.metric("Total Insights", len(df))
    
    if "rating" in df.columns:
        rating_counts = df["rating"].value_counts()
        if not rating_counts.empty:
            fig = px.pie(
                values=rating_counts.values,
                names=rating_counts.index,
                title="Rating Distribution"
            )
            st.plotly_chart(fig, width='stretch')
    
    if "price_target" in df.columns:
        price_targets = df["price_target"].dropna()
        if not price_targets.empty:
            col1, col2 = st.columns(2)
            col1.metric("Average Price Target", f"${price_targets.mean():.2f}")
            col2.metric("Median Price Target", f"${price_targets.median():.2f}")
    
    st.dataframe(df, width='stretch')


def render_analyst_ratings_tab(api_key: str, ticker: Optional[str], date_gte: Optional[str], date_lte: Optional[str]):
    st.subheader("Analyst Ratings")
    st.caption("Real-time analyst ratings, including rating actions and price target changes")
    
    df = fetch_analyst_ratings(api_key, ticker, date_gte, date_lte)
    if df.empty:
        _render_empty_state("No analyst ratings found.")
        return
    
    st.metric("Total Ratings", len(df))
    
    if "rating_action" in df.columns:
        action_counts = df["rating_action"].value_counts()
        if not action_counts.empty:
            fig = px.bar(
                x=action_counts.index,
                y=action_counts.values,
                labels={"x": "Rating Action", "y": "Count"},
                title="Rating Actions Distribution"
            )
            st.plotly_chart(fig, width='stretch')
    
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df_with_dates = df.dropna(subset=["date"])
        if not df_with_dates.empty:
            daily_counts = df_with_dates.groupby(df_with_dates["date"].dt.date).size()
            if not daily_counts.empty:
                fig = px.line(
                    x=daily_counts.index,
                    y=daily_counts.values,
                    labels={"x": "Date", "y": "Number of Ratings"},
                    title="Ratings Over Time"
                )
                st.plotly_chart(fig, width='stretch')
    
    st.dataframe(df, width='stretch')


def render_bulls_bears_say_tab(api_key: str, ticker: Optional[str]):
    st.subheader("Bulls & Bears Say")
    st.caption("Real-time bull and bear case summaries for publicly traded companies")
    
    df = fetch_bulls_bears_say(api_key, ticker)
    if df.empty:
        _render_empty_state("No bulls/bears data found.")
        return
    
    st.metric("Total Records", len(df))
    
    for idx, row in df.head(5).iterrows():
        ticker_val = row.get("ticker", "N/A")
        company = row.get("company_name", "N/A")
        with st.expander(f"{ticker_val} - {company}"):
            if "bull_case" in row and pd.notna(row["bull_case"]):
                st.markdown(f"**Bull Case:** {row['bull_case']}")
            if "bear_case" in row and pd.notna(row["bear_case"]):
                st.markdown(f"**Bear Case:** {row['bear_case']}")
    
    st.dataframe(df, width='stretch')


def render_consensus_ratings_tab(api_key: str, ticker: Optional[str]):
    st.subheader("Consensus Ratings")
    st.caption("Real-time aggregated rating distributions and price target ranges")
    
    df = fetch_consensus_ratings(api_key, ticker)
    if df.empty:
        _render_empty_state("No consensus ratings found.")
        return
    
    st.metric("Total Consensus Records", len(df))
    
    if "consensus_rating" in df.columns:
        consensus_counts = df["consensus_rating"].value_counts()
        if not consensus_counts.empty:
            fig = px.pie(
                values=consensus_counts.values,
                names=consensus_counts.index,
                title="Consensus Rating Distribution"
            )
            st.plotly_chart(fig, width='stretch')
    
    if "price_target_low" in df.columns and "price_target_high" in df.columns:
        df_clean = df.dropna(subset=["price_target_low", "price_target_high"])
        if not df_clean.empty:
            fig = go.Figure()
            fig.add_trace(go.Box(y=df_clean["price_target_low"], name="Low Target", boxmean="sd"))
            fig.add_trace(go.Box(y=df_clean["price_target_high"], name="High Target", boxmean="sd"))
            fig.update_layout(title="Price Target Ranges", yaxis_title="Price Target")
            st.plotly_chart(fig, width='stretch')
    
    st.dataframe(df, width='stretch')


def render_corporate_guidance_tab(api_key: str, ticker: Optional[str], date_gte: Optional[str], date_lte: Optional[str]):
    st.subheader("Corporate Guidance")
    st.caption("Real-time structured earnings guidance data, including projected EPS and revenue figures")
    
    df = fetch_corporate_guidance(api_key, ticker, date_gte, date_lte)
    if df.empty:
        _render_empty_state("No corporate guidance found.")
        return
    
    st.metric("Total Guidance Records", len(df))
    
    if "guidance_type" in df.columns:
        type_counts = df["guidance_type"].value_counts()
        if not type_counts.empty:
            fig = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                labels={"x": "Guidance Type", "y": "Count"},
                title="Guidance Types Distribution"
            )
            st.plotly_chart(fig, width='stretch')
    
    st.dataframe(df, width='stretch')


def render_earnings_tab(api_key: str, ticker: Optional[str], date_gte: Optional[str], date_lte: Optional[str]):
    st.subheader("Earnings")
    st.caption("Real-time earnings announcements with EPS, revenue, and analyst estimates")
    
    df = fetch_earnings(api_key, ticker, date_gte, date_lte)
    if df.empty:
        _render_empty_state("No earnings data found.")
        return
    
    st.metric("Total Earnings Records", len(df))
    
    if "eps_surprise_percent" in df.columns:
        surprises = df["eps_surprise_percent"].dropna()
        if not surprises.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Avg EPS Surprise %", f"{surprises.mean():.2f}%")
            col2.metric("Positive Surprises", f"{(surprises > 0).sum()}")
            col3.metric("Negative Surprises", f"{(surprises < 0).sum()}")
    
    if "date" in df.columns and "actual_eps" in df.columns and "estimated_eps" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df_clean = df.dropna(subset=["date", "actual_eps", "estimated_eps"]).sort_values("date")
        if not df_clean.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_clean["date"],
                y=df_clean["actual_eps"],
                name="Actual EPS",
                mode="lines+markers"
            ))
            fig.add_trace(go.Scatter(
                x=df_clean["date"],
                y=df_clean["estimated_eps"],
                name="Estimated EPS",
                mode="lines+markers"
            ))
            fig.update_layout(
                title="EPS: Actual vs Estimated Over Time",
                xaxis_title="Date",
                yaxis_title="EPS"
            )
            st.plotly_chart(fig, width='stretch')
    
    st.dataframe(df, width='stretch')


def render_firm_details_tab(api_key: str):
    st.subheader("Firm Details")
    st.caption("Real-time structured data on analyst firms, including firm names and identifiers")
    
    df = fetch_firm_details(api_key)
    if df.empty:
        _render_empty_state("No firm details found.")
        return
    
    st.metric("Total Firms", len(df))
    st.dataframe(df, width='stretch')


def render_news_tab(api_key: str, ticker: Optional[str], published_gte: Optional[str], published_lte: Optional[str]):
    st.subheader("Real-time Benzinga News")
    st.caption("Real-time structured, timestamped news articles from Benzinga")
    
    # Real-time toggle
    realtime_enabled = st.checkbox("Enable Real-time Updates", value=False, key="realtime_news")
    
    if realtime_enabled:
        st.info("🔄 Real-time mode: News will refresh automatically. Use the refresh button to update manually.")
        
        # Initialize session state
        if "last_news_update" not in st.session_state:
            st.session_state.last_news_update = None
        
        # Manual refresh button
        if st.button("🔄 Refresh News Now"):
            fetch_news.clear()
            st.session_state.last_news_update = None
            st.rerun()
        
        # Auto-refresh logic
        current_time = time.time()
        if (st.session_state.last_news_update is None or 
            current_time - st.session_state.last_news_update > 30):
            with st.spinner("Fetching latest news..."):
                fetch_news.clear()
                df = fetch_news(api_key, ticker, published_gte, published_lte)
                st.session_state.last_news_update = current_time
                st.session_state.news_df = df
        else:
            df = st.session_state.get("news_df", pd.DataFrame())
            if df.empty:
                df = fetch_news(api_key, ticker, published_gte, published_lte)
    else:
        df = fetch_news(api_key, ticker, published_gte, published_lte)
    
    if df.empty:
        _render_empty_state("No news articles found.")
        return
    
    st.metric("Total Articles", len(df))
    
    if "published" in df.columns:
        df["published"] = pd.to_datetime(df["published"], errors="coerce")
        df_with_dates = df.dropna(subset=["published"])
        if not df_with_dates.empty:
            hourly_counts = df_with_dates.groupby(df_with_dates["published"].dt.floor("h")).size()
            if not hourly_counts.empty:
                fig = px.line(
                    x=hourly_counts.index,
                    y=hourly_counts.values,
                    labels={"x": "Time", "y": "Number of Articles"},
                    title="News Articles Over Time (Hourly)"
                )
                st.plotly_chart(fig, width='stretch')
    
    if "channels" in df.columns:
        all_channels = []
        for channels in df["channels"].dropna():
            if isinstance(channels, list):
                all_channels.extend(channels)
        if all_channels:
            channel_counts = pd.Series(all_channels).value_counts().head(10)
            fig = px.bar(
                x=channel_counts.values,
                y=channel_counts.index,
                orientation="h",
                labels={"x": "Count", "y": "Channel"},
                title="Top 10 News Channels"
            )
            st.plotly_chart(fig, width='stretch')
    
    # Display recent articles
    st.subheader("Recent Articles")
    for idx, row in df.head(10).iterrows():
        title = row.get("title", "No Title")
        published = row.get("published", "N/A")
        with st.expander(f"{title} - {published}"):
            if "teaser" in row and pd.notna(row["teaser"]):
                st.markdown(row["teaser"])
            if "url" in row and pd.notna(row["url"]):
                st.link_button("Read Full Article", row["url"])
            if "tickers" in row:
                tickers = row["tickers"]
                if tickers is not None:
                    if isinstance(tickers, list) and len(tickers) > 0:
                        st.write(f"**Tickers:** {', '.join(tickers)}")
                    elif not isinstance(tickers, list) and pd.notna(tickers):
                        st.write(f"**Tickers:** {tickers}")
    
    st.dataframe(df, width='stretch')


# ============================================================================
# Main App
# ============================================================================

def _calculate_date_range(date_range: str) -> tuple[Optional[str], Optional[str]]:
    """Calculate date range from preset selection."""
    today = date.today()
    ranges = {
        "Last 7 days": (today - timedelta(days=7), today),
        "Last 30 days": (today - timedelta(days=30), today),
        "Last 90 days": (today - timedelta(days=90), today),
        "Last year": (today - timedelta(days=365), today),
    }
    if date_range in ranges:
        start, end = ranges[date_range]
        return start.isoformat(), end.isoformat()
    return None, None


def main():
    st.set_page_config(
        page_title="Benzinga Dashboard",
        page_icon="📰",
        layout="wide",
    )
    st.title("Benzinga Dashboard")
    st.caption(
        "Powered by Massive.com • Benzinga partnership data "
        "(/benzinga/v1 and /benzinga/v2 endpoints). "
        "All endpoints provide real-time data."
    )

    api_key = _resolve_api_key()
    if not api_key:
        st.error(
            "MASSIVE_API_KEY is missing. Add it to `.env` or Streamlit secrets "
            "before using the dashboard."
        )
        st.stop()

    with st.sidebar:
        st.header("Filters")
        ticker_input = st.text_input("Ticker (optional)", value="").strip().upper()
        ticker = ticker_input if ticker_input else None
        
        date_range = st.selectbox(
            "Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Last year", "Custom", "All"],
            index=1
        )
        
        date_gte = None
        date_lte = None
        
        if date_range == "Custom":
            date_gte = st.date_input("Start Date", value=date.today() - timedelta(days=30))
            date_lte = st.date_input("End Date", value=date.today())
            date_gte = date_gte.isoformat()
            date_lte = date_lte.isoformat()
        elif date_range != "All":
            date_gte, date_lte = _calculate_date_range(date_range)
        
        st.divider()
        st.caption("**Note:** Some endpoints may require specific entitlements. "
                  "Check your Massive account for Benzinga partnership access.")

    tabs = st.tabs([
        "📰 News (Real-time)",
        "📊 Analyst Ratings",
        "💡 Analyst Insights",
        "👥 Analyst Details",
        "📈 Earnings",
        "🎯 Consensus Ratings",
        "🐂🐻 Bulls & Bears",
        "📋 Corporate Guidance",
        "🏢 Firm Details",
    ])

    with tabs[0]:
        render_news_tab(api_key, ticker, date_gte, date_lte)
    with tabs[1]:
        render_analyst_ratings_tab(api_key, ticker, date_gte, date_lte)
    with tabs[2]:
        render_analyst_insights_tab(api_key, ticker)
    with tabs[3]:
        render_analyst_details_tab(api_key, ticker)
    with tabs[4]:
        render_earnings_tab(api_key, ticker, date_gte, date_lte)
    with tabs[5]:
        render_consensus_ratings_tab(api_key, ticker)
    with tabs[6]:
        render_bulls_bears_say_tab(api_key, ticker)
    with tabs[7]:
        render_corporate_guidance_tab(api_key, ticker, date_gte, date_lte)
    with tabs[8]:
        render_firm_details_tab(api_key)

    st.divider()
    st.caption(
        "Educational example. Data courtesy of Massive.com + Benzinga. "
        "Always confirm entitlements and licensing before using in production."
    )


if __name__ == "__main__":
    main()
