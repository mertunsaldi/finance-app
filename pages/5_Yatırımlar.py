import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import calendar
import uuid
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from utils.data_handler import load_data, save_data
from utils.finance import calc_first_payment_date, clear_form_keys

from utils.auth import check_login
check_login()
current_user = st.session_state["logged_in_user"]

st.title(":material/trending_up: Yatırım ve Portföy Yönetimi")
st.markdown("""
Sadece yatırım kategorisini seçin ve işlemi girin. Sistem TEFAS fonlarını, hisseleri, kriptoları ve **Kapalıçarşı** altın/gümüş fiyatlarını otomatik olarak bularak portföyünüzü hesaplar.
*(Yabancı varlıklar ve kriptolar güncel Dolar/TL kuruyla otomatik TL'ye çevrilir. Altın ve gümüş kâr/zarar hesaplamaları "Alış" fiyatı üzerinden yapılır.)*
""")

transactions = load_data(f"investments_{current_user}")
saved_cards = load_data(f"cards_{current_user}")

# --- 1. YENİ İŞLEM EKLEME FORMU ---
with st.expander(":material/add: Yeni Alım / Satım İşlemi Ekle", expanded=False):
    category = st.selectbox("Yatırım Kategorisi", [
        "Altın / Gümüş",
        "Yatırım Fonu (TEFAS)",
        "BIST Hisse (Yerli)",
        "Yabancı Hisse",
        "Kripto Para"
    ])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        t_type = st.selectbox("İşlem Tipi", ["Alım", "Satım"])
        tx_date = st.date_input("İşlem Tarihi", value=date.today(), key="tx_date")

    with col2:
        if category == "Altın / Gümüş":
            asset_display = st.selectbox("Varlık Seçin", [
                "Fiziki Gram Altın", "Sanal Gram Altın",
                "Fiziki 22 Ayar Altın", "Fiziki Gümüş", "Sanal Gümüş"
            ])
        elif category == "Yatırım Fonu (TEFAS)":
            asset_display = st.text_input("Fon Kodu (Örn: MAC, TI3)", key="fon_input").upper()
        elif category == "BIST Hisse (Yerli)":
            asset_display = st.text_input("Hisse Kodu (Örn: THYAO)", key="bist_input").upper()
        elif category == "Yabancı Hisse":
            asset_display = st.text_input("Hisse Kodu (Örn: AAPL)", key="yabanci_input").upper()
        else:
            asset_display = st.text_input("Kripto Kodu (Örn: BTC)", key="kripto_input").upper()

    with col3:
        quantity = st.number_input("Adet / Gram", min_value=0.00001, step=1.0, format="%.5f", key="qty_input")

    with col4:
        cost_method = st.selectbox("Fiyat Girişi", ["Birim Maliyet", "Toplam Maliyet"], key="cost_method")
        cost_input = st.number_input(f"{cost_method} (TL)", min_value=0.0, step=10.0, format="%.2f", key="cost_input")

    # Ödeme şekli (sadece Alım'da göster)
    payment_type = "tek_seferlik"
    inst_months = 1
    inst_bank = ""
    if t_type == "Alım":
        st.divider()
        payment_type = st.radio("Ödeme Şekli", ["Tek Seferlik", "Taksitli"], horizontal=True, key="payment_type")
        payment_type = "tek_seferlik" if payment_type == "Tek Seferlik" else "taksitli"

        if payment_type == "taksitli":
            if not saved_cards:
                st.warning("Taksitli işlem için önce Taksitler sayfasından bir Banka/Kart eklemelisiniz.")
            else:
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    card_names = [c.get("bank_name", "") for c in saved_cards]
                    inst_bank = st.selectbox("Banka/Kart Seçin", card_names, key="inv_inst_bank")
                with col_t2:
                    inst_months = st.number_input("Taksit Sayısı", min_value=2, step=1, value=3, key="inv_inst_months")

                # Toplam tutarı hesapla ve aylık taksiti göster
                total_cost = cost_input if cost_method == "Toplam Maliyet" else (cost_input * quantity)
                if total_cost > 0 and inst_months > 0:
                    monthly = total_cost / inst_months
                    st.info(f"Toplam: **{total_cost:,.2f} TL** → Aylık taksit: **{monthly:,.2f} TL** x {inst_months} ay")

    submitted = st.button("İşlemi Kaydet", type="primary")

    if submitted:
        if asset_display and quantity > 0 and cost_input > 0:
            price = cost_input if cost_method == "Birim Maliyet" else (cost_input / quantity)
            total = quantity * price

            ticker = ""
            asset_name = ""

            if category == "Altın / Gümüş":
                asset_name = asset_display
                ticker_map = {
                    "Fiziki Gram Altın": "API_GRAM_FIZIKI",
                    "Sanal Gram Altın": "API_GRAM_BANKA",
                    "Fiziki 22 Ayar Altın": "API_22_FIZIKI",
                    "Fiziki Gümüş": "API_GUMUS_FIZIKI",
                    "Sanal Gümüş": "API_GUMUS_BANKA"
                }
                ticker = ticker_map.get(asset_display, "")
            elif category == "Yatırım Fonu (TEFAS)":
                asset_display = asset_display.strip()
                asset_name = f"{asset_display} Fonu"
                ticker = f"{asset_display}_FON"
            elif category == "BIST Hisse (Yerli)":
                asset_display = asset_display.strip()
                asset_name = asset_display
                ticker = f"{asset_display}.IS"
            elif category == "Yabancı Hisse":
                asset_display = asset_display.strip()
                asset_name = asset_display
                ticker = asset_display
            elif category == "Kripto Para":
                asset_display = asset_display.strip()
                asset_name = asset_display
                ticker = f"{asset_display}-USD"

            new_tx = {
                "id": str(uuid.uuid4())[:8],
                "date": tx_date.strftime("%Y-%m-%d"),
                "type": t_type,
                "asset": ticker,
                "asset_name": asset_name,
                "quantity": quantity,
                "price": price,
                "total": total,
                "payment_type": payment_type if t_type == "Alım" else "tek_seferlik"
            }
            transactions.append(new_tx)
            save_data(f"investments_{current_user}", transactions)

            # Taksitli ise otomatik taksit kaydı oluştur
            if t_type == "Alım" and payment_type == "taksitli" and inst_bank and inst_months >= 2:
                installments = load_data(f"installments_{current_user}")
                monthly_payment = total / inst_months

                selected_card = next((c for c in saved_cards if c.get("bank_name") == inst_bank), None)
                p_day = selected_card.get("payment_day", 1) if selected_card else 1
                first_payment = calc_first_payment_date(tx_date, p_day)

                new_inst = {
                    "id": str(uuid.uuid4())[:8],
                    "item": f"{asset_name} (Yatırım)",
                    "bank": inst_bank,
                    "monthly_payment": monthly_payment,
                    "remaining_months": inst_months,
                    "first_payment_date": first_payment.strftime("%Y-%m-%d"),
                    "total_remaining": total
                }
                installments.append(new_inst)
                save_data(f"installments_{current_user}", installments)

            st.success(f"{asset_name} için {t_type} işlemi kaydedildi!" +
                       (" (Taksit kaydı da oluşturuldu)" if payment_type == "taksitli" else ""))

            clear_form_keys(["qty_input", "cost_input", "fon_input", "bist_input", "yabanci_input", "kripto_input"])
            st.rerun()
        else:
            st.error("Lütfen varlık adını, adedi ve tutarı kontrol edin.")

