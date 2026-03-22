import streamlit as st
import pandas as pd
from datetime import datetime
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
saved_banks = load_data(f"banks_{current_user}")

# Eğer dosya boşsa veya yeni oluşturulduysa boş liste olarak başlat
if not saved_banks:
    saved_banks = []

# --- 1. BÖLÜM: BANKA VE KART YÖNETİM PANELİ ---
st.markdown("### 🏦 Banka ve Kart Yönetimi")
with st.expander("Banka/Kart Ekle veya Sil", expanded=False):
    col_add, col_del = st.columns(2)

    with col_add:
        st.markdown("**➕ Yeni Banka/Kart Ekle**")
        with st.form("add_bank_form", clear_on_submit=True):
            new_bank_name = st.text_input("Banka veya Kart Adı (Örn: Garanti Miles&Smiles)")
            submit_bank = st.form_submit_button("Listeye Ekle")

            if submit_bank:
                if new_bank_name and new_bank_name.strip() not in saved_banks:
                    saved_banks.append(new_bank_name.strip())
                    save_data(f"banks_{current_user}", saved_banks)
                    st.success(f"'{new_bank_name}' başarıyla eklendi!")
                    st.rerun()
                elif new_bank_name.strip() in saved_banks:
                    st.warning("Bu kayıt zaten listenizde mevcut.")
                else:
                    st.error("Lütfen geçerli bir isim girin.")

    with col_del:
        st.markdown("**🗑️ Kayıtlı Bankayı/Kartı Sil**")
        if saved_banks:
            with st.form("delete_bank_form"):
                bank_to_delete = st.selectbox("Silinecek kaydı seçin", saved_banks)
                submit_del_bank = st.form_submit_button("Listeden Sil")

                if submit_del_bank and bank_to_delete:
                    saved_banks.remove(bank_to_delete)
                    save_data(f"banks_{current_user}", saved_banks)
                    st.success(f"'{bank_to_delete}' başarıyla silindi!")
                    st.rerun()
        else:
            st.info("Listenizde henüz kayıtlı bir banka veya kart bulunmuyor.")

st.divider()

# --- 2. BÖLÜM: YENİ TAKSİT EKLEME FORMU ---
with st.expander("➕ Yeni Taksit Ekle", expanded=False):
    if not saved_banks:
        st.warning("⚠️ Taksit ekleyebilmek için lütfen önce yukarıdaki panelden en az bir tane Banka/Kart ekleyin.")
    else:
        with st.form("add_installment_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                item_name = st.text_input("Ürün/Açıklama (Örn: Cep Telefonu, Beyaz Eşya vb.)")
                bank_name = st.selectbox("Banka/Kart Seçin", saved_banks)
                monthly_payment = st.number_input("Aylık Taksit Tutarı (TL)", min_value=0.0, step=100.0)

            with col2:
                remaining_months = st.number_input("Kalan Taksit Sayısı", min_value=1, step=1)
                # Varsayılan ilk ödeme tarihi olarak bugünü al
                current_date = datetime.now()
                first_payment_date = st.date_input("Sıradaki Ödeme Tarihi", current_date)

            submitted = st.form_submit_button("Taksiti Kaydet")

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
    total_monthly = sum(item["monthly_payment"] for item in installments)
    total_debt = sum(item["total_remaining"] for item in installments)

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