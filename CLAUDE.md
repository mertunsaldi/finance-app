# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal finance dashboard built with **Streamlit** (Python). Tracks installments/debts and investments across multiple asset classes (gold, silver, TEFAS funds, BIST stocks, foreign stocks, crypto) with real-time price feeds. Uses **Google Sheets** as the primary database via gspread service account authentication.

## Running the App

Project uses **uv** for package management and a local `.venv`. Always run through the venv — global Python does not have the dependencies installed.

```bash
# Install dependencies
uv pip install -r requirements.txt

# Run (development) — ALWAYS use .venv
.venv/bin/python -m streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false

# Run (production)
.venv/bin/python -m streamlit run app.py
```

The app runs on port 8501. No test framework is configured.

## Architecture

### Multi-Page Streamlit App

- `app.py` — Main dashboard: financial overview, 6-month cash flow projection, portfolio distribution chart
- `pages/2_Gelirler.py` — Income management: regular (recurring) and irregular (one-time) income entries
- `pages/3_Giderler.py` — Expense management: recurring fixed expenses (rent, bills, subscriptions)
- `pages/4_Taksitler.py` — Installment/debt management: add cards, track monthly payments
- `pages/5_Yatırımlar.py` — Investment portfolio: multi-asset buy/sell transactions, real-time P&L

Streamlit auto-routes based on numbered filenames in `pages/`.

### Data Layer (`utils/data_handler.py`)

All data is stored in a Google Sheets spreadsheet ("finance-db") with per-user worksheets:
- `users` — credentials (SHA-256 hashed passwords)
- `installments_{username}`, `investments_{username}`, `cards_{username}` — user-isolated data

Key functions: `load_data(filename)` returns list of dicts, `save_data(filename, data)` writes to Google Sheets. GCP credentials are in `.streamlit/secrets.toml`.

### Authentication (`utils/auth.py`)

Cookie-based login via `extra-streamlit-components.CookieManager`. Every page calls `check_login()` at the top. Session tracked in `st.session_state["logged_in_user"]`. Cookies persist 30 days.

### Financial Data Sources

| Source | Asset Types | Method |
|--------|------------|--------|
| yfinance | BIST stocks (.IS suffix), foreign stocks, crypto (-USD suffix), USD/TRY rate | API |
| TEFAS website | Turkish investment funds | BeautifulSoup scraping |
| CanlıDöviz (canlidoviz.com) | Gold/silver prices | BeautifulSoup scraping, yfinance fallback |

All price-fetching functions are cached with `@st.cache_data(ttl=300)` (5-minute TTL). Foreign asset values are auto-converted to TRY using live USD/TRY rate.

### Caching Strategy

- `@st.cache_resource` — Google Sheets client (persistent across reruns)
- `@st.cache_data(ttl=300)` — All price-fetching functions (5-min TTL)

## Language

The UI is in Turkish. Variable names and code comments are a mix of Turkish and English.
