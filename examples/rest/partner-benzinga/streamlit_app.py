"""Benzinga Dashboard - Streamlit demo for Massive + Benzinga partnership.
"""
from __future__ import annotations

import html as html_mod
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv
from massive import RESTClient
from massive.exceptions import BadResponse


load_dotenv()

MAX_LIMIT = 500


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

# ============================================================================
# Plotly dark theme (Massive blue + Benzinga navy palette)
# ============================================================================

_CHART_COLORS = [
    "#155cfc",
    "#4da3ff",
    "#093451",
    "#7ab3ff",
    "#ff8163",
    "#ffa94d",
]

_CHART_MARGIN = dict(t=40, b=10, l=10, r=10)
_CHART_MARGIN_COMPACT = dict(t=10, b=10, l=10, r=10)

_dark_template = go.layout.Template()
_dark_template.layout = go.Layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e8e6ef", family="sans-serif"),
    title=dict(font=dict(color="#e8e6ef", size=16)),
    xaxis=dict(gridcolor="#2d2c35", zerolinecolor="#2d2c35"),
    yaxis=dict(gridcolor="#2d2c35", zerolinecolor="#2d2c35"),
    colorway=_CHART_COLORS,
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)
pio.templates["massive_dark"] = _dark_template
pio.templates.default = "plotly+massive_dark"

# ============================================================================
# Custom CSS
# ============================================================================

_CUSTOM_CSS = """
<style>
/* ---- Hide Streamlit chrome ---- */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}

/* ---- Metric cards ---- */
div[data-testid="stMetric"] {
    background: #1e1d24;
    border: 1px solid #2d2c35;
    border-radius: 8px;
    padding: 12px 16px;
}
div[data-testid="stMetric"] label {
    color: #9e9da6;
}

/* ---- Tab bar ---- */
button[data-baseweb="tab"] {
    color: #9e9da6 !important;
    font-weight: 600;
    font-size: 0.95rem;
    padding: 10px 18px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #155cfc !important;
    border-bottom-color: #155cfc !important;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    border-right: 1px solid #2d2c35;
}

/* ---- Expanders ---- */
details[data-testid="stExpander"] {
    border: 1px solid #2d2c35;
    border-radius: 8px;
    background: #1e1d24;
}

/* ---- Containers with border (cards) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #2d2c35 !important;
    border-radius: 10px !important;
}

/* ---- Info / Warning boxes ---- */
div[data-testid="stAlert"] {
    border-radius: 8px;
}

/* ---- Dataframes ---- */
div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ---- Responsive / mobile ---- */
@media (max-width: 768px) {
    button[data-baseweb="tab"] {
        font-size: 0.8rem !important;
        padding: 8px 10px !important;
    }
    div[data-testid="stMetric"] {
        padding: 8px 10px;
    }
    .card-title {
        font-size: 0.95rem;
    }
}

/* ---- Section titles inside cards ---- */
.card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #e8e6ef;
    margin-bottom: 0.5rem;
}
.card-subtitle {
    font-size: 0.82rem;
    color: #9e9da6;
    margin-bottom: 1rem;
}
</style>
"""

_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
_LOGO_FILES = {
    "massive_white": os.path.join(_IMAGES_DIR, "massive-logo-white.svg"),
    "massive_black": os.path.join(_IMAGES_DIR, "massive-logo-black.svg"),
    "benzinga_white": os.path.join(_IMAGES_DIR, "Benzinga-logo-white.svg"),
    "benzinga_blue": os.path.join(_IMAGES_DIR, "Benzinga-logo-blue.svg"),
}


def _render_svg(filepath: str, width: int = 160) -> None:
    """Render an SVG file inline to avoid Streamlit's image container masking."""
    if not os.path.isfile(filepath):
        return
    with open(filepath) as f:
        svg = f.read()
    st.markdown(
        f'<div style="width:{width}px;margin-bottom:8px;">{svg}</div>',
        unsafe_allow_html=True,
    )


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


def _model_to_dict(item: Any) -> dict[str, Any]:
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