st.divider()


# --- 2. CANLI VERİ ÇEKME MOTORLARI ---
@st.cache_data(ttl=300)
def get_usd_try():
    try:
        return float(yf.Ticker("TRY=X").history(period="5d")['Close'].dropna().iloc[-1])
    except Exception:
        return 32.0


@st.cache_data(ttl=300)
def get_tefas_price(fon_kodu):
    try:
        url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10, verify=False)

        if response.status_code != 200:
            return -1.0, -1.0

        soup = BeautifulSoup(response.content, "html.parser")
        page_title = soup.title.text if soup.title else ""
        if "Just a moment" in page_title or "Attention Required" in page_title:
            return -1.0, -1.0

        top_list = soup.find("ul", class_="top-list")
        if top_list:
            price_str = top_list.find_all("li")[0].find("span").text.strip()
            price_float = float(price_str.replace('.', '').replace(',', '.'))
            return price_float, price_float
        return -1.0, -1.0
    except Exception:
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
def get_gold_silver_price(ticker):
    if "BANKA" in ticker:
        try:
            usd_try = get_usd_try()
            if "GRAM" in ticker:
                gold_oz = float(yf.Ticker("GC=F").history(period="5d")['Close'].dropna().iloc[-1])
                price = _oz_to_try(gold_oz, usd_try)
                return price, price
            elif "GUMUS" in ticker:
                silver_oz = float(yf.Ticker("SI=F").history(period="5d")['Close'].dropna().iloc[-1])
                price = _oz_to_try(silver_oz, usd_try)
                return price, price
        except Exception:
            pass

    try:
        url = "https://canlidoviz.com/altin-fiyatlari/kapali-carsi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10, verify=False)

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


# --- 3. PORTFÖY HESAPLAMA ---
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

active_assets = []
fon_uyari = False

