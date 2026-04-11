import streamlit as st
import gspread
from concurrent.futures import ThreadPoolExecutor

SHEET_NAME = "finance-db"


@st.cache_resource
def get_gspread_client():
    """Google'a bağlanır (uygulama ömrü boyunca tek sefer)."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Google bağlantı hatası: {e}")
        return None


@st.cache_resource
def get_spreadsheet():
    """Spreadsheet nesnesini bir kez açıp cache'ler."""
    client = get_gspread_client()
    if not client:
        return None
    try:
        return client.open(SHEET_NAME)
    except Exception as e:
        st.error(f"Spreadsheet açılamadı: {e}")
        return None


def _get_or_create_worksheet(sh, title):
    """İstenen sekme yoksa oluşturur."""
    try:
        return sh.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows="1000", cols="20")


# Sheet adına göre sayısal alan tanımları (Google Sheets her şeyi string döner)
_TYPE_SCHEMAS = {
    "regular_income": {"amount": float, "day": int, "start_month": int},
    "irregular_income": {"amount": float},
    "expenses": {"amount": float, "day": int},
    "installments": {"monthly_payment": float, "remaining_months": int, "total_remaining": float},
    "investments": {"quantity": float, "price": float, "total": float},
    "cards": {"payment_day": int},
}


_DATE_PARSE_FIELDS = {
    "installments": ("first_payment_date", "_parsed_date"),
}


def _coerce_types(records, filename):
    """Sheet adına göre sayısal alanları doğru tipe çevirir."""
    from datetime import datetime

    # Exact prefix match (filename format: "prefix_username")
    schema = None
    date_field = None
    for prefix, s in _TYPE_SCHEMAS.items():
        if filename == prefix or filename.startswith(prefix + "_"):
            schema = s
            break
    if not schema:
        return records

    for prefix, (src, dst) in _DATE_PARSE_FIELDS.items():
        if filename == prefix or filename.startswith(prefix + "_"):
            date_field = (src, dst)
            break

    for record in records:
        for field, typ in schema.items():
            if field in record:
                try:
                    record[field] = typ(record[field])
                except (ValueError, TypeError):
                    record[field] = typ()
        if date_field and date_field[0] in record:
            try:
                record[date_field[1]] = datetime.strptime(record[date_field[0]], "%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    return records


def _raw_load(filename):
    """Google Sheets'ten ham veri çeker (cache'siz, thread-safe)."""
    sh = get_spreadsheet()
    if not sh:
        return []
    try:
        ws = _get_or_create_worksheet(sh, filename)
        records = ws.get_all_records()

        if filename.startswith("banks_"):
            if records and "Bankalar" in records[0]:
                return [str(r["Bankalar"]) for r in records if str(r["Bankalar"]).strip()]
            return []
        return _coerce_types(records, filename)
    except Exception:
        return []


def load_data(filename):
    """Session cache'ten veri okur. Cache'te yoksa Sheets'ten çeker."""
    cache_key = f"_data_{filename}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    data = _raw_load(filename)
    st.session_state[cache_key] = data
    return data


def save_data(filename, data):
    """Veriyi Sheets'e yazar ve session cache'i anında günceller."""
    sh = get_spreadsheet()
    if not sh:
        return

    try:
        ws = _get_or_create_worksheet(sh, filename)
        ws.clear()

        if not data:
            st.session_state[f"_data_{filename}"] = []
            return

        if filename.startswith("banks_"):
            rows = [["Bankalar"]] + [[str(item)] for item in data]
            ws.update(values=rows, range_name="A1")
        else:
            if isinstance(data, list) and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [headers] + [[str(item.get(h, "")) for h in headers] for item in data]
                ws.update(values=rows, range_name="A1")

        # Session cache'i yazılan veriyle güncelle (tekrar fetch gerekmez)
        st.session_state[f"_data_{filename}"] = data

    except Exception as e:
        st.error(f"Kaydetme hatası: {e}")


def preload_data(filenames):
    """Birden fazla dosyayı paralel olarak yükler. Cache'te olanları atlar."""
    to_fetch = [f for f in filenames if f"_data_{f}" not in st.session_state]
    if not to_fetch:
        return

    # Thread'lerdeki Streamlit ScriptRunContext uyarısını bastır
    import logging
    logger = logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context")
    prev_level = logger.level
    logger.setLevel(logging.ERROR)

    with ThreadPoolExecutor(max_workers=min(len(to_fetch), 6)) as executor:
        results = list(executor.map(_raw_load, to_fetch))

    logger.setLevel(prev_level)

    for filename, data in zip(to_fetch, results):
        st.session_state[f"_data_{filename}"] = data
