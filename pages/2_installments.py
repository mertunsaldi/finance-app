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

# Veriyi JSON dosyasından yükle (Kullanıcıya özel veri)
installments = load_data(f"installments_{current_user}")

# 1. BÖLÜM: YENİ TAKSİT EKLEME FORMU
with st.expander("➕ Yeni Taksit Ekle", expanded=False):
    with st.form("add_installment_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            item_name = st.text_input("Ürün/Açıklama (Örn: Cep Telefonu, Beyaz Eşya vb.)")

            # Kullanıcıya özel kaydedilmiş banka/kart listesini çek
            saved_banks = load_data(f"banks_{current_user}")
            if not saved_banks:
                # İlk defa giriyorsa varsayılan listeyi oluştur
                saved_banks = ["Garanti", "Ziraat", "Yapı Kredi", "İş Bankası"]
                save_data(f"banks_{current_user}", saved_banks)

            bank_selection = st.selectbox("Banka/Kart", saved_banks + ["+ Yeni Banka/Kart Ekle"])

            # Eğer kullanıcı yeni banka/kart eklemek isterse metin kutusunu göster
            if bank_selection == "+ Yeni Banka/Kart Ekle":
                bank_name = st.text_input("Yeni Banka veya Kart Adı (Örn: Garanti Bonus)")
            else:
                bank_name = bank_selection

            monthly_payment = st.number_input("Aylık Taksit Tutarı (TL)", min_value=0.0, step=100.0)

        with col2:
            remaining_months = st.number_input("Kalan Taksit Sayısı", min_value=1, step=1)
            # Varsayılan ilk ödeme tarihi olarak bugünü al
            current_date = datetime.now()
            first_payment_date = st.date_input("Sıradaki Ödeme Tarihi", current_date)

        submitted = st.form_submit_button("Kaydet")

        if submitted:
            if item_name and monthly_payment > 0 and bank_name:

                # Yeni girilen banka/kart daha önce listede yoksa kullanıcının kalıcı listesine kaydet
                if bank_name not in saved_banks:
                    saved_banks.append(bank_name)
                    save_data(f"banks_{current_user}", saved_banks)

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
                installments.append(new_item)
                save_data(f"installments_{current_user}", installments)  # JSON'a kaydet (Kullanıcıya özel)
                st.success(f"{item_name} başarıyla eklendi!")
                st.rerun()  # Sayfayı yenile ki tablo güncellensin
            else:
                st.error("Lütfen ürün adını, bankayı ve aylık tutarı geçerli giriniz.")

st.divider()

# 2. BÖLÜM: AKTİF TAKSİTLERİ LİSTELEME
st.markdown("### Aktif Taksit Listesi")

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

    # 3. BÖLÜM: SİLME İŞLEMİ
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
            save_data(f"installments_{current_user}", installments)  # Güncellemeyi kişiye özel dosyaya yaz
            st.success("Kayıt başarıyla silindi.")
            st.rerun()

else:
    st.info("Henüz eklenmiş bir taksit bulunmuyor. Yukarıdaki 'Yeni Taksit Ekle' butonundan veri girebilirsiniz.")