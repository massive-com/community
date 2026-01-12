import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
import os
from massive import RESTClient
from massive.exceptions import BadResponse
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from urllib.parse import urlparse, parse_qs

load_dotenv()

DEFAULT_TICKERS = "AAPL,MSFT,GOOGL,TSLA,NVDA,META,AMZN,IBM,INTC,CSCO,ORCL,SAP,IBM,SAP,ORCL,CSCO,INTC,META"
DEFAULT_EVENT_TYPES = ["earnings_announcement_date"]
DEFAULT_STATUSES = ["confirmed", "approved"]
DEFAULT_DATE_RANGE_DAYS = 90
MAX_DATE_RANGE_DAYS = 365
DEFAULT_LIMIT = 50
MIN_DATE = date(2018, 1, 1)

ALL_EVENT_TYPES = [
    "analyst_day",
    "business_update",
    "capital_markets_day",
    "conference",
    "dividend",
    "earnings_announcement_date",
    "earnings_conference_call",
    "earnings_results_announcement",
    "forum",
    "interim_statement",
    "other_interim_announcement",
    "production_update",
    "research_and_development_day",
    "seminar",
    "shareholder_meeting",
    "sales_update",
    "stock_split",
    "summit",
    "service_level_update",
    "tradeshow",
    "company_travel",
    "workshop",
]

ALL_STATUSES = [
    "approved",
    "canceled",
    "confirmed",
    "historical",
    "pending_approval",
    "postponed",
    "unconfirmed",
]

EVENT_TYPE_COLORS = {
    "earnings": "#dc3545",
    "dividend": "#28a745",
    "conference": "#007bff",
    "meeting": "#6f42c1",
    "update": "#fd7e14",
    "default": "#ffc107",
}

DISPLAY_COLUMNS = ["date", "ticker", "company_name", "type", "status", "name"]

COLUMN_CONFIG = {
    "date": st.column_config.DateColumn("Date"),
    "ticker": st.column_config.TextColumn("Ticker"),
    "company_name": st.column_config.TextColumn("Company"),
    "type": st.column_config.TextColumn("Event Type"),
    "status": st.column_config.TextColumn("Status"),
    "name": st.column_config.TextColumn("Event Name"),
}

def initialize_session_state():
    if "events_loaded" not in st.session_state:
        st.session_state.events_loaded = False
    if "events" not in st.session_state:
        st.session_state.events = []
    if "selected_event" not in st.session_state:
        st.session_state.selected_event = None

def format_event_field(value: str) -> str:
    return value.replace("_", " ").title() if value else ""

def event_to_dict(event: Any) -> Dict[str, Any]:
    return {
        key: value
        for key, value in vars(event).items()
        if not key.startswith("_")
    }

def get_event_id(event_dict: Dict[str, Any]) -> Optional[str]:
    return (
        event_dict.get("tmx_record_id") or
        f"{event_dict.get('ticker')}_{event_dict.get('date')}_{event_dict.get('type')}"
    )

def get_event_color(event_type: str) -> str:
    if not event_type:
        return EVENT_TYPE_COLORS["default"]
    
    event_lower = event_type.lower()
    if "earnings" in event_lower:
        return EVENT_TYPE_COLORS["earnings"]
    elif "dividend" in event_lower:
        return EVENT_TYPE_COLORS["dividend"]
    elif any(x in event_lower for x in ["conference", "forum", "summit"]):
        return EVENT_TYPE_COLORS["conference"]
    elif "meeting" in event_lower:
        return EVENT_TYPE_COLORS["meeting"]
    elif "update" in event_lower:
        return EVENT_TYPE_COLORS["update"]
    return EVENT_TYPE_COLORS["default"]

def get_quarter_dates(year: int, quarter: int) -> Tuple[date, date]:
    quarter_ranges = {
        1: (date(year, 1, 1), date(year, 3, 31)),
        2: (date(year, 4, 1), date(year, 6, 30)),
        3: (date(year, 7, 1), date(year, 9, 30)),
        4: (date(year, 10, 1), date(year, 12, 31)),
    }
    return quarter_ranges.get(quarter, quarter_ranges[1])

