import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import uuid
import sys
import os
import urllib3
import re
import hashlib

# SSL Uyarılarını Gizle (Mac/Linux ortamlarında devlet/finans siteleri için gereklidir)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# utils klasöründeki modülleri çağırabilmek için dosya yolunu ayarlıyoruz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data
from utils.auth import check_login

# Sayfa ayarları
st.set_page_config(page_title="Yatırım Portföyü", page_icon="📈", layout="wide")

# --- GİRİŞ KONTROLÜ (TÜM SAYFAYI KORUR) ---
current_user = check_login()

st.title("📈 Yatırım ve Portföy Yönetimi")
st.markdown("""
Sadece yatırım kategorisini seçin ve işlemi girin. Sistem TEFAS fonlarını, hisseleri, kriptoları ve **Kapalıçarşı** altın/gümüş fiyatlarını otomatik olarak bularak portföyünüzü hesaplar. 
*(Yabancı varlıklar ve kriptolar güncel Dolar/TL kuruyla otomatik TL'ye çevrilir. Altın ve gümüş kâr/zarar hesaplamaları "Alış" fiyatı üzerinden yapılır.)*
""")

# Veriyi yükle (Kullanıcıya özel JSON dosyası)
transactions = load_data(f"investments_{current_user}")

# --- 1. AKILLI YENİ İŞLEM EKLEME FORMU ---
with st.expander("➕ Yeni Alım / Satım İşlemi Ekle", expanded=False):
    category = st.selectbox("Yatırım Kategorisi", [
        "Altın / Gümüş",
        "Yatırım Fonu (TEFAS)",
        "BIST Hisse (Yerli)",
        "Yabancı Hisse",
        "Kripto Para"
    ])

    # st.form bloğu kaldırıldı. Artık seçimler arayüzü anında güncelleyecek!
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        t_type = st.selectbox("İşlem Tipi", ["Alım", "Satım"])

    with col2:
        if category == "Altın / Gümüş":
            asset_display = st.selectbox("Varlık Seçin", [
                "Fiziki Gram Altın",
                "Sanal Gram Altın",
                "Fiziki 22 Ayar Altın",
                "Fiziki Gümüş",
                "Sanal Gümüş"
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
        # State karışıklığını önlemek için cost_method'a key atandı
        cost_method = st.selectbox("Fiyat Girişi", ["Birim Maliyet", "Toplam Maliyet"], key="cost_method")
        cost_input = st.number_input(f"{cost_method} (TL)", min_value=0.0, step=10.0, format="%.2f", key="cost_input")

    submitted = st.button("İşlemi Kaydet", type="primary")

    if submitted:
        if asset_display and quantity > 0 and cost_input > 0:

            # Seçilen yönteme göre birim maliyeti hesapla
            price = cost_input if cost_method == "Birim Maliyet" else (cost_input / quantity)

            ticker = ""
            asset_name = ""

            if category == "Altın / Gümüş":
                asset_name = asset_display
                if asset_display == "Fiziki Gram Altın":
                    ticker = "API_GRAM_FIZIKI"
                elif asset_display == "Sanal Gram Altın":
                    ticker = "API_GRAM_BANKA"
                elif asset_display == "Fiziki 22 Ayar Altın":
                    ticker = "API_22_FIZIKI"
                elif asset_display == "Fiziki Gümüş":
                    ticker = "API_GUMUS_FIZIKI"
                elif asset_display == "Sanal Gümüş":
                    ticker = "API_GUMUS_BANKA"
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
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": t_type,
                "asset": ticker,
                "asset_name": asset_name,
                "quantity": quantity,
                "price": price,
                "total": quantity * price
            }
            transactions.append(new_tx)
            save_data(f"investments_{current_user}", transactions)
            st.success(f"{asset_name} için {t_type} işlemi başarıyla kaydedildi!")

            # Form silinme mekanizmasını (clear_on_submit) manuel olarak simüle et
            for key in ["qty_input", "cost_input", "fon_input", "bist_input", "yabanci_input", "kripto_input",
                        "cost_method"]:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()
        else:
            st.error("Lütfen varlık adını, adedi ve tutarı kontrol edin.")

st.divider()


# --- 2. CANLI VERİ ÇEKME MOTORLARI ---
@st.cache_data(ttl=300)
def get_usd_try():
    try:
        # Hafta sonu boş veri gelmesine karşı period="5d" ve dropna() kullanıyoruz
        return float(yf.Ticker("TRY=X").history(period="5d")['Close'].dropna().iloc[-1])
    except:
        return 32.0


@st.cache_data(ttl=300)
def get_tefas_price(fon_kodu):
    """TEFAS web sitesinden güncel fon fiyatını çeker. Fonlarda alış-satış ortaktır."""
    try:
        url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10, verify=False)

        if response.status_code != 200:
            st.sidebar.error(f"DEBUG: TEFAS {fon_kodu} için HTTP {response.status_code} hatası döndürdü.")
            return -1.0, -1.0

        soup = BeautifulSoup(response.content, "html.parser")

        page_title = soup.title.text if soup.title else ""
        if "Just a moment" in page_title or "Attention Required" in page_title:
            st.sidebar.error(f"DEBUG: TEFAS {fon_kodu} bağlantısı Bot Korumasına takıldı.")
            return -1.0, -1.0

        top_list = soup.find("ul", class_="top-list")
        if top_list:
            try:
                price_str = top_list.find_all("li")[0].find("span").text.strip()
                price_float = float(price_str.replace('.', '').replace(',', '.'))
                return price_float, price_float  # Fonlarda alış-satış tek fiyattır
            except Exception as inner_e:
                st.sidebar.error(f"DEBUG: TEFAS {fon_kodu} için fiyat metni parçalanamadı. Hata: {inner_e}")
                return -1.0, -1.0
        else:
            st.sidebar.error(f"DEBUG: TEFAS {fon_kodu} sayfasında 'top-list' bulunamadı.")
            return -1.0, -1.0

    except Exception as e:
        st.sidebar.error(f"DEBUG: TEFAS {fon_kodu} Beklenmeyen Hata: {e}")
        return -1.0, -1.0


