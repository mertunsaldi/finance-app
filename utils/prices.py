"""Shared price-fetching functions for all asset types."""

import re
import requests
import urllib3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import streamlit as st
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@st.cache_data(ttl=300)
def get_usd_try():
    try:
        return float(yf.Ticker("TRY=X").history(period="5d")['Close'].dropna().iloc[-1])
    except Exception:
        return 32.0


_TEFAS_HEADERS = {
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://fundturkey.com.tr",
    "Referer": "https://fundturkey.com.tr/TarihselVeriler.aspx",
}


def _tefas_latest_date():
    """Son veri bulunan iş gününü DD.MM.YYYY formatında döndürür."""
    d = datetime.now()
    # Hafta sonunu atla
    if d.weekday() >= 5:
        d -= timedelta(days=(d.weekday() - 4))
    # Bugün henüz veri yoksa bir önceki iş gününe düş
    for _ in range(3):
        date_str = d.strftime("%d.%m.%Y")
        try:
            r = requests.post(
                "https://fundturkey.com.tr/api/DB/BindHistoryInfo",
                headers=_TEFAS_HEADERS, timeout=10, verify=False,
                data={"fontip": "YAT", "bastarih": date_str, "bittarih": date_str, "fonkod": "MAC"},
            )
            if r.json().get("data"):
                return date_str
        except Exception:
            pass
        d -= timedelta(days=1)
        if d.weekday() >= 5:
            d -= timedelta(days=(d.weekday() - 4))
    return d.strftime("%d.%m.%Y")


@st.cache_data(ttl=300)
def _get_tefas_date():
    """Cache'li son TEFAS veri tarihi."""
    return _tefas_latest_date()


@st.cache_data(ttl=300)
def get_tefas_price(fon_kodu):
    """Tek bir fonun fiyatını fundturkey.com.tr API'sinden çeker (~0.1 sn)."""
    date_str = _get_tefas_date()
    try:
        r = requests.post(
            "https://fundturkey.com.tr/api/DB/BindHistoryInfo",
            headers=_TEFAS_HEADERS, timeout=10, verify=False,
            data={"fontip": "YAT", "bastarih": date_str, "bittarih": date_str, "fonkod": fon_kodu},
        )
        records = r.json().get("data", [])
        if records:
            price = records[0]["FIYAT"]
            return price, price
    except Exception:
        pass
    return -1.0, -1.0


def clean_and_parse_price(text):
    text = re.sub(r'[^\d.,]', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    return float(text) if text else 0.0


def _oz_to_try(oz_price, usd_try):
    """Ons fiyatını gram-TL'ye çevirir (1 ons = 31.103 gram)."""
    return (oz_price / 31.103) * usd_try


@st.cache_data(ttl=300)
def _get_yapikredi_prices():
    """Yapı Kredi döviz sayfasından XAU ve XAG alış/satış fiyatlarını çeker.

    Returns: dict {"XAU": (alis, satis), "XAG": (alis, satis)} veya boş dict
    """
    try:
        url = "https://www.yapikredi.com.tr/yatirimci-kosesi/doviz-bilgileri"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            return {}

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", id="currencyResultContent")
        if not table:
            return {}

        result = {}
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            name = tds[0].text.strip().upper()
            if name in ("XAU", "XAG"):
                alis = clean_and_parse_price(tds[2].text)
                satis = clean_and_parse_price(tds[3].text)
                result[name] = (alis, satis)
        return result
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_gold_silver_price(ticker):
    # Sanal (banka) altın/gümüş → Yapı Kredi XAU/XAG
    if "BANKA" in ticker:
        yk = _get_yapikredi_prices()
        if "GRAM" in ticker and "XAU" in yk:
            return yk["XAU"]
        if "GUMUS" in ticker and "XAG" in yk:
            return yk["XAG"]

    # Fiziki altın/gümüş → CanlıDöviz Kapalıçarşı
    try:
        url = "https://canlidoviz.com/altin-fiyatlari/kapali-carsi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            search_text = ""
            if "GRAM" in ticker:
                search_text = "GRAM ALTIN"
            elif "22" in ticker:
                search_text = "22 AYAR BİLEZİK"
            elif "GUMUS" in ticker:
                search_text = "GÜMÜŞ"

            for tr in soup.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 3:
                    name_cell = tds[0].text.upper()
                    if search_text in name_cell:
                        alis_text = tds[1].text.strip().split()[0] if tds[1].text.strip() else ""
                        satis_text = tds[2].text.strip().split()[0] if tds[2].text.strip() else ""
                        return clean_and_parse_price(alis_text), clean_and_parse_price(satis_text)
    except Exception:
        pass

    # yfinance fallback
    try:
        usd_try = get_usd_try()
        if "GRAM" in ticker:
            gold_oz = float(yf.Ticker("GC=F").history(period="5d")['Close'].dropna().iloc[-1])
            price = _oz_to_try(gold_oz, usd_try)
            return price, price
        elif "22" in ticker:
            gold_oz = float(yf.Ticker("GC=F").history(period="5d")['Close'].dropna().iloc[-1])
            price = _oz_to_try(gold_oz, usd_try) * 0.916
            return price, price
        elif "GUMUS" in ticker:
            silver_oz = float(yf.Ticker("SI=F").history(period="5d")['Close'].dropna().iloc[-1])
            price = _oz_to_try(silver_oz, usd_try)
            return price, price
    except Exception:
        return 0.0, 0.0
    return 0.0, 0.0


@st.cache_data(ttl=300)
def get_current_price(ticker):
    if ticker.endswith("_FON"):
        return get_tefas_price(ticker.replace("_FON", ""))
    if ticker.startswith("API_"):
        return get_gold_silver_price(ticker)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].dropna().iloc[-1])
            if ticker.endswith("-USD") or not ticker.endswith(".IS"):
                price = price * get_usd_try()
            return price, price
        return 0.0, 0.0
    except Exception:
        return 0.0, 0.0