def calculate_date_range_from_preset(preset: str, current_year: int, current_quarter: int) -> Tuple[date, date]:
    if preset == "Custom":
        return date.today(), date.today() + timedelta(days=DEFAULT_DATE_RANGE_DAYS)
    elif preset.startswith("Q"):
        year = int(preset.split()[-1])
        q_num = int(preset.split()[0][1])
        return get_quarter_dates(year, q_num)
    elif preset == "Next 30 Days":
        return date.today(), date.today() + timedelta(days=30)
    elif preset == "Next 60 Days":
        return date.today(), date.today() + timedelta(days=60)
    elif preset == "Next 90 Days":
        return date.today(), date.today() + timedelta(days=90)
    elif preset == "Current Quarter":
        return get_quarter_dates(current_year, current_quarter)
    elif preset == "Next Quarter":
        next_q = current_quarter + 1
        next_year = current_year
        if next_q > 4:
            next_q = 1
            next_year += 1
        return get_quarter_dates(next_year, next_q)
    else:
        return date.today(), date.today() + timedelta(days=DEFAULT_DATE_RANGE_DAYS)

def validate_date_range(start_date: date, end_date: date) -> Optional[str]:
    if start_date > end_date:
        return "Start date must be before or equal to end date."
    
    if start_date < MIN_DATE:
        return f"Start date cannot be before {MIN_DATE.strftime('%B %d, %Y')}."
    
    max_allowed_range = (end_date - MIN_DATE).days
    days_diff = (end_date - start_date).days
    
    if days_diff > max_allowed_range:
        return f"Date range exceeds the maximum allowed ({max_allowed_range} days from {MIN_DATE.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}). Please select a shorter range."
    
    return None

@st.cache_resource(show_spinner=False)
def get_client(api_key: str) -> RESTClient:
    return RESTClient(api_key=api_key)

def fetch_corporate_events(
    client: RESTClient,
    start_date: str,
    end_date: str,
    tickers: Optional[List[str]] = None,
    event_types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    limit: int = DEFAULT_LIMIT,
    debug: bool = False,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "date.gte": start_date,
        "date.lte": end_date,
        "limit": limit,
        "sort": "date.asc",
    }
    
    if tickers and len(tickers) > 0:
        if len(tickers) == 1:
            params["ticker"] = tickers[0]
        else:
            params["ticker.any_of"] = ",".join(tickers)
    
    if event_types and len(event_types) > 0:
        if len(event_types) == 1:
            params["type"] = event_types[0]
        else:
            params["type.any_of"] = ",".join(event_types)
    
    if statuses and len(statuses) > 0:
        if len(statuses) == 1:
            params["status"] = statuses[0]
        else:
            params["status.any_of"] = ",".join(statuses)
    
    if debug:
        st.write(f"🔍 Debug: Request params: {params}")
    
    try:
        all_results = []
        current_url = "/tmx/v1/corporate-events"
        current_params = params
        page_count = 0
        request_id = None
        
        while True:
            page_count += 1
            response = client._get(current_url, params=current_params)
            
            if isinstance(response, dict) and response.get("status") == "OK":
                results = response.get("results", [])
                all_results.extend(results)
                request_id = response.get("request_id")
                next_url = response.get("next_url")
                
                if debug:
                    st.write(f"🔍 Debug: Page {page_count} - Retrieved {len(results)} events (total: {len(all_results)})")
                
                if not next_url:
                    break
                
                parsed_url = urlparse(next_url)
                current_url = parsed_url.path
                query_params = parse_qs(parsed_url.query)
                current_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
                
                if debug:
                    st.write(f"🔍 Debug: Fetching next page from: {current_url}")
            else:
                raise ValueError(f"API returned unexpected format or status: {response}")
        
        if debug:
            st.write(f"🔍 Debug: Completed pagination - {page_count} page(s), {len(all_results)} total events")
        
        return {
            "status": "OK",
            "results": all_results,
            "next_url": None,
            "request_id": request_id or f"combined_{len(all_results)}"
        }
    
    except BadResponse as e:
        error_msg = f"API Error: {str(e)}"
        if debug:
            st.write(f"🔍 Debug: {error_msg}")
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        if debug:
            st.write(f"🔍 Debug: {error_msg}")
        raise RuntimeError(error_msg) from e

