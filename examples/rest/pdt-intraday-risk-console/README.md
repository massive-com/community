# PDT replaced by intraday margin deficits (IML) demo

This demo is a small Streamlit dashboard that helps explain a key rule change for U.S. equities margin: the old Pattern Day Trader (PDT) framing was replaced by **intraday margin deficits**, based on **intraday margin level (IML)**, under **FINRA Rule 4210(d)(2)**.

The app uses **Massive** for **accurate, real-time equities pricing**, fetched via REST and **polled** on an interval. Those live marks are then fed into a transparent, simplified simulator so you can see how account actions and price moves can push IML negative and create an intraday deficit in the model.

## What this demo is

- A dashboard you can run locally to visualize live marks and an educational “order impact preview” style simulation.
- A concrete explanation of the shift from “How many day trades did I do?” to “Did my account run an intraday margin deficit as prices moved?”

## What this demo is not

This is an **educational demo only**.

- It is **not** a broker margin engine.
- It does **not** connect to any brokerage account.
- It does **not** model broker-specific house requirements, portfolio margin, Reg T, or other production margin logic.

## Run it

From `examples/rest/pdt-intraday-risk-console`:

### 1) Create and activate a virtualenv

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -e ".[dev]"
```

### 3) Configure environment variables

Copy the example env file and set your Massive API key.

```bash
cp .env.example .env
export $(cat .env | xargs)
```

Required:
- `MASSIVE_API_KEY`

Optional:
- `PDT_DEMO_TICKERS` (comma-separated equities tickers shown in the UI by default)

### 4) Start the Streamlit app

```bash
streamlit run streamlit_app.py
```

