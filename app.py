import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import calendar
import sys
import os

# utils klasöründeki modülleri çağırabilmek için dosya yolunu (kök dizin) ayarlıyoruz
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from utils.data_handler import load_data
from utils.auth import check_login

# Sayfa ayarları (İlk Streamlit komutu olmalı)
st.set_page_config(page_title="Finansal Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# --- GİRİŞ KONTROLÜ (TÜM SİSTEMİ KORUR) ---
current_user = check_login()

# Giriş yapıldıysa Dashboard içeriğini göster
st.title("📊 Finansal Kontrol Paneli")
st.markdown("Gelir, gider ve yatırım durumunuzun büyük resmi.")

# Verileri Yükle (Aktif kullanıcıya özel veriler)
installments = load_data(f"installments_{current_user}")
investments = load_data(f"investments_{current_user}")

# --- 1. SOL MENÜ: GELİR VE SABİT GİDER GİRİŞİ ---
st.sidebar.header("⚙️ Bütçe Ayarları")
st.sidebar.markdown("Projeksiyon hesaplaması için tahmini değerleri girin:")
monthly_income = st.sidebar.number_input("Tahmini Aylık Gelir (TL)", min_value=0, value=60000, step=1000)
fixed_expenses = st.sidebar.number_input("Sabit Giderler (Kira, Fatura vb.)", min_value=0, value=20000, step=1000)

# --- 2. HIZLI ÖZET KARTLARI (METRİKLER) ---
# Taksit Toplamlarını Hesapla
total_active_debt = sum(item["total_remaining"] for item in installments)
current_month_load = 0

# Bu ayki taksit yükünü bul
now = datetime.now()
for inst in installments:
    start_date = datetime.strptime(inst["first_payment_date"], "%Y-%m-%d")
    diff_months = (now.year - start_date.year) * 12 + (now.month - start_date.month)
    if 0 <= diff_months < inst["remaining_months"]:
        current_month_load += inst["monthly_payment"]

# Toplam Yatırım Maliyetini Hesapla (Alım - Satım)
total_investment_cost = 0
for t in investments:
    if t["type"] == "Alım":
        total_investment_cost += t["total"]
    elif t["type"] == "Satım":
        total_investment_cost -= t["total"]

if total_investment_cost < 0:
    total_investment_cost = 0

# Kartları Çiz
col1, col2, col3 = st.columns(3)
col1.metric("💰 Toplam Yatırım (Maliyet)", f"{total_investment_cost:,.0f} TL")
col2.metric("💳 Kalan Toplam Taksit Borcu", f"{total_active_debt:,.0f} TL")
col3.metric("🔥 Bu Ayki Taksit Yükü", f"{current_month_load:,.0f} TL",
            delta=f"Net Kalan: {(monthly_income - fixed_expenses - current_month_load):,.0f} TL", delta_color="normal")

st.divider()

# --- 3. GELECEK 6 AYIN PROJEKSİYONU (BAR CHART) ---
st.markdown("### 🔭 6 Aylık Harcanabilir Nakit Projeksiyonu")
st.caption("Aylık Gelir - (Sabit Giderler + O Ayki Taksitler) formülüyle hesaplanmıştır.")

months_data = []
month_names = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

for i in range(6):
    target_month = (now.month + i - 1) % 12 + 1
    target_year = now.year + (now.month + i - 1) // 12
    label = f"{month_names[target_month - 1]} {target_year}"

    # O ayki taksit yükünü hesapla
    month_load = 0
    for inst in installments:
        start_date = datetime.strptime(inst["first_payment_date"], "%Y-%m-%d")
        diff_months = (target_year - start_date.year) * 12 + (target_month - start_date.month)
        if 0 <= diff_months < inst["remaining_months"]:
            month_load += inst["monthly_payment"]

    net_cash = monthly_income - fixed_expenses - month_load

    months_data.append({
        "Ay": label,
        "Net Harcanabilir": net_cash,
        "Taksit Yükü": month_load
    })

df_proj = pd.DataFrame(months_data)

# Sütun Grafik (Plotly)
fig_bar = px.bar(
    df_proj,
    x="Ay",
    y=["Net Harcanabilir", "Taksit Yükü"],
    title="Gelecek Aylardaki Bütçe Durumu",
    barmode="stack",
    color_discrete_sequence=["#2ca02c", "#d62728"],  # Yeşil (Net) ve Kırmızı (Borç)
    labels={"value": "Tutar (TL)", "variable": "Kalem"}
)
fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig_bar, width='stretch')

st.divider()

# --- 4. PORTFÖY DAĞILIMI (PIE CHART) ---
st.markdown("### 🍰 Yatırım Dağılımı (Maliyet Bazlı)")

# Varlıkları topla (Alım ve satımlara göre net maliyet hesapla)
portfolio_summary = {}
for t in investments:
    asset = t.get("asset_name", t["asset"])
    if asset not in portfolio_summary:
        portfolio_summary[asset] = 0.0

    if t["type"] == "Alım":
        portfolio_summary[asset] += t["total"]
    elif t["type"] == "Satım":
        portfolio_summary[asset] -= t["total"]

# Sıfır veya eksi olanları (tamamen satılmışları) filtrele
active_portfolio = {k: v for k, v in portfolio_summary.items() if v > 1}

if active_portfolio:
    df_pie = pd.DataFrame({
        "Varlık": list(active_portfolio.keys()),
        "Tutar": list(active_portfolio.values())
    })

    fig_pie = px.pie(
        df_pie,
        names="Varlık",
        values="Tutar",
        hole=0.4,  # Ortasını delik yaparak şık bir 'donut' grafiği
        title="Yatırımların Maliyet Bazlı Oranları",
        color_discrete_sequence=px.colors.sequential.Teal
    )
    st.plotly_chart(fig_pie, width='stretch')
else:
    st.info("Portföyünüzde henüz aktif bir yatırım bulunmuyor.")