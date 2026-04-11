import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
import uuid

from utils.data_handler import load_data, save_data
from utils.finance import calc_first_payment_date, clear_form_keys
from utils.prices import get_current_price, fetch_all_prices, build_portfolio

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


# --- 2. PORTFÖY HESAPLAMA ---
portfolio = build_portfolio(transactions)

active = {name: data for name, data in portfolio.items() if data["qty"] > 0}
prices = fetch_all_prices([data["ticker"] for data in active.values()]) if active else {}

active_assets = []
fon_uyari = False

for a_name, data in active.items():
    avg_cost = data["total_cost"] / data["qty"]
    alis_fiyati, satis_fiyati = prices[data["ticker"]]

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

st.markdown(
    "<div style='text-align:center; color:rgba(150,150,150,0.45); font-size:0.7rem; margin-top:3rem;'>"
    "Sanal altın/gümüş: <a href='https://www.yapikredi.com.tr/yatirimci-kosesi/doviz-bilgileri' style='color:inherit'>Yapı Kredi</a> · "
    "Fiziki altın/gümüş: <a href='https://canlidoviz.com/altin-fiyatlari/kapali-carsi' style='color:inherit'>CanlıDöviz</a> · "
    "BIST & kripto & döviz: <a href='https://finance.yahoo.com' style='color:inherit'>Yahoo Finance</a> · "
    "Yatırım fonları: <a href='https://fundturkey.com.tr' style='color:inherit'>TEFAS</a>"
    "</div>",
    unsafe_allow_html=True
)