def fetch_all_prices(tickers):
    """Birden fazla ticker için fiyatları paralel çeker.

    Returns: dict {ticker: (alis, satis)}
    """
    if not tickers:
        return {}
    # TEFAS fonları için önce tarihi cache'le (tek hafif istek), sonra hepsi paralel
    if any(t.endswith("_FON") for t in tickers):
        _get_tefas_date()
    with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
        return dict(zip(tickers, executor.map(get_current_price, tickers)))


def build_portfolio(transactions):
    """İşlem listesinden portföy pozisyonlarını hesaplar.

    Returns: dict {asset_name: {"qty", "total_cost", "ticker"}}
    """
    portfolio = {}
    for t in transactions:
        a_ticker = t["asset"]
        a_name = t.get("asset_name", a_ticker)
        qty = float(t["quantity"])
        price = float(t["price"])

        if a_name not in portfolio:
            portfolio[a_name] = {"qty": 0.0, "total_cost": 0.0, "ticker": a_ticker}

        if t["type"] == "Alım":
            portfolio[a_name]["qty"] += qty
            portfolio[a_name]["total_cost"] += (qty * price)
        elif t["type"] == "Satım":
            if portfolio[a_name]["qty"] > 0:
                avg_cost = portfolio[a_name]["total_cost"] / portfolio[a_name]["qty"]
                portfolio[a_name]["qty"] -= qty
                portfolio[a_name]["total_cost"] -= (qty * avg_cost)
                if portfolio[a_name]["qty"] <= 0.00001:
                    portfolio[a_name]["qty"] = 0.0
                    portfolio[a_name]["total_cost"] = 0.0

    return portfolio


def calculate_portfolio_totals(transactions):
    """Yatırım işlemlerinden portföy maliyet ve güncel değerini hesaplar.

    Returns: (total_cost, total_current_value)
    """
    portfolio = build_portfolio(transactions)

    active = {name: data for name, data in portfolio.items() if data["qty"] > 0}
    if not active:
        return 0.0, 0.0

    tickers = [data["ticker"] for data in active.values()]
    prices = fetch_all_prices(tickers)

    total_cost = 0.0
    total_current_value = 0.0

    for a_name, data in active.items():
        total_cost += data["total_cost"]
        alis_fiyati, _ = prices[data["ticker"]]
        if alis_fiyati == -1.0:
            alis_fiyati = data["total_cost"] / data["qty"]
        total_current_value += data["qty"] * alis_fiyati

    return total_cost, total_current_value
