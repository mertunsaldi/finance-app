import streamlit as st
import extra_streamlit_components as stx
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from utils.auth import check_login, show_sidebar_user
from utils.data_handler import preload_data

st.set_page_config(page_title="Finansal Dashboard", page_icon=":material/monitoring:", layout="wide")

# CookieManager — script run başına tek instance
cookie_manager = stx.CookieManager(key="auth_cookie_manager")

# Auth
check_login(cookie_manager)
show_sidebar_user(cookie_manager)

# Tüm kullanıcı verisini paralel preload
current_user = st.session_state["logged_in_user"]
preload_data([
    f"installments_{current_user}",
    f"investments_{current_user}",
    f"regular_income_{current_user}",
    f"irregular_income_{current_user}",
    f"expenses_{current_user}",
    f"cards_{current_user}",
])

pages = st.navigation([
    st.Page("pages/1_Dashboard.py", title="Ana Sayfa", icon=":material/home:"),
    st.Page("pages/2_Gelirler.py", title="Gelirler", icon=":material/attach_money:"),
    st.Page("pages/3_Giderler.py", title="Giderler", icon=":material/receipt_long:"),
    st.Page("pages/4_Taksitler.py", title="Taksitler", icon=":material/credit_card:"),
    st.Page("pages/5_Yatırımlar.py", title="Yatırımlar", icon=":material/trending_up:"),
])

pages.run()