def _parse_tickers(ticker_input: str) -> Optional[tuple[str, ...]]:
    """Parse comma-separated ticker input into a tuple, or None if empty."""
    if not ticker_input:
        return None
    tickers = tuple(t.strip().upper() for t in ticker_input.split(",") if t.strip())
    return tickers if tickers else None


# ============================================================================
# Data Fetching Functions
# ============================================================================

@st.cache_data(ttl=60, show_spinner="Fetching analyst details...")
def fetch_analyst_details(api_key: str, limit: int = 100) -> pd.DataFrame:
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_analysts", limit=limit
    )


@st.cache_data(ttl=60, show_spinner="Fetching analyst insights...")
def fetch_analyst_insights(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "last_updated.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_analyst_insights", limit=limit, **kwargs,
    )


@st.cache_data(ttl=60, show_spinner="Fetching analyst ratings...")
def fetch_analyst_ratings(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_ratings", limit=limit, **kwargs
    )


@st.cache_data(ttl=60, show_spinner="Fetching bulls & bears analysis...")
def fetch_bulls_bears_say(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "last_updated.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_bulls_bears_say", limit=limit, **kwargs,
    )


@st.cache_data(ttl=60, show_spinner="Fetching consensus ratings...")
def fetch_consensus_ratings(
    api_key: str, ticker: Optional[str] = None, limit: int = 100
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {}
    if ticker:
        kwargs["ticker"] = ticker
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_consensus_ratings", limit=limit, **kwargs,
    )


@st.cache_data(ttl=60, show_spinner="Fetching corporate guidance...")
def fetch_corporate_guidance(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_guidance", limit=limit, **kwargs
    )


@st.cache_data(ttl=60, show_spinner="Fetching earnings data...")
def fetch_earnings(
    api_key: str,
    ticker: Optional[str] = None,
    date_gte: Optional[str] = None,
    date_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "date.desc"}
    if ticker:
        kwargs["ticker"] = ticker
    if date_gte:
        kwargs["date_gte"] = date_gte
    if date_lte:
        kwargs["date_lte"] = date_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_earnings", limit=limit, **kwargs
    )


@st.cache_data(ttl=60, show_spinner="Fetching firm details...")
def fetch_firm_details(api_key: str, limit: int = 100) -> pd.DataFrame:
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_firms", limit=limit
    )


@st.cache_data(ttl=60, show_spinner="Fetching news...")
def fetch_news(
    api_key: str,
    tickers: Optional[tuple[str, ...]] = None,
    published_gte: Optional[str] = None,
    published_lte: Optional[str] = None,
    limit: int = 100,
) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"sort": "published.desc"}
    if tickers:
        if len(tickers) == 1:
            kwargs["tickers"] = tickers[0]
        else:
            kwargs["tickers_any_of"] = tickers
    if published_gte:
        kwargs["published_gte"] = published_gte
    if published_lte:
        kwargs["published_lte"] = published_lte
    return _fetch_benzinga_data_from_method(
        api_key, "list_benzinga_news_v2", limit=limit, **kwargs,
    )


# ============================================================================
# Real-time refresh helpers
# ============================================================================

REFRESH_INTERVAL_MS = 30_000


# ============================================================================
# Helpers
# ============================================================================

def _card_header(title: str, subtitle: str = "") -> None:
    """Render a card title + optional subtitle using HTML for clean styling."""
    html = f'<div class="card-title">{title}</div>'
    if subtitle:
        html += f'<div class="card-subtitle">{subtitle}</div>'
    st.markdown(html, unsafe_allow_html=True)


def _raw_data_expander(
    df: pd.DataFrame,
    label: str = "View raw data",
    column_config: Optional[dict] = None,
) -> None:
    """Show a dataframe inside a collapsed expander."""
    if df.empty:
        return
    with st.expander(label):
        st.dataframe(df, width='stretch', column_config=column_config)


