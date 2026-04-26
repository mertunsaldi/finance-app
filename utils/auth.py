import streamlit as st
import hashlib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_login():
    """Kullanıcının giriş yapıp yapmadığını kontrol eder."""

    current_user = st.session_state.get("logged_in_user")
    if current_user:
        return current_user

    # Giriş yapılmamış — login formu göster
    st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

    st.title(":material/lock: Giriş Yap")
    st.markdown("Sistemi kullanmak için giriş yapın veya yeni bir hesap oluşturun.")

    tab1, tab2 = st.tabs(["Giriş Yap", "Yeni Hesap Oluştur"])

    with tab1:
        with st.form("login_form"):
            login_username = st.text_input("Kullanıcı Adı")
            login_password = st.text_input("Şifre", type="password")
            submit_login = st.form_submit_button("Giriş Yap", type="primary")

        if submit_login:
            users = load_data("users")
            user_found = next(
                (u for u in users if
                 u.get("username") == login_username and
                 u.get("password") == hash_password(login_password)),
                None
            )
            if user_found:
                st.session_state["logged_in_user"] = login_username
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

    with tab2:
        with st.form("register_form"):
            reg_username = st.text_input("Kullanıcı Adı Seçin")
            reg_password = st.text_input("Şifre Belirleyin", type="password")
            submit_reg = st.form_submit_button("Kayıt Ol", type="primary")

        if submit_reg:
            users = load_data("users")
            if any(u.get("username") == reg_username for u in users):
                st.error("Bu kullanıcı adı zaten kullanılıyor. Lütfen başka bir tane seçin.")
            elif len(reg_username) < 3 or len(reg_password) < 3:
                st.error("Kullanıcı adı ve şifre en az 3 karakter olmalıdır.")
            else:
                users.append({"username": reg_username, "password": hash_password(reg_password)})
                save_data("users", users)
                st.success("Hesabınız oluşturuldu! Şimdi 'Giriş Yap' sekmesinden giriş yapabilirsiniz.")

    st.stop()


def show_sidebar_user():
    """Sidebar'da aktif kullanıcı ve çıkış butonu gösterir."""
    current_user = st.session_state.get("logged_in_user")
    if not current_user:
        return

    st.sidebar.markdown(f":material/person: **{current_user}**")
    if st.sidebar.button(":material/logout: Çıkış Yap", key="logout_btn"):
        st.session_state.clear()
        st.rerun()