def format_event_details(event: Dict[str, Any]) -> str:
    details = []
    if event.get("company_name"):
        details.append(f"**Company:** {event['company_name']}")
    if event.get("ticker"):
        details.append(f"**Ticker:** {event['ticker']}")
    if event.get("type"):
        details.append(f"**Type:** {format_event_field(event['type'])}")
    if event.get("status"):
        details.append(f"**Status:** {format_event_field(event['status'])}")
    if event.get("date"):
        details.append(f"**Date:** {event['date']}")
    if event.get("name"):
        details.append(f"**Event Name:** {event['name']}")
    if event.get("url"):
        details.append(f"**Source:** [View Announcement]({event['url']})")
    if event.get("isin"):
        details.append(f"**ISIN:** {event['isin']}")
    if event.get("trading_venue"):
        details.append(f"**Trading Venue:** {event['trading_venue']}")
    
    return "\n\n".join(details)

@st.cache_data(show_spinner=False)
def calculate_statistics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = {
        "total": len(events),
        "unique_tickers": set(),
        "earnings_count": 0,
        "confirmed_count": 0,
    }
    
    for ev in events:
        if ev.get("ticker"):
            stats["unique_tickers"].add(ev["ticker"])
        
        ev_type = ev.get("type", "").lower()
        if "earnings" in ev_type:
            stats["earnings_count"] += 1
        
        if ev.get("status") in DEFAULT_STATUSES:
            stats["confirmed_count"] += 1
    
    stats["unique_tickers"] = len(stats["unique_tickers"])
    return stats

@st.cache_data(show_spinner=False)
def create_calendar_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cal_events = []
    for ev in events:
        ev_type = ev.get("type", "")
        color = get_event_color(ev_type)
        
        title = f"{ev.get('ticker', '—')}"
        if ev.get("name"):
            title += f" - {ev.get('name')[:30]}"
        elif ev_type:
            title += f" - {format_event_field(ev_type)}"
        
        cal_events.append({
            "title": title,
            "start": ev.get("date"),
            "backgroundColor": color,
            "borderColor": color,
            "textColor": "white" if color != EVENT_TYPE_COLORS["default"] else "black",
            "extendedProps": {
                "company": ev.get("company_name", "—"),
                "type": ev_type,
                "status": ev.get("status", "—"),
                "url": ev.get("url"),
                "ticker": ev.get("ticker", "—"),
                "isin": ev.get("isin", "—"),
                "full_event": ev,
            }
        })
    return cal_events


st.set_page_config(
    page_title="Corporate Events Calendar",
    page_icon="📅",
    layout="wide",
)

initialize_session_state()

api_key = os.getenv("MASSIVE_API_KEY")

if not api_key:
    st.warning("No MASSIVE_API_KEY found in environment variables or .env file.")
    api_key_input = st.text_input("Enter your Massive API Key", type="password", key="manual_key")
    if api_key_input:
        api_key = api_key_input.strip()
    else:
        st.stop()

with st.sidebar:
    st.header("API Status")
    if os.getenv("MASSIVE_API_KEY"):
        st.success("✓ API Key loaded from environment")
    else:
        st.info("API Key entered manually")
    
    st.divider()
    st.caption("**About:** This app showcases Massive's TMX Corporate Events API. Filter by ticker, event type, status, and date range to view upcoming corporate events in an interactive calendar.")

st.title("📅 Corporate Events Calendar")
st.caption("Powered by Massive • TMX Corporate Events")

with st.expander("ℹ️ About This Demo", expanded=False):
    st.markdown("""
    This application demonstrates the capabilities of Massive's **TMX Corporate Events API** endpoint:
    
    - **Comprehensive Event Types:** Earnings announcements, dividends, shareholder meetings, conferences, and more
    - **Status Tracking:** View confirmed, pending, canceled, or postponed events
    - **Flexible Filtering:** Filter by ticker(s), event type, status, and date range
    - **Interactive Calendar:** Visualize events with color-coding and click for details
    - **Rich Event Data:** Company names, ISINs, trading venues, and source URLs
    
    **API Endpoint:** `/tmx/v1/corporate-events`
    """)

st.subheader("Filters")

col1, col2, col3 = st.columns(3)

with col1:
    tickers_input = st.text_input(
        "Tickers (comma-separated)",
        value=DEFAULT_TICKERS,
        help="Enter one or more ticker symbols separated by commas"
    )
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()] if tickers_input else []

with col2:
    col_select_all, col_clear_all = st.columns(2)
    with col_select_all:
        if st.button("Select All", key="select_all_event_types"):
            st.session_state.event_types_select = ALL_EVENT_TYPES
            st.rerun()
    with col_clear_all:
        if st.button("Clear All", key="clear_all_event_types"):
            st.session_state.event_types_select = []
            st.rerun()
    
    event_types = st.multiselect(
        "Event Types",
        options=ALL_EVENT_TYPES,
        default=DEFAULT_EVENT_TYPES,
        key="event_types_select",
        help="Select one or more event types to filter"
    )

