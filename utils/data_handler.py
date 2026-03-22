import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Drive ve Sheets yetkilendirme linkleri
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Senin oluşturduğun E-Tablo'nun BİREBİR adı
SHEET_NAME = "FinansDB"


@st.cache_resource
def get_gspread_client():
    """Streamlit Secrets üzerinden Google'a bağlanır."""
    try:
        # st.secrets'tan bilgileri çekip dict'e çeviriyoruz
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
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
            ws.update(range_name="A1", values=rows)

        # 2. Durum: Bu bir Yatırım/Taksit listesi ise (Sözlük listesi)
        else:
            if isinstance(data, list) and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [headers]  # İlk satır başlıklar (Sütun isimleri)

                for item in data:
                    # Hücrelerde hata almamak için tüm değerleri string'e (metne) çeviriyoruz
                    row = [str(item.get(h, "")) for h in headers]
                    rows.append(row)

                ws.update(range_name="A1", values=rows)

    except Exception as e:
        st.error(f"Google E-Tablolara kaydedilirken hata oluştu: {e}")