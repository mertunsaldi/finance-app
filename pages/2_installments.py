import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
import uuid
import sys
import os

# utils klasöründeki modülleri çağırabilmek için dosya yolunu ayarlıyoruz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_handler import load_data, save_data
from utils.auth import check_login

# Sayfa ayarları
st.set_page_config(page_title="Taksit Takibi", page_icon="💳", layout="wide")

# Giriş kontrolü
current_user = check_login()

st.title("💳 Taksit ve Borç Yönetimi")
st.markdown("Kredi kartı taksitlerinizi buradan ekleyebilir, aktif borç yükünüzü takip edebilirsiniz.")

# Kullanıcıya özel verileri yükle
installments = load_data(f"installments_{current_user}")

# Kartların ve ödeme günlerinin tutulacağı yeni liste: cards_{current_user}
saved_cards = load_data(f"cards_{current_user}")

# EĞER ESKİ SİSTEMDEN KALAN "banks_" DOSYASI VARSA VE YENİ SİSTEM BOŞSA, OTOMATİK GEÇİŞ YAP (MIGRATION)
if not saved_cards:
    old_banks = load_data(f"banks_{current_user}")
    if old_banks:
        # Eski banka isimlerini alıp varsayılan olarak ayın 1'ine ayarla
        saved_cards = [{"bank_name": str(b), "payment_day": 1} for b in old_banks]
        save_data(f"cards_{current_user}", saved_cards)
    else:
        saved_cards = []

# --- 1. BÖLÜM: BANKA VE KART YÖNETİM PANELİ ---
st.markdown("### 🏦 Banka ve Kart Yönetimi")
with st.expander("Banka/Kart Ekle veya Sil", expanded=False):
    col_add, col_del = st.columns(2)

    with col_add:
        st.markdown("**➕ Yeni Banka/Kart Ekle**")
        with st.form("add_bank_form", clear_on_submit=True):
            new_bank_name = st.text_input("Banka veya Kart Adı (Örn: Garanti Miles&Smiles)")
            payment_day = st.number_input("Her Ayın Ödeme Günü", min_value=1, max_value=31, step=1, value=15)
            submit_bank = st.form_submit_button("Listeye Ekle")

            if submit_bank:
                existing_names = [c.get("bank_name", "") for c in saved_cards]
                if new_bank_name and new_bank_name.strip() not in existing_names:
                    saved_cards.append({"bank_name": new_bank_name.strip(), "payment_day": payment_day})
                    save_data(f"cards_{current_user}", saved_cards)
                    st.success(f"'{new_bank_name}' (Ödeme Günü: {payment_day}) başarıyla eklendi!")
                    st.rerun()
                elif new_bank_name.strip() in existing_names:
                    st.warning("Bu kayıt zaten listenizde mevcut.")
                else:
                    st.error("Lütfen geçerli bir isim girin.")

    with col_del:
        st.markdown("**🗑️ Kayıtlı Bankayı/Kartı Sil**")
        if saved_cards:
            with st.form("delete_bank_form"):
                card_names = [c.get("bank_name", "") for c in saved_cards]
                bank_to_delete = st.selectbox("Silinecek kaydı seçin", card_names)
                submit_del_bank = st.form_submit_button("Listeden Sil")

                if submit_del_bank and bank_to_delete:
                    saved_cards = [c for c in saved_cards if c.get("bank_name") != bank_to_delete]
                    save_data(f"cards_{current_user}", saved_cards)
                    st.success(f"'{bank_to_delete}' başarıyla silindi!")
                    st.rerun()
        else:
            st.info("Listenizde henüz kayıtlı bir banka veya kart bulunmuyor.")

st.divider()

