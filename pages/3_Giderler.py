import streamlit as st
import pandas as pd
import uuid
from utils.data_handler import load_data, save_data
from utils.finance import DAY_TYPE_OPTIONS, clear_form_keys, format_day_type

current_user = st.session_state["logged_in_user"]

st.title(":material/receipt_long: Düzenli Gider Yönetimi")
st.markdown("Kira, fatura, abonelik gibi her ay tekrarlayan sabit giderlerinizi buradan yönetebilirsiniz.")

expenses = load_data(f"expenses_{current_user}")

# --- 1. YENİ GİDER EKLEME ---
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

# --- 2. GİDER LİSTESİ ---
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
    with st.expander(":material/delete: Gider Sil"):
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
