import streamlit as st
import hashlib
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_login(cookie_manager=None):
    """Kullanıcının giriş yapıp yapmadığını kontrol eder.
    cookie_manager: app.py'den geçirilen CookieManager nesnesi.
    Pages'dan çağrıldığında None olur — session state fast path'e düşer.
    """

    # 1) Session'da zaten login varsa — anında geç
    current_user = st.session_state.get("logged_in_user")
    if current_user:
        return current_user

    # 2) Cookie'den oku (CookieManager gerekli)
    if cookie_manager is not None:
        cookies = cookie_manager.get_all()
        cookie_user = cookies.get("current_user") if cookies else None

        if cookie_user:
            st.session_state["logged_in_user"] = cookie_user
            return cookie_user

        # CookieManager ilk renderda boş döner (bileşen henüz yüklenmedi).
        # Bir kez sessiz rerun yap — ikinci renderda gerçek cookie'ler gelir.
        if "_cookies_checked" not in st.session_state:
            st.session_state["_cookies_checked"] = True
            st.stop()

    # 3) cookie_manager yoksa (sayfa doğrudan çalıştı) — login'e yönlendir
    if cookie_manager is None:
        st.warning("Oturum bulunamadı. Lütfen ana sayfadan giriş yapın.")
        st.stop()

    # 4) Giriş yapılmamış — login formu göster
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
                    cookie_manager.set("current_user", login_username, max_age=30 * 24 * 60 * 60)
                    time.sleep(0.5)
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


def show_sidebar_user(cookie_manager=None):
    """Sidebar'da aktif kullanıcı ve çıkış butonu gösterir."""
    current_user = st.session_state.get("logged_in_user")
    if not current_user:
        return

    st.sidebar.markdown(f":material/person: **{current_user}**")
    if st.sidebar.button(":material/logout: Çıkış Yap", key="logout_btn"):
        keys_to_clear = [k for k in st.session_state if k.startswith("_data_")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.session_state["logged_in_user"] = None
        if cookie_manager is not None:
            cookie_manager.delete("current_user")
            time.sleep(0.5)
        st.rerun()