def _format_tickers_display(raw_tickers) -> Optional[str]:
    if raw_tickers is None:
        return None
    if isinstance(raw_tickers, list):
        return ", ".join(str(t) for t in raw_tickers) if raw_tickers else None
    if isinstance(raw_tickers, str) and raw_tickers.strip():
        return raw_tickers.strip()
    return None


# ============================================================================
# Tab: Insights (Consensus + Bulls/Bears + Insights)
# ============================================================================

def render_dashboard_tab(
    api_key: str,
    ticker: Optional[str],
    date_gte: Optional[str],
    date_lte: Optional[str],
    limit: int,
):
    # --- Consensus Ratings ---
    with st.container(border=True):
        _card_header("Consensus Ratings", "Aggregated rating distributions and price target ranges")
        if not ticker:
            st.caption("Requires a ticker.")
        else:
            df = fetch_consensus_ratings(api_key, ticker, limit=limit)
            if df.empty:
                st.caption("No consensus ratings found.")
            else:
                rating_cols = {
                    "Strong Buy": "strong_buy_ratings",
                    "Buy": "buy_ratings",
                    "Hold": "hold_ratings",
                    "Sell": "sell_ratings",
                    "Strong Sell": "strong_sell_ratings",
                }
                breakdown = {}
                for label, col in rating_cols.items():
                    if col in df.columns:
                        val = pd.to_numeric(df[col], errors="coerce").sum()
                        if val > 0:
                            breakdown[label] = int(val)
                if breakdown:
                    fig = px.pie(
                        values=list(breakdown.values()),
                        names=list(breakdown.keys()),
                        title="Rating Breakdown",
                    )
                    fig.update_layout(margin=_CHART_MARGIN)
                    st.plotly_chart(fig, width='stretch')
                elif "consensus_rating" in df.columns:
                    counts = df["consensus_rating"].value_counts()
                    if not counts.empty:
                        fig = px.pie(values=counts.values, names=counts.index, title="Rating Distribution")
                        fig.update_layout(margin=_CHART_MARGIN)
                        st.plotly_chart(fig, width='stretch')
                _raw_data_expander(df)

    # --- Bulls & Bears ---
    with st.container(border=True):
        _card_header("Bulls & Bears Say", "Bull and bear case summaries")
        df = fetch_bulls_bears_say(api_key, ticker, limit=limit)
        if df.empty:
            st.caption("No bulls/bears data found.")
        else:
            for _, row in df.head(6).iterrows():
                ticker_val = row.get("ticker", "")
                company = row.get("company_name")
                label = f"{ticker_val} - {company}" if company and pd.notna(company) else str(ticker_val)
                with st.expander(label):
                    c1, c2 = st.columns(2)
                    with c1:
                        bull = row.get("bull_case")
                        if bull and pd.notna(bull):
                            st.markdown(f"**Bull Case**\n\n{bull}")
                        else:
                            st.caption("No bull case available.")
                    with c2:
                        bear = row.get("bear_case")
                        if bear and pd.notna(bear):
                            st.markdown(f"**Bear Case**\n\n{bear}")
                        else:
                            st.caption("No bear case available.")
            _raw_data_expander(df)

    # --- Analyst Insights ---
    with st.container(border=True):
        _card_header("Analyst Insights", "Ratings, price targets, and rationale")
        df = fetch_analyst_insights(api_key, ticker, date_gte, date_lte, limit=limit)
        if df.empty:
            st.caption("No analyst insights found.")
        else:
            col_pie, col_metrics = st.columns([2, 1])
            with col_pie:
                if "rating" in df.columns:
                    counts = df["rating"].value_counts()
                    if not counts.empty:
                        fig = px.pie(values=counts.values, names=counts.index, title="Insight Rating Distribution")
                        fig.update_layout(margin=_CHART_MARGIN)
                        st.plotly_chart(fig, width='stretch')
            with col_metrics:
                if ticker and "price_target" in df.columns:
                    targets = df["price_target"].dropna()
                    if not targets.empty:
                        st.metric("Avg Price Target", f"${targets.mean():.2f}")
                        st.metric("Median Price Target", f"${targets.median():.2f}")
                        st.metric("Insights Count", len(df))
                elif not ticker:
                    st.caption("Enter a ticker to see price target metrics.")
            _raw_data_expander(df)