# --- 2. BÖLÜM: YENİ TAKSİT EKLEME FORMU ---
with st.expander("➕ Yeni Taksit Ekle", expanded=False):
    if not saved_cards:
        st.warning("⚠️ Taksit ekleyebilmek için lütfen önce yukarıdaki panelden en az bir tane Banka/Kart ekleyin.")
    else:
        # Anlık güncellemelerin çalışması için st.form yapısı buradan kaldırıldı.
        col1, col2 = st.columns(2)

        with col1:
            item_name = st.text_input("Ürün/Açıklama (Örn: Cep Telefonu, Beyaz Eşya vb.)", key="inst_item")
            card_names_for_select = [c.get("bank_name", "") for c in saved_cards]
            bank_name = st.selectbox("Banka/Kart Seçin", card_names_for_select, key="inst_bank")
            monthly_payment = st.number_input("Aylık Taksit Tutarı (TL)", min_value=0.0, step=100.0, key="inst_payment")

        with col2:
            remaining_months = st.number_input("Kalan Taksit Sayısı", min_value=1, step=1, key="inst_months")

            # Seçilen karta göre otomatik ödeme tarihi hesaplama algoritması (Artık anında güncellenir)
            first_payment_date = datetime.now()
            if bank_name:
                selected_card = next((c for c in saved_cards if c.get("bank_name") == bank_name), None)
                p_day = int(selected_card.get("payment_day", 1)) if selected_card else 1

                now = datetime.now()
                t_month = now.month
                t_year = now.year

                # Eğer bugünün tarihi ödeme gününü geçmişse, ödeme bir sonraki aya sarkar
                if now.day > p_day:
                    t_month += 1
                    if t_month > 12:
                        t_month = 1
                        t_year += 1

                # Şubat ayı gibi ayın 30'u veya 31'i olmayan durumlar için limit belirle
                max_days_in_month = calendar.monthrange(t_year, t_month)[1]
                actual_day = min(p_day, max_days_in_month)

                first_payment_date = datetime(t_year, t_month, actual_day)

                st.info(
                    f"📅 Otomatik İlk Ödeme Tarihi: **{first_payment_date.strftime('%d.%m.%Y')}**\n\n*(Kartın ödeme günü her ayın {p_day}. günü olarak tanımlı)*")

        submitted = st.button("Taksiti Kaydet", type="primary")

        if submitted:
            if item_name and monthly_payment > 0 and bank_name:
                # Her kayda benzersiz bir ID veriyoruz (silme işlemi için gerekli)
                new_item = {
                    "id": str(uuid.uuid4())[:8],
                    "item": item_name,
                    "bank": bank_name,
                    "monthly_payment": monthly_payment,
                    "remaining_months": remaining_months,
                    "first_payment_date": first_payment_date.strftime("%Y-%m-%d"),
                    "total_remaining": monthly_payment * remaining_months
                }
                if not installments:
                    installments = []
                installments.append(new_item)
                save_data(f"installments_{current_user}", installments)
                st.success(f"{item_name} başarıyla eklendi!")

                # Form silme mekanizmasını (clear_on_submit) manuel simüle etme
                for key in ["inst_item", "inst_payment", "inst_months"]:
                    if key in st.session_state:
                        del st.session_state[key]

                st.rerun()
            else:
                st.error("Lütfen ürün adını ve aylık tutarı geçerli giriniz.")

st.divider()

# --- 3. BÖLÜM: AKTİF TAKSİTLERİ LİSTELEME ---
st.markdown("### 📋 Aktif Taksit Listesi")

if installments:
    df = pd.DataFrame(installments)

    # Kullanıcıya göstereceğimiz tablo için sütun isimlerini Türkçeleştir
    display_df = df.copy()
    display_df = display_df.rename(columns={
        "item": "Açıklama",
        "bank": "Banka/Kart",
        "monthly_payment": "Aylık Tutar (TL)",
        "remaining_months": "Kalan Taksit",
        "first_payment_date": "Sıradaki Ödeme",
        "total_remaining": "Kalan Toplam Borç (TL)"
    })

    # Arka planda çalışan "id" sütununu gizleyerek tabloyu çiz
    st.dataframe(
        display_df.drop(columns=["id"]),
        width="stretch",
        hide_index=True
    )

    # Toplam Özet Metrikleri
    total_monthly = sum(float(item["monthly_payment"]) for item in installments)
    total_debt = sum(float(item["total_remaining"]) for item in installments)

    col_sum1, col_sum2, col_sum3 = st.columns(3)
    col_sum1.metric("Toplam Aylık Yük", f"{total_monthly:,.2f} TL")
    col_sum2.metric("Toplam Kalan Borç", f"{total_debt:,.2f} TL")

    st.divider()

    # --- 4. BÖLÜM: SİLME İŞLEMİ ---
    st.markdown("### 🗑️ Taksit Kapat / Sil")
    col_del1, col_del2 = st.columns([3, 1])

    with col_del1:
        # Silinecek öğeyi listeden seçtir (Açıklama + Banka)
        options = {item["id"]: f"{item['item']} ({item['bank']} - {item['monthly_payment']} TL)" for item in
                   installments}
        selected_id = st.selectbox("Silmek veya kapatmak istediğiniz kaydı seçin:", options=list(options.keys()),
                                   format_func=lambda x: options[x])

    with col_del2:
        st.write("")  # Dikey hizalama için boşluk
        st.write("")
        if st.button("Seçili Kaydı Sil", type="primary"):
            # Seçili ID hariç diğerlerini listede tut ve kaydet
            installments = [item for item in installments if item["id"] != selected_id]
            save_data(f"installments_{current_user}", installments)
            st.success("Kayıt başarıyla silindi.")
            st.rerun()

else:
    st.info("Henüz eklenmiş bir taksit bulunmuyor. Yukarıdaki 'Yeni Taksit Ekle' butonundan veri girebilirsiniz.")