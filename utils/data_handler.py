import streamlit as st
import gspread

# Senin oluşturduğun E-Tablo'nun BİREBİR adı
SHEET_NAME = "finance-db"


@st.cache_resource
def get_gspread_client():
    """Streamlit Secrets üzerinden Google'a modern yöntemle bağlanır."""
    try:
        # st.secrets'tan bilgileri çekip standart bir Python sözlüğüne (dict) çeviriyoruz
        creds_dict = dict(st.secrets["gcp_service_account"])

        # gspread'in kendi dahili kimlik doğrulamasını kullanıyoruz (oauth2client kütüphanesine gerek yok)
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except Exception as e:
        st.error(f"Google bağlantı hatası: Lütfen .streamlit/secrets.toml ayarlarınızı kontrol edin. Detay: {e}")
        return None


def get_or_create_worksheet(client, sh, title):
    """İstenen sekme (Örn: installments_mert) yoksa otomatik oluşturur."""
    try:
        return sh.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        # Yoksa yeni bir sekme ekle (1000 satır, 20 sütun)
        return sh.add_worksheet(title=title, rows="1000", cols="20")


def load_data(filename):
    """Google Sheets'ten veriyi çeker ve sözlük listesi olarak döndürür."""
    client = get_gspread_client()
    if not client: return []

    try:
        sh = client.open(SHEET_NAME)
        ws = get_or_create_worksheet(client, sh, filename)

        records = ws.get_all_records()

        # Banka listeleri tek sütunluk bir dizidir, özel işlenir
        if filename.startswith("banks_"):
            if records and "Bankalar" in records[0]:
                return [str(r["Bankalar"]) for r in records if str(r["Bankalar"]).strip()]
            return []

        return records
    except Exception as e:
        # Tablo boşsa veya yeni oluşturulmuşsa hata fırlatmak yerine boş liste dön
        return []


def save_data(filename, data):
    """Sözlük veya liste verisini Google Sheets sekmesine yazar."""
    client = get_gspread_client()
    if not client: return

    try:
        sh = client.open(SHEET_NAME)
        ws = get_or_create_worksheet(client, sh, filename)

        ws.clear()  # Yeni veri yazılmadan önce mevcut sekmedeki her şeyi sil

        if not data:
            return

        # 1. Durum: Bu bir Banka Listesi ise (Sadece string listesi)
        if filename.startswith("banks_"):
            rows = [["Bankalar"]] + [[str(item)] for item in data]
            # Güncel gspread sürümüne (v6+) uygun veri yazma formatı
            ws.update(values=rows, range_name="A1")

        # 2. Durum: Bu bir Yatırım/Taksit/Kullanıcı listesi ise (Sözlük listesi)
        else:
            if isinstance(data, list) and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [headers]  # İlk satır başlıklar (Sütun isimleri)

                for item in data:
                    # Hücrelerde hata almamak için tüm değerleri string'e (metne) çeviriyoruz
                    row = [str(item.get(h, "")) for h in headers]
                    rows.append(row)

                # Güncel gspread sürümüne (v6+) uygun veri yazma formatı
                ws.update(values=rows, range_name="A1")

    except Exception as e:
        st.error(f"Google E-Tablolara kaydedilirken hata oluştu: {e}")