# ============================================================================
# Tab: News
# ============================================================================

def _clean_text(text: str) -> str:
    """Unescape HTML entities that the API sometimes returns pre-encoded."""
    return html_mod.unescape(text)


def _render_news_card(row) -> str:
    """Build an HTML card for a single news article."""
    raw_title = _clean_text(str(row.get("title", "No Title")))
    title = html_mod.escape(raw_title)
    published = str(row.get("published", ""))
    author = row.get("author", "")
    teaser = row.get("teaser", "")
    url = row.get("url", "")
    ticker_str = _format_tickers_display(row.get("tickers")) or ""

    meta_items = []
    if published:
        meta_items.append(html_mod.escape(published))
    if author and pd.notna(author):
        meta_items.append(f"by {html_mod.escape(_clean_text(str(author)))}")
    if ticker_str:
        meta_items.append(f'<span style="color:#155cfc;">{html_mod.escape(ticker_str)}</span>')
    meta_html = " &middot; ".join(meta_items)

    teaser_html = ""
    if teaser and pd.notna(teaser):
        clean_teaser = html_mod.escape(_clean_text(str(teaser)))
        teaser_html = f'<p style="color:#c8c6d0;margin:6px 0 8px 0;font-size:0.9rem;line-height:1.4;">{clean_teaser}</p>'

    link_html = ""
    if url and pd.notna(url) and str(url).startswith(("http://", "https://")):
        link_html = f'<a href="{html_mod.escape(str(url))}" target="_blank" style="color:#155cfc;text-decoration:none;font-size:0.85rem;">Read full article &rarr;</a>'

    return (
        f'<div style="border:1px solid #2d2c35;border-radius:10px;padding:16px 20px;margin-bottom:10px;background:#1e1d24;">'
        f'<div style="font-size:1rem;font-weight:600;color:#e8e6ef;margin-bottom:4px;">{title}</div>'
        f'<div style="font-size:0.78rem;color:#9e9da6;margin-bottom:4px;">{meta_html}</div>'
        f'{teaser_html}'
        f'{link_html}'
        f'</div>'
    )


def render_news_tab(
    api_key: str,
    tickers: Optional[tuple[str, ...]],
    published_gte: Optional[str],
    published_lte: Optional[str],
    limit: int,
):
    df = fetch_news(api_key, tickers, published_gte, published_lte, limit=limit)
    if df.empty:
        st.info("No news found.")
        return

    display_df = df
    if "title" in df.columns:
        display_df = df.drop_duplicates(subset=["title"], keep="first")

    cards_html = ""
    for _, row in display_df.head(20).iterrows():
        cards_html += _render_news_card(row)
    st.markdown(cards_html, unsafe_allow_html=True)

    _raw_data_expander(display_df)

    # Channels chart
    if "channels" in df.columns:
        with st.container(border=True):
            _card_header("Top News Channels")
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
                )
                fig.update_layout(margin=_CHART_MARGIN_COMPACT)
                st.plotly_chart(fig, width='stretch')


# ============================================================================
# Tab: Analyst Activity (Ratings + Analyst Details)
# ============================================================================

def render_analyst_activity_tab(
    api_key: str,
    ticker: Optional[str],
    date_gte: Optional[str],
    date_lte: Optional[str],
    limit: int,
):
    with st.container(border=True):
        _card_header("Analyst Ratings", "Rating actions and price target changes")
        df = fetch_analyst_ratings(api_key, ticker, date_gte, date_lte, limit=limit)
        if df.empty:
            st.caption("No analyst ratings found.")
        else:
            if "rating_action" in df.columns:
                action_counts = df["rating_action"].value_counts()
                if not action_counts.empty:
                    fig = px.bar(
                        x=action_counts.index,
                        y=action_counts.values,
                        labels={"x": "Rating Action", "y": "Count"},
                        title="Rating Actions",
                    )
                    fig.update_layout(margin=_CHART_MARGIN)
                    st.plotly_chart(fig, width='stretch')
            _raw_data_expander(df)