with col3:
    statuses = st.multiselect(
        "Status",
        options=ALL_STATUSES,
        default=DEFAULT_STATUSES,
        help="Filter by event status"
    )

st.divider()

col_date1, col_date2, col_date3 = st.columns(3)

current_year = datetime.now().year
current_quarter = (datetime.now().month - 1) // 3 + 1

with col_date1:
    quarter_preset = st.selectbox(
        "Quick Date Preset",
        ["Custom", f"Q1 {current_year}", f"Q2 {current_year}", f"Q3 {current_year}", f"Q4 {current_year}",
         f"Q1 {current_year + 1}", f"Q2 {current_year + 1}", f"Q3 {current_year + 1}", f"Q4 {current_year + 1}",
         "Next 30 Days", "Next 60 Days", "Next 90 Days", "Current Quarter", "Next Quarter"],
        help="Select a preset date range or use Custom for manual dates"
    )

with col_date2:
    default_start, default_end = calculate_date_range_from_preset(quarter_preset, current_year, current_quarter)
    manual_start = st.date_input("Start Date", value=default_start, min_value=MIN_DATE, key="start_date")

with col_date3:
    manual_end = st.date_input("End Date", value=default_end, min_value=MIN_DATE, key="end_date")

date_validation_error = validate_date_range(manual_start, manual_end)
if date_validation_error:
    st.error(date_validation_error)
    st.stop()

start_str = manual_start.strftime("%Y-%m-%d")
end_str = manual_end.strftime("%Y-%m-%d")

st.divider()

col_debug, col_test = st.columns(2)
with col_debug:
    debug_mode = st.checkbox("🐛 Enable Debug Mode", help="Show detailed API request/response information")
with col_test:
    if st.button("🧪 Test API Connection", help="Test a simple API call to verify connection"):
        with st.spinner("Testing API connection..."):
            try:
                client = get_client(api_key)
                test_events_iter = client.list_tmx_corporate_events(limit=5)
                test_events = []
                for event in test_events_iter:
                    test_events.append(event)
                    if len(test_events) >= 5:
                        break
                st.success(f"✅ API Connection successful! Retrieved {len(test_events)} events")
                if debug_mode and test_events:
                    st.json(event_to_dict(test_events[0]))
            except BadResponse as e:
                st.error(f"❌ API Error: {str(e)}")
            except Exception as e:
                st.error(f"❌ API Connection failed: {str(e)}")

if st.button("🔍 Load Events", type="primary"):
    if not tickers:
        st.warning("Please enter at least one ticker symbol.")
        st.stop()
    
    if not event_types:
        st.warning("Please select at least one event type.")
        st.stop()
    
    with st.spinner("Fetching corporate events from Massive API..."):
        try:
            client = get_client(api_key)
            
            if debug_mode:
                st.write("**Debug Information:**")
                st.write(f"- Tickers: {tickers}")
                st.write(f"- Event Types: {event_types}")
                st.write(f"- Statuses: {statuses}")
                st.write(f"- Date Range: {start_str} to {end_str}")
                st.divider()
            
            data = fetch_corporate_events(
                client=client,
                start_date=start_str,
                end_date=end_str,
                tickers=tickers,
                event_types=event_types,
                statuses=statuses if statuses else None,
                limit=DEFAULT_LIMIT,
                debug=debug_mode,
            )
            
            if isinstance(data, dict) and data.get("status") == "OK":
                all_events = data.get("results", [])
                
                if debug_mode:
                    st.write(f"**Total events retrieved:** {len(all_events)}")
                    if all_events:
                        st.write("**Sample event:**")
                        st.json(all_events[0])
                
                if not all_events:
                    st.info(
                        "No events found with the current filters.\n\n"
                        "**Suggestions:**\n"
                        "- Widen the date range\n"
                        "- Remove or change ticker filter\n"
                        "- Select different event types\n"
                        "- Try different status filters\n"
                        "- Check your API key has TMX Corporate Events access"
                    )
                    st.session_state.events_loaded = False
                    st.session_state.events = []
                    st.stop()
                
                st.session_state.events = all_events
                st.session_state.events_loaded = True
                st.rerun()
            
            else:
                st.error(f"API returned unexpected format or status: {data}")
                if debug_mode:
                    st.json(data)
                st.stop()
            
        except ValueError as e:
            st.error(
                f"**API Error:**\n\n{str(e)}\n\n"
                f"This usually indicates an issue with the API request parameters or your API key permissions."
            )
            st.stop()
        except RuntimeError as e:
            st.error(
                f"**Request Failed:**\n\n{str(e)}\n\n"
                f"This usually indicates a network issue or API service problem."
            )
            st.stop()
        except Exception as e:
            st.error(
                f"**Unexpected Error:**\n\n{str(e)}\n\n"
                f"**Common causes:**\n"
                f"• Invalid/expired API key or missing entitlements for TMX dataset\n"
                f"• Network/connectivity issue\n"
                f"• Invalid parameters (check dates/tickers)\n\n"
                f"**Debug tip:** Test a minimal request:\n"
                f"```python\n"
                f"from massive import RESTClient\n"
                f"client = RESTClient('YOUR_API_KEY')\n"
                f"events = list(client.list_tmx_corporate_events(limit=5))\n"
                f"print(events)\n"
                f"```"
            )
            st.stop()

