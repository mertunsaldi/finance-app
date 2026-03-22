import streamlit as st
import extra_streamlit_components as stx
import hashlib
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_login():
    """Kullanıcının giriş yapıp yapmadığını kontrol eder. Yapmadıysa giriş formunu gösterip sayfayı durdurur."""

    # Cache (Önbellek) kullanmıyoruz ki çerez okuyucu her yeniden yüklemede aktif kalsın
    cookie_manager = stx.CookieManager(key="auth_cookie_manager")

    # Çerezleri get_all() ile toplu çekmek ilk sayfa yüklemesinde daha stabil çalışır
    cookies = cookie_manager.get_all()
    cookie_user = cookies.get("current_user") if cookies else None

    # Eğer oturum (session) boşsa ama tarayıcıda kayıtlı çerez varsa, otomatik giriş yap
    if "logged_in_user" not in st.session_state or st.session_state["logged_in_user"] is None:
        st.session_state["logged_in_user"] = cookie_user

    current_user = st.session_state.get("logged_in_user")

    if not current_user:
        # Kullanıcı giriş yapmadıysa sol menüyü (sidebar) tamamen GİZLE
        st.markdown("""
        <style>
            [data-testid="collapsedControl"] { display: none; }
            [data-testid="stSidebar"] { display: none; }
        </style>
        """, unsafe_allow_html=True)

        st.title("🔐 Giriş Yap")
        st.markdown("Sistemi kullanmak için giriş yapın veya yeni bir hesap oluşturun.")

        tab1, tab2 = st.tabs(["Giriş Yap", "Yeni Hesap Oluştur"])

        with tab1:
            with st.form("login_form"):
                login_username = st.text_input("Kullanıcı Adı")
                login_password = st.text_input("Şifre", type="password")
                submit_login = st.form_submit_button("Giriş Yap")

                if submit_login:
                    users = load_data("users")
                    # Şifre doğrulama
                    user_found = next((u for u in users if
                                       u.get("username") == login_username and u.get("password") == hash_password(
                                           login_password)), None)

                    if user_found:
                        st.session_state["logged_in_user"] = login_username
                        # Çerezi ayarla (30 gün geçerli)
                        cookie_manager.set("current_user", login_username, max_age=30 * 24 * 60 * 60)
                        st.success("Giriş başarılı! Yönlendiriliyorsunuz...")

                        # KRİTİK NOKTA: Çerezin tarayıcıya yazılması için scripti anlık duraklatıyoruz.
                        time.sleep(0.75)
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

        # Giriş yapılmadıysa sayfanın (Dashboard vb.) çalışmasını güvenle durdur
        st.stop()

        # Kullanıcı giriş yaptıysa sol menüde (sidebar) aktif kullanıcıyı ve Çıkış butonunu göster
    st.sidebar.markdown(f"👤 **Aktif Kullanıcı:** {current_user}")
    if st.sidebar.button("🚪 Çıkış Yap", key="logout_btn"):
        st.session_state["logged_in_user"] = None
        cookie_manager.delete("current_user")
        time.sleep(0.75)  # Silme işleminin tarayıcıya yansıması için süre tanı
        st.rerun()

    return current_user