# ============================================================================
# Tab: Earnings & Guidance
# ============================================================================

def render_earnings_guidance_tab(
    api_key: str,
    ticker: Optional[str],
    date_gte: Optional[str],
    date_lte: Optional[str],
    limit: int,
):
    # --- Earnings ---
    with st.container(border=True):
        _card_header("Earnings", "EPS, revenue, and analyst estimates")
        df = fetch_earnings(api_key, ticker, date_gte, date_lte, limit=limit)
        if df.empty:
            st.caption("No earnings data found.")
        else:
            if "eps_surprise_percent" in df.columns:
                surprises = df["eps_surprise_percent"].dropna()
                if not surprises.empty:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Avg EPS Surprise", f"{surprises.mean():.2f}%")
                    c2.metric("Beats", f"{(surprises > 0).sum()}")
                    c3.metric("Misses", f"{(surprises < 0).sum()}")

            if "date" in df.columns and "actual_eps" in df.columns and "estimated_eps" in df.columns:
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df_clean = df.dropna(subset=["date", "actual_eps", "estimated_eps"]).sort_values("date")
                if not df_clean.empty:
                    if len(df_clean) <= 3:
                        labels = df_clean["date"].dt.strftime("%Y-%m-%d")
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=labels, y=df_clean["actual_eps"], name="Actual"))
                        fig.add_trace(go.Bar(x=labels, y=df_clean["estimated_eps"], name="Estimated"))
                        fig.update_layout(barmode="group", title="EPS: Actual vs Estimated", xaxis_title="Date", yaxis_title="EPS", margin=_CHART_MARGIN)
                    else:
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=df_clean["date"], y=df_clean["actual_eps"], name="Actual", mode="lines+markers"))
                        fig.add_trace(go.Scatter(x=df_clean["date"], y=df_clean["estimated_eps"], name="Estimated", mode="lines+markers"))
                        fig.update_layout(title="EPS: Actual vs Estimated", xaxis_title="Date", yaxis_title="EPS", margin=_CHART_MARGIN)
                    st.plotly_chart(fig, width='stretch')
            _raw_data_expander(df)

    # --- Corporate Guidance ---
    with st.container(border=True):
        _card_header("Corporate Guidance", "Projected EPS and revenue figures")
        df = fetch_corporate_guidance(api_key, ticker, date_gte, date_lte, limit=limit)
        if df.empty:
            st.caption("No corporate guidance found.")
        else:
            if ticker and "ticker" in df.columns:
                returned = set(df["ticker"].dropna().unique())
                if ticker not in returned:
                    st.caption(f"No guidance data for: {ticker}")

            df = df.copy()
            numeric_cols_map = {
                "estimated_eps_guidance": "EPS Est.",
                "min_eps_guidance": "EPS Low",
                "max_eps_guidance": "EPS High",
                "estimated_revenue_guidance": "Revenue Est.",
                "min_revenue_guidance": "Revenue Low",
                "max_revenue_guidance": "Revenue High",
            }
            for col in numeric_cols_map:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            latest = df.iloc[0] if len(df) > 0 else None
            if latest is not None:
                period_parts = []
                if "fiscal_period" in df.columns and pd.notna(latest.get("fiscal_period")):
                    period_parts.append(str(latest["fiscal_period"]))
                if "fiscal_year" in df.columns and pd.notna(latest.get("fiscal_year")):
                    period_parts.append(str(int(latest["fiscal_year"])))
                if period_parts:
                    st.caption(f"Latest guidance: {' '.join(period_parts)}")

                metric_items: list[tuple[str, str]] = []
                if "estimated_revenue_guidance" in df.columns and pd.notna(latest.get("estimated_revenue_guidance")):
                    metric_items.append(("Revenue Est.", f"${latest['estimated_revenue_guidance']:,.0f}"))
                if "min_revenue_guidance" in df.columns and pd.notna(latest.get("min_revenue_guidance")):
                    metric_items.append(("Revenue Low", f"${latest['min_revenue_guidance']:,.0f}"))
                if "max_revenue_guidance" in df.columns and pd.notna(latest.get("max_revenue_guidance")):
                    metric_items.append(("Revenue High", f"${latest['max_revenue_guidance']:,.0f}"))
                if "estimated_eps_guidance" in df.columns and pd.notna(latest.get("estimated_eps_guidance")):
                    metric_items.append(("EPS Est.", f"${latest['estimated_eps_guidance']:.2f}"))
                if "min_eps_guidance" in df.columns and pd.notna(latest.get("min_eps_guidance")):
                    metric_items.append(("EPS Low", f"${latest['min_eps_guidance']:.2f}"))
                if "max_eps_guidance" in df.columns and pd.notna(latest.get("max_eps_guidance")):
                    metric_items.append(("EPS High", f"${latest['max_eps_guidance']:.2f}"))

                if metric_items:
                    cols = st.columns(min(len(metric_items), 3))
                    for i, (label, value) in enumerate(metric_items):
                        cols[i % len(cols)].metric(label, value)

            col_cfg = {}
            for col, label in numeric_cols_map.items():
                if col in df.columns:
                    fmt = "$%,.0f" if "revenue" in col else "%.2f"
                    col_cfg[col] = st.column_config.NumberColumn(label, format=fmt)
            _raw_data_expander(df, "View guidance data", column_config=col_cfg)


