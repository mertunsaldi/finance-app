import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
import uuid
from utils.data_handler import load_data, save_data
from utils.finance import FREQUENCY_OPTIONS, DAY_TYPE_OPTIONS, MONTH_NAMES_FULL, clear_form_keys, format_day_type

from utils.auth import check_login
check_login()
current_user = st.session_state["logged_in_user"]

st.title(":material/attach_money: Gelir Yönetimi")
st.markdown("Düzenli ve düzensiz gelirlerinizi buradan yönetebilirsiniz. Dashboard projeksiyonları bu verilere göre hesaplanır.")

regular_incomes = load_data(f"regular_income_{current_user}")
irregular_incomes = load_data(f"irregular_income_{current_user}")

# --- 1. DÜZENLİ GELİRLER ---
st.markdown("### :material/event_repeat: Düzenli Gelirler")
st.caption("Maaş, kira geliri, düzenli yan gelir gibi tekrarlayan gelirleri ekleyin.")

with st.expander(":material/add: Yeni Düzenli Gelir Ekle", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        reg_name = st.text_input("Gelir Adı (Örn: Maaş, Kira Geliri)", key="reg_name")
        reg_amount = st.number_input("Tutar (TL)", min_value=0.0, step=500.0, key="reg_amount")
        reg_frequency = st.selectbox("Tekrar Sıklığı", FREQUENCY_OPTIONS, key="reg_frequency")

    with col2:
        reg_day_type_label = st.selectbox("Ödeme Günü Tipi", list(DAY_TYPE_OPTIONS.keys()), key="reg_day_type")
        reg_day_type = DAY_TYPE_OPTIONS[reg_day_type_label]

        reg_day = 1
        if reg_day_type == "specific":
            reg_day = st.number_input("Ayın Kaçıncı Günü", min_value=1, max_value=31, value=15, step=1, key="reg_day")

        # Aylık olmayan frekanslarda başlangıç ayı gerekli
        reg_start_month = 1
        if reg_frequency != "Aylık":
            reg_start_month = st.selectbox(
                "İlk Ödeme Ayı",
                range(1, 13),
                format_func=lambda x: MONTH_NAMES_FULL[x - 1],
                key="reg_start_month",
                help="Bu geliri ilk aldığınız ay. Örn: 3 ayda bir Mart'ta alıyorsanız Mart seçin. Sistem bu aydan itibaren sıklığa göre hesaplar."
            )

    if st.button("Düzenli Geliri Kaydet", type="primary", key="save_regular"):
        if reg_name and reg_amount > 0:
            new_income = {
                "id": str(uuid.uuid4())[:8],
                "name": reg_name.strip(),
                "amount": reg_amount,
                "frequency": reg_frequency,
                "day_type": reg_day_type,
                "day": reg_day,
                "start_month": reg_start_month
            }
            regular_incomes.append(new_income)
            save_data(f"regular_income_{current_user}", regular_incomes)
            st.success(f"'{reg_name}' başarıyla eklendi!")
            for key in ["reg_name", "reg_amount"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        else:
            st.error("Lütfen gelir adını ve tutarı giriniz.")

# Düzenli gelirleri listele
if regular_incomes:
    display_data = []
    for inc in regular_incomes:
        day_str = format_day_type(inc["day_type"], inc.get("day"))

        freq = inc["frequency"]
        if freq != "Aylık":
            freq += f" ({MONTH_NAMES_FULL[inc['start_month'] - 1]}'dan itibaren)"

        display_data.append({
            "Gelir Adı": inc["name"],
            "Tutar (TL)": inc["amount"],
            "Sıklık": freq,
            "Ödeme Günü": day_str
        })

    st.dataframe(pd.DataFrame(display_data), width="stretch", hide_index=True)

    # Toplam aylık gelir tahmini
    monthly_estimate = sum(
        inc["amount"] / (int(inc["frequency"].split()[0]) if inc["frequency"] != "Aylık" and inc["frequency"] != "Yıllık" else (1 if inc["frequency"] == "Aylık" else 12))
        for inc in regular_incomes
    )
    st.metric("Aylık Ortalama Düzenli Gelir Tahmini", f"{monthly_estimate:,.0f} TL")

    # Silme
    with st.expander(":material/delete: Düzenli Gelir Sil"):
        options = {inc["id"]: f"{inc['name']} - {inc['amount']:,.0f} TL ({inc['frequency']})" for inc in regular_incomes}
        selected_id = st.selectbox("Silinecek geliri seçin:", options=list(options.keys()),
                                   format_func=lambda x: options[x], key="del_regular")
        if st.button("Seçili Geliri Sil", type="primary", key="btn_del_regular"):
            regular_incomes = [inc for inc in regular_incomes if inc["id"] != selected_id]
            save_data(f"regular_income_{current_user}", regular_incomes)
            st.success("Gelir kaydı silindi.")
            st.rerun()
else:
    st.info("Henüz düzenli gelir eklenmemiş. Yukarıdan ekleyebilirsiniz.")

st.divider()

# --- 2. DÜZENSİZ GELİRLER ---
st.markdown("### :material/payments: Düzensiz / Tek Seferlik Gelirler")
st.caption("Freelance, ikramiye, hediye gibi tek seferlik gelirleri ekleyin.")

with st.expander(":material/add: Yeni Düzensiz Gelir Ekle", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        irr_name = st.text_input("Açıklama (Örn: Freelance proje)", key="irr_name")
    with col2:
        irr_amount = st.number_input("Tutar (TL)", min_value=0.0, step=500.0, key="irr_amount")
    with col3:
        irr_date = st.date_input("Tarih", value=date.today(), key="irr_date")

    if st.button("Düzensiz Geliri Kaydet", type="primary", key="save_irregular"):
        if irr_name and irr_amount > 0:
            new_irr = {
                "id": str(uuid.uuid4())[:8],
                "name": irr_name.strip(),
                "amount": irr_amount,
                "date": irr_date.strftime("%Y-%m-%d")
            }
            irregular_incomes.append(new_irr)
            save_data(f"irregular_income_{current_user}", irregular_incomes)
            st.success(f"'{irr_name}' başarıyla eklendi!")
            for key in ["irr_name", "irr_amount"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        else:
            st.error("Lütfen açıklama ve tutarı giriniz.")

if irregular_incomes:
    display_irr = []
    for inc in irregular_incomes:
        display_irr.append({
            "Açıklama": inc["name"],
            "Tutar (TL)": inc["amount"],
            "Tarih": inc["date"]
        })

    df_irr = pd.DataFrame(display_irr).sort_values("Tarih", ascending=False)
    st.dataframe(df_irr, width="stretch", hide_index=True)

    total_irr = sum(inc["amount"] for inc in irregular_incomes)
    st.metric("Toplam Düzensiz Gelir", f"{total_irr:,.0f} TL")

    # Silme
    with st.expander(":material/delete: Düzensiz Gelir Sil"):
        options_irr = {inc["id"]: f"{inc['date']} - {inc['name']} ({inc['amount']:,.0f} TL)" for inc in irregular_incomes}
        selected_irr_id = st.selectbox("Silinecek geliri seçin:", options=list(options_irr.keys()),
                                       format_func=lambda x: options_irr[x], key="del_irregular")
        if st.button("Seçili Geliri Sil", type="primary", key="btn_del_irregular"):
            irregular_incomes = [inc for inc in irregular_incomes if inc["id"] != selected_irr_id]
            save_data(f"irregular_income_{current_user}", irregular_incomes)
            st.success("Gelir kaydı silindi.")
            st.rerun()
else:
    st.info("Henüz düzensiz gelir eklenmemiş.")
