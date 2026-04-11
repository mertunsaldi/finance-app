import streamlit as st
import pandas as pd
import uuid
from datetime import date
from utils.data_handler import load_data, save_data
from utils.finance import DAY_TYPE_OPTIONS, clear_form_keys, format_day_type

from utils.auth import check_login
check_login()
current_user = st.session_state["logged_in_user"]

st.title(":material/receipt_long: Gider Yönetimi")
st.markdown("Tek seferlik ve düzenli giderlerinizi buradan yönetebilirsiniz.")

expenses = load_data(f"expenses_{current_user}")
irregular_expenses = load_data(f"irregular_expenses_{current_user}")

# --- 1. TEK SEFERLİK GİDERLER ---
st.markdown("### :material/shopping_cart: Tek Seferlik Giderler")
st.caption("Beklenmedik harcamalar, tamir, alışveriş gibi tek seferlik giderleri ekleyin.")

with st.expander(":material/add: Yeni Tek Seferlik Gider Ekle", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        irr_exp_name = st.text_input("Açıklama (Örn: Araba tamiri)", key="irr_exp_name")
    with col2:
        irr_exp_amount = st.number_input("Tutar (TL)", min_value=0.0, step=100.0, key="irr_exp_amount")
    with col3:
        irr_exp_date = st.date_input("Tarih", value=date.today(), key="irr_exp_date")

    if st.button("Tek Seferlik Gideri Kaydet", type="primary", key="save_irr_expense"):
        if irr_exp_name and irr_exp_amount > 0:
            new_irr_exp = {
                "id": str(uuid.uuid4())[:8],
                "name": irr_exp_name.strip(),
                "amount": irr_exp_amount,
                "date": irr_exp_date.strftime("%Y-%m-%d")
            }
            irregular_expenses.append(new_irr_exp)
            save_data(f"irregular_expenses_{current_user}", irregular_expenses)
            st.success(f"'{irr_exp_name}' başarıyla eklendi!")
            for key in ["irr_exp_name", "irr_exp_amount"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        else:
            st.error("Lütfen açıklama ve tutarı giriniz.")

if irregular_expenses:
    display_irr_exp = []
    for exp in irregular_expenses:
        display_irr_exp.append({
            "Açıklama": exp["name"],
            "Tutar (TL)": exp["amount"],
            "Tarih": exp["date"]
        })

    df_irr_exp = pd.DataFrame(display_irr_exp).sort_values("Tarih", ascending=False)
    st.dataframe(df_irr_exp, width="stretch", hide_index=True)

    total_irr_exp = sum(exp["amount"] for exp in irregular_expenses)
    st.metric("Toplam Tek Seferlik Gider", f"{total_irr_exp:,.0f} TL")

    with st.expander(":material/delete: Tek Seferlik Gider Sil"):
        options_irr_exp = {exp["id"]: f"{exp['date']} - {exp['name']} ({exp['amount']:,.0f} TL)" for exp in irregular_expenses}
        selected_irr_exp_id = st.selectbox("Silinecek gideri seçin:", options=list(options_irr_exp.keys()),
                                           format_func=lambda x: options_irr_exp[x], key="del_irr_expense")
        if st.button("Seçili Gideri Sil", type="primary", key="btn_del_irr_expense"):
            irregular_expenses = [exp for exp in irregular_expenses if exp["id"] != selected_irr_exp_id]
            save_data(f"irregular_expenses_{current_user}", irregular_expenses)
            st.success("Gider kaydı silindi.")
            st.rerun()
else:
    st.info("Henüz tek seferlik gider eklenmemiş.")

st.divider()

# --- 2. DÜZENLİ GİDERLER ---
st.markdown("### :material/event_repeat: Düzenli Giderler")
st.caption("Kira, fatura, abonelik gibi her ay tekrarlayan sabit giderlerinizi ekleyin.")

with st.expander(":material/add: Yeni Düzenli Gider Ekle", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        exp_name = st.text_input("Gider Adı (Örn: Kira, Elektrik, Netflix)", key="exp_name")
    with col2:
        exp_amount = st.number_input("Aylık Tutar (TL)", min_value=0.0, step=100.0, key="exp_amount")
    with col3:
        exp_day_type_label = st.selectbox("Ödeme Günü Tipi", list(DAY_TYPE_OPTIONS.keys()), key="exp_day_type")
        exp_day_type = DAY_TYPE_OPTIONS[exp_day_type_label]

        exp_day = 1
        if exp_day_type == "specific":
            exp_day = st.number_input("Ayın Kaçıncı Günü", min_value=1, max_value=31, value=1, step=1, key="exp_day")

    if st.button("Gideri Kaydet", type="primary", key="save_expense"):
        if exp_name and exp_amount > 0:
            new_expense = {
                "id": str(uuid.uuid4())[:8],
                "name": exp_name.strip(),
                "amount": exp_amount,
                "day_type": exp_day_type,
                "day": exp_day
            }
            expenses.append(new_expense)
            save_data(f"expenses_{current_user}", expenses)
            st.success(f"'{exp_name}' başarıyla eklendi!")
            for key in ["exp_name", "exp_amount"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        else:
            st.error("Lütfen gider adını ve tutarı giriniz.")

# --- DÜZENLİ GİDER LİSTESİ ---
if expenses:
    display_data = []
    for exp in expenses:
        day_str = format_day_type(exp["day_type"], exp.get("day"))

        display_data.append({
            "Gider Adı": exp["name"],
            "Aylık Tutar (TL)": exp["amount"],
            "Ödeme Günü": day_str
        })

    st.dataframe(pd.DataFrame(display_data), width="stretch", hide_index=True)

    # Toplam
    total_expenses = sum(exp["amount"] for exp in expenses)
    st.metric("Toplam Aylık Sabit Gider", f"{total_expenses:,.0f} TL")

    # Silme
    with st.expander(":material/delete: Düzenli Gider Sil"):
        options = {exp["id"]: f"{exp['name']} - {exp['amount']:,.0f} TL" for exp in expenses}
        selected_id = st.selectbox("Silinecek gideri seçin:", options=list(options.keys()),
                                   format_func=lambda x: options[x], key="del_expense")
        if st.button("Seçili Gideri Sil", type="primary", key="btn_del_expense"):
            expenses = [exp for exp in expenses if exp["id"] != selected_id]
            save_data(f"expenses_{current_user}", expenses)
            st.success("Gider kaydı silindi.")
            st.rerun()
else:
    st.info("Henüz düzenli gider eklenmemiş. Yukarıdan ekleyebilirsiniz.")