# ============================================================================
# Reference Section (not ticker-filtered)
# ============================================================================

def render_reference_section(api_key: str, limit: int):
    """Render Analyst Directory and Firm Directory below the main tabs."""
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            _card_header("Analyst Directory", "Analysts and their affiliated firms")
            df = fetch_analyst_details(api_key, limit=limit)
            if df.empty:
                st.caption("No analyst details found.")
            else:
                if "firm" in df.columns:
                    firm_counts = df["firm"].value_counts().head(10)
                    if not firm_counts.empty:
                        fig = px.bar(
                            x=firm_counts.values,
                            y=firm_counts.index,
                            orientation="h",
                            labels={"x": "Analysts", "y": "Firm"},
                            title="Top Firms by Analyst Count",
                        )
                        fig.update_layout(margin=_CHART_MARGIN)
                        st.plotly_chart(fig, width='stretch')
                st.dataframe(df, width='stretch')

    with col_right:
        with st.container(border=True):
            _card_header("Firm Directory", "Analyst firms and identifiers")
            df = fetch_firm_details(api_key, limit=limit)
            if df.empty:
                st.caption("No firm details found.")
            else:
                st.dataframe(df, width='stretch')


# ============================================================================
# Main App
# ============================================================================

def _calculate_date_range(date_range: str) -> tuple[Optional[str], Optional[str]]:
    """Calculate date range from preset selection.

    End date is set to tomorrow so that today's data is always included.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    ranges = {
        "Last 7 days": (today - timedelta(days=7), tomorrow),
        "Last 30 days": (today - timedelta(days=30), tomorrow),
        "Last 90 days": (today - timedelta(days=90), tomorrow),
        "Last year": (today - timedelta(days=365), tomorrow),
    }
    if date_range in ranges:
        start, end = ranges[date_range]
        return start.isoformat(), end.isoformat()
    return None, None


def main():
    st.set_page_config(
        page_title="Real-time Benzinga + Massive Dashboard",
        page_icon="\U0001f4f0",
        layout="wide",
    )

    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # --- Sidebar: branding + filters ---
    with st.sidebar:
        _render_svg(_LOGO_FILES["massive_white"], width=130)
        _render_svg(_LOGO_FILES["benzinga_white"], width=130)
        st.markdown(
            "<p style='color:#9e9da6;font-size:0.78rem;margin-top:2px;'>"
            "Powered by <strong style='color:#155cfc;'>Massive</strong> + "
            "<strong style='color:#4da3ff;'>Benzinga</strong></p>",
            unsafe_allow_html=True,
        )
        st.divider()

        ticker_input = st.text_input(
            "Ticker",
            value="",
            placeholder="e.g. AAPL",
        ).strip().upper()
        news_tickers = _parse_tickers(ticker_input)
        multi_ticker = news_tickers is not None and len(news_tickers) > 1
        ticker = news_tickers[0] if news_tickers and not multi_ticker else None

        date_range = st.selectbox(
            "Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Last year", "Custom", "All"],
            index=1,
        )

        date_gte = None
        date_lte = None
        if date_range == "Custom":
            date_gte = st.date_input("Start Date", value=date.today() - timedelta(days=30))
            date_lte = st.date_input("End Date", value=date.today())
            date_gte = date_gte.isoformat()
            date_lte = (date_lte + timedelta(days=1)).isoformat()
        elif date_range != "All":
            date_gte, date_lte = _calculate_date_range(date_range)

        st.divider()

        limit = st.number_input(
            "Results limit",
            min_value=1,
            max_value=MAX_LIMIT,
            value=100,
            step=25,
            help=f"Max records per endpoint (max {MAX_LIMIT}).",
        )

        st.divider()

        realtime_enabled = st.toggle(
            "Auto-refresh (30s)",
            value=False,
            help="Refresh all data every 30 seconds.",
        )

        st.divider()
        st.caption("Some endpoints require Benzinga entitlements. "
                  "Check your Massive account for access.")

    # --- Real-time refresh ---
    if realtime_enabled:
        st_autorefresh(interval=REFRESH_INTERVAL_MS, key="benzinga_autorefresh")
        st.session_state["last_refresh_time"] = datetime.now().strftime("%I:%M:%S %p")

    # --- API key ---
    api_key = _resolve_api_key()
    if not api_key:
        st.error(
            "MASSIVE_API_KEY is missing. Add it to `.env` or Streamlit secrets "
            "before using the dashboard."
        )
        st.stop()

    # --- Page header ---
    hdr_left, hdr_right = st.columns([4, 1])
    with hdr_left:
        st.markdown(
            "<h2 style='margin-bottom:0;'>Real-time Benzinga + Massive Dashboard</h2>",
            unsafe_allow_html=True,
        )
    with hdr_right:
        last = st.session_state.get("last_refresh_time")
        if last and realtime_enabled:
            st.caption(f"Refreshed {last}")

    # --- Main tabs ---
    tabs = st.tabs([
        "News",
        "Insights",
        "Analyst Activity",
        "Earnings & Guidance",
    ])

    with tabs[0]:
        render_news_tab(api_key, news_tickers, date_gte, date_lte, limit)
    _SINGLE_TICKER_MSG = "These charts support a single ticker. Please enter only one ticker in the sidebar."
    with tabs[1]:
        if multi_ticker:
            st.info(_SINGLE_TICKER_MSG)
        elif not ticker:
            st.info("Enter a ticker in the sidebar to view the dashboard.")
        else:
            render_dashboard_tab(api_key, ticker, date_gte, date_lte, limit)
    with tabs[2]:
        if multi_ticker:
            st.info(_SINGLE_TICKER_MSG)
        elif not ticker:
            st.info("Enter a ticker in the sidebar to view analyst activity.")
        else:
            render_analyst_activity_tab(api_key, ticker, date_gte, date_lte, limit)
    with tabs[3]:
        if multi_ticker:
            st.info(_SINGLE_TICKER_MSG)
        elif not ticker:
            st.info("Enter a ticker in the sidebar to view earnings & guidance.")
        else:
            render_earnings_guidance_tab(api_key, ticker, date_gte, date_lte, limit)

    # --- Reference section (not filtered by ticker) ---
    st.markdown(
        "<h3 style='margin-top:2rem;margin-bottom:0.5rem;color:#9e9da6;'>Reference</h3>",
        unsafe_allow_html=True,
    )
    render_reference_section(api_key, limit)


if __name__ == "__main__":
    main()