for a_name, data in portfolio.items():
    if data["qty"] > 0:
        avg_cost = data["total_cost"] / data["qty"]
        alis_fiyati, satis_fiyati = get_current_price(data["ticker"])

        if alis_fiyati == -1.0:
            alis_fiyati = satis_fiyati = avg_cost
            fon_uyari = True

        current_value = data["qty"] * alis_fiyati
        profit_loss = current_value - data["total_cost"]
        profit_loss_pct = (profit_loss / data["total_cost"]) * 100 if data["total_cost"] > 0 else 0

        active_assets.append({
            "Varlık": a_name,
            "Adet": round(data["qty"], 5),
            "Ort. Maliyet (TL)": round(avg_cost, 2),
            "Güncel Alış (TL)": round(alis_fiyati, 6),
            "Güncel Satış (TL)": round(satis_fiyati, 6),
            "Toplam Değer": round(current_value, 2),
            "Kâr/Zarar (TL)": round(profit_loss, 2),
            "Kâr/Zarar (%)": round(profit_loss_pct, 2)
        })

st.markdown("### :material/account_balance_wallet: Anlık Portföy Durumu")

if active_assets:
    df_portfolio = pd.DataFrame(active_assets)

    def color_profit_loss(val):
        color = '#28a745' if val > 0 else '#dc3545' if val < 0 else 'white'
        return f'color: {color}'

    st.dataframe(
        df_portfolio.style.map(color_profit_loss, subset=['Kâr/Zarar (TL)', 'Kâr/Zarar (%)']).format({
            "Ort. Maliyet (TL)": "{:,.2f} ₺",
            "Güncel Alış (TL)": "{:,.6f} ₺",
            "Güncel Satış (TL)": "{:,.6f} ₺",
            "Toplam Değer": "{:,.2f} ₺",
            "Kâr/Zarar (TL)": "{:,.2f} ₺",
            "Kâr/Zarar (%)": "{:,.2f} %"
        }),
        width='stretch',
        hide_index=True
    )

    st.caption(
        "Not: Borsa hisseleri ve yatırım fonlarında alış-satış genellikle tek fiyat (kapanış/anlık fiyat) üzerinden yansıtılır.")

    if fon_uyari:
        st.warning(
            "Bazı Yatırım Fonlarının canlı fiyatı TEFAS bağlantı sorunu nedeniyle çekilemedi. Bu fonlar için yatırdığınız anapara gösterilmektedir.")

    total_investment = sum(item["total_cost"] for item in portfolio.values())
    total_current_value = sum(item["Toplam Değer"] for item in active_assets)
    total_pl = total_current_value - total_investment
    total_pl_pct = (total_pl / total_investment) * 100 if total_investment > 0 else 0

    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Toplam Yatırım Maliyeti", f"{total_investment:,.2f} TL")
    col_p2.metric("Anlık Portföy Büyüklüğü (Bozdurma)", f"{total_current_value:,.2f} TL",
                  delta=f"{total_pl:,.2f} TL ({total_pl_pct:,.2f}%)")
else:
    st.info("Şu an elinizde aktif bir varlık bulunmuyor. Yeni alım girdiğinizde burada listelenecektir.")

st.divider()

# --- 4. İŞLEM GEÇMİŞİ ---
st.markdown("### :material/history: İşlem Geçmişi (Alım - Satım)")

if transactions:
    display_tx = []
    for t in transactions:
        pt = t.get("payment_type", "tek_seferlik")
        odeme = "Taksitli" if pt == "taksitli" else "Tek Seferlik"
        display_tx.append({
            "Tarih": t["date"],
            "İşlem": t["type"],
            "Varlık": t.get("asset_name", t["asset"]),
            "Adet": t["quantity"],
            "Birim Fiyat": t["price"],
            "Toplam": t["total"],
            "Ödeme": odeme
        })

    df_tx = pd.DataFrame(display_tx).sort_values("Tarih", ascending=False)
    st.dataframe(df_tx, width='stretch', hide_index=True)

    with st.expander("Hatalı İşlemi Sil"):
        options = {item["id"]: f"{item['date']} - {item['type']} {item.get('asset_name', item['asset'])} ({item['quantity']} Adet)"
                   for item in reversed(transactions)}
        selected_id = st.selectbox("Silinecek kaydı seçin:", options=list(options.keys()),
                                   format_func=lambda x: options[x])
        if st.button("Seçili İşlemi Sil", type="primary"):
            transactions = [item for item in transactions if item["id"] != selected_id]
            save_data(f"investments_{current_user}", transactions)
            st.success("Kayıt başarıyla silindi.")
            st.rerun()
else:
    st.caption("Henüz bir işlem geçmişi bulunmuyor.")