if st.session_state.get("events_loaded", False):
    events = st.session_state.get("events", [])
    
    if events:
        st.success(f"✅ Loaded {len(events)} corporate event(s)")
        
        stats = calculate_statistics(events)
        
        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
        
        with col_sum1:
            st.metric("Total Events", stats["total"])
        
        with col_sum2:
            st.metric("Unique Tickers", stats["unique_tickers"])
        
        with col_sum3:
            st.metric("Earnings Events", stats["earnings_count"])
        
        with col_sum4:
            st.metric("Confirmed Events", stats["confirmed_count"])
        
        st.divider()
        
        tab1, tab2 = st.tabs(["📅 Calendar View", "📊 Table View"])
        
        with tab1:
            cal_events = create_calendar_events(events)
            
            calendar_options = {
                "editable": True,
                "selectable": True,
                "initialView": "dayGridMonth",
                "headerToolbar": {
                    "left": "prev,next",
                    "center": "title",
                    "right": "dayGridMonth"
                },
                "height": "auto",
            }
            
            cal_data = calendar(
                events=cal_events,
                options=calendar_options,
                key="corporate_events_calendar"
            )
            
            # Handle event clicks - based on streamlit-calendar documentation
            # The callback returns data when an event is clicked
            if cal_data and isinstance(cal_data, dict):
                callback = cal_data.get("callback")
                
                if callback == "eventClick":
                    # The structure is: cal_data["eventClick"]["event"]["extendedProps"]["full_event"]
                    event_click_data = cal_data.get("eventClick", {})
                    if isinstance(event_click_data, dict):
                        event_obj = event_click_data.get("event", {})
                        if isinstance(event_obj, dict):
                            extended_props = event_obj.get("extendedProps", {})
                            full_event = extended_props.get("full_event")
                            
                            if full_event:
                                st.session_state.selected_event = full_event
            
            # Display selected event details
            if st.session_state.selected_event:
                selected = st.session_state.selected_event
                st.divider()
                
                col_title, col_close = st.columns([0.95, 0.05])
                with col_title:
                    st.subheader("📋 Event Details")
                with col_close:
                    if st.button("✕", key="close_event_details", help="Close event details"):
                        st.session_state.selected_event = None
                        st.rerun()
                
                st.markdown(format_event_details(selected))
                
                if selected.get("url"):
                    st.link_button("🔗 View Source Announcement", selected["url"])
                
                st.divider()
            else:
                st.info("💡 **Tip:** Click on any event in the calendar to view detailed information.")
        
        with tab2:
            df = pd.DataFrame(events)
            
            if not df.empty:
                available_cols = [col for col in DISPLAY_COLUMNS if col in df.columns]
                df_display = (
                    df[available_cols]
                    .copy()
                    .assign(date=lambda x: pd.to_datetime(x["date"]).dt.strftime("%Y-%m-%d"))
                    .sort_values("date")
                )
                
                st.dataframe(
                    df_display,
                    width="stretch",
                    hide_index=True,
                    column_config={k: v for k, v in COLUMN_CONFIG.items() if k in available_cols}
                )
                
                if st.checkbox("Show Full Event Data (JSON)"):
                    st.json(events)

st.divider()
st.caption(
    "Filter by ticker, event type, status, and date range • "
    "Data: Massive TMX Corporate Events API • "
    f"Client: massive==2.0.3"
)