def clean_and_parse_price(text):
    """Fiyat metnindeki rakamları ve virgülleri ayrıştırıp float'a çevirir."""
    text = re.sub(r'[^\d.,]', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    return float(text) if text else 0.0


@st.cache_data(ttl=300)
def get_gold_silver_price(ticker):
    """Canlı Döviz (Kapalıçarşı) üzerinden fiziki, YFinance üzerinden sanal (banka) fiyatlarını çeker."""
    # 1. Sanal/Banka Altın ve Gümüş (Spot Küresel Fiyat)
    if "BANKA" in ticker:
        try:
            usd_try = get_usd_try()
            if "GRAM" in ticker:
                try:
                    # Yfinance hata vermemesi için period genişletildi ve boş günler filtrelendi
                    gold_oz = float(yf.Ticker("XAUUSD=X").history(period="5d")['Close'].dropna().iloc[-1])
                except:
                    gold_oz = float(yf.Ticker("GC=F").history(period="5d")['Close'].dropna().iloc[-1])
                price = (gold_oz / 31.103) * usd_try
                return price, price
            elif "GUMUS" in ticker:
                try:
                    silver_oz = float(yf.Ticker("XAGUSD=X").history(period="5d")['Close'].dropna().iloc[-1])
                except:
                    silver_oz = float(yf.Ticker("SI=F").history(period="5d")['Close'].dropna().iloc[-1])
                price = (silver_oz / 31.103) * usd_try
                return price, price
        except:
            pass  # HATA VERME, 0 DÖNME. YFinance çökerse CanlıDöviz'deki fiziki fiyata (fallback) geçiş yapacak!

    # 2. Fiziki Altın ve Gümüş (Kapalıçarşı)
    try:
        url = "https://canlidoviz.com/altin-fiyatlari/kapali-carsi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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
                        # 1. Sütun Alış, 2. Sütun Satış
                        alis_raw = tds[1].text.strip()
                        satis_raw = tds[2].text.strip()

                        # İçerisinde "0.00 %0.00" gibi değişim oranları olduğu için ilk parçayı alırız
                        alis_text = alis_raw.split()[0] if alis_raw else ""
                        satis_text = satis_raw.split()[0] if satis_raw else ""

                        alis_float = clean_and_parse_price(alis_text)
                        satis_float = clean_and_parse_price(satis_text)

                        return alis_float, satis_float
        else:
            st.sidebar.error(f"DEBUG: CanlıDöviz HTTP {response.status_code} hatası.")

    except Exception as e:
        st.sidebar.error(f"DEBUG: CanlıDöviz Bağlantı Hatası: {e}. YFinance yedeğine geçiliyor.")
        pass

    # Yfinance Yedek Planı (API Çökerse Ons üzerinden hesaplar, alış-satış tek fiyat döner)
    try:
        usd_try = get_usd_try()
        if "GRAM" in ticker:
            gold_oz = float(yf.Ticker("XAUUSD=X").history(period="5d")['Close'].dropna().iloc[-1])
            price = (gold_oz / 31.103) * usd_try
            return price, price
        elif "22" in ticker:
            gold_oz = float(yf.Ticker("XAUUSD=X").history(period="5d")['Close'].dropna().iloc[-1])
            price = ((gold_oz / 31.103) * usd_try) * 0.916
            return price, price
        elif "GUMUS" in ticker:
            silver_oz = float(yf.Ticker("XAGUSD=X").history(period="5d")['Close'].dropna().iloc[-1])
            price = (silver_oz / 31.103) * usd_try
            return price, price
    except:
        return 0.0, 0.0

    return 0.0, 0.0


@st.cache_data(ttl=300)
def get_current_price(ticker):
    """Varlık tipine göre ilgili robottan canlı alış ve satış fiyatlarını (Tuple) alır."""
    if ticker.endswith("_FON"):
        fon_kodu = ticker.replace("_FON", "")
        return get_tefas_price(fon_kodu)

    if ticker.startswith("API_") or ticker in ["HAREM_GRAM", "GRAM_ALTIN", "HAREM_22", "HAREM_GUMUS", "GRAM_GUMUS"]:
        return get_gold_silver_price(ticker)

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")  # Boş günleri atlamak için genişletildi
        if not hist.empty:
            price = float(hist['Close'].dropna().iloc[-1])
            if ticker.endswith("-USD") or not ticker.endswith(".IS"):
                price = price * get_usd_try()
            return price, price  # Hisse/Kriptoda şimdilik alış/satış ortaktır
        return 0.0, 0.0
    except:
        return 0.0, 0.0


# --- 3. PORTFÖY HESAPLAMA ---
portfolio = {}
for t in transactions:
    a_ticker = t["asset"]
    a_name = t.get("asset_name", a_ticker)

    qty = t["quantity"]
    price = t["price"]

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

        # DİKKAT: Toplam Değer ve Kâr/Zarar artık eldeki varlık BOZDURULDUĞUNDA
        # geçerli olacak olan ALIŞ FİYATI üzerinden hesaplanır.
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

st.markdown("### 💼 Anlık Portföy Durumu")

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
            "⚠️ Bazı Yatırım Fonlarının canlı fiyatı TEFAS bağlantı sorunu nedeniyle çekilemedi. Bu fonlar için yatırdığınız anapara gösterilmektedir.")

    total_investment = sum(item["total_cost"] for item in portfolio.values())
    total_current_value = sum(item["Toplam Değer"] for item in active_assets)
    total_pl = total_current_value - total_investment

    col_p1, col_p2, col_p3 = st.columns(3)
    col_p1.metric("Toplam Yatırım Maliyeti", f"{total_investment:,.2f} TL")
    col_p2.metric("Anlık Portföy Büyüklüğü (Bozdurma)", f"{total_current_value:,.2f} TL", delta=f"{total_pl:,.2f} TL")

else:
    st.info("Şu an elinizde aktif bir varlık bulunmuyor. Yeni alım girdiğinizde burada listelenecektir.")

st.divider()

# --- 4. İŞLEM GEÇMİŞİ (ARŞİV) ---
st.markdown("### 📜 İşlem Geçmişi (Alım - Satım)")

if transactions:
    display_tx = []
    for t in transactions:
        display_tx.append({
            "Tarih": t["date"],
            "İşlem": t["type"],
            "Varlık": t.get("asset_name", t["asset"]),
            "Adet": t["quantity"],
            "Birim Fiyat": t["price"],
            "İşlem Hacmi": t["total"]
        })

    df_tx = pd.DataFrame(display_tx).sort_index(ascending=False)

    st.dataframe(
        df_tx,
        width='stretch',
        hide_index=True
    )

    with st.expander("Hatalı İşlemi Sil"):
        options = {item[
                       "id"]: f"{item['date']} - {item['type']} {item.get('asset_name', item['asset'])} ({item['quantity']} Adet)"
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