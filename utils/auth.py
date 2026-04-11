import streamlit as st
import hashlib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _set_cookie(name, value, max_age=30 * 24 * 60 * 60):
    """Tarayıcıya cookie yazar (JS ile, bileşen gerektirmez)."""
    import re
    safe_value = re.sub(r'[^a-zA-Z0-9_\-.]', '', str(value))
    st.html(f"""
        <script>
        document.cookie = "{name}={safe_value}; path=/; max-age={max_age}; SameSite=Lax";
        </script>
    """)


def _delete_cookie(name):
    """Tarayıcıdan cookie siler."""
    st.html(f"""
        <script>
        document.cookie = "{name}=; path=/; max-age=0; SameSite=Lax";
        </script>
    """)


def check_login():
    """Kullanıcının giriş yapıp yapmadığını kontrol eder."""

    # 1) Session'da zaten login varsa — anında geç
    current_user = st.session_state.get("logged_in_user")
    if current_user:
        return current_user

    # 2) Cookie'den oku (st.context.cookies — yerleşik, JS bileşeni yok, anında)
    cookie_user = st.context.cookies.get("current_user")
    if cookie_user:
        st.session_state["logged_in_user"] = cookie_user
        return cookie_user

    # 3) Giriş yapılmamış — login formu göster
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
            submit_login = st.form_submit_button("Giriş Yap")

            if submit_login:
                users = load_data("users")
                user_found = next((u for u in users if
                                   u.get("username") == login_username and u.get("password") == hash_password(
                                       login_password)), None)

                if user_found:
                    st.session_state["logged_in_user"] = login_username
                    _set_cookie("current_user", login_username)
                    st.success("Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")

    with tab2:
        with st.form("register_form"):
            reg_username = st.text_input("Kullanıcı Adı Seçin")
            reg_password = st.text_input("Şifre Belirleyin", type="password")
            submit_reg = st.form_submit_button("Kayıt Ol")

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
        # Kullanıcı veri cache'ini temizle
        keys_to_clear = [k for k in st.session_state if k.startswith("_data_")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.session_state["logged_in_user"] = None
        _delete_cookie("current_user")
        st.rerun()
