"""Shared finance helpers and constants used across pages."""

from datetime import datetime, date, timedelta
import calendar

# --- Sabit değerler ---
FREQUENCY_OPTIONS = ["Aylık", "2 Ayda Bir", "3 Ayda Bir", "6 Ayda Bir", "Yıllık"]

DAY_TYPE_OPTIONS = {
    "Belirli bir gün": "specific",
    "Ayın son günü": "last_day",
    "Ayın son iş günü": "last_business_day"
}

MONTH_NAMES_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
MONTH_NAMES_FULL = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


# --- Yardımcı fonksiyonlar ---

def resolve_day(day_type, day_value, year, month):
    """Ödeme günü tipine göre gerçek günü hesaplar."""
    max_day = calendar.monthrange(year, month)[1]
    if day_type == "last_day":
        return max_day
    elif day_type == "last_business_day":
        d = date(year, month, max_day)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d.day
    else:
        return min(int(day_value), max_day)


def is_income_applicable(inc, year, month):
    """Düzenli gelir kaydının belirtilen ay için geçerli olup olmadığını kontrol eder."""
    freq = inc["frequency"]
    start_month = inc["start_month"]
    if freq == "Aylık":
        return True
    interval = 12 if freq == "Yıllık" else int(freq.split()[0])
    return (month - start_month) % interval == 0


def format_day_type(day_type, day_value=None):
    """Ödeme günü tipini Türkçe metne çevirir."""
    if day_type == "last_day":
        return "Ayın son günü"
    elif day_type == "last_business_day":
        return "Ayın son iş günü"
    else:
        return f"Ayın {day_value}. günü"


def is_installment_active(inst, year, month):
    """Taksit kaydının belirtilen ayda aktif olup olmadığını kontrol eder."""
    start_date = inst.get("_parsed_date") or datetime.strptime(inst["first_payment_date"], "%Y-%m-%d")
    diff_months = (year - start_date.year) * 12 + (month - start_date.month)
    return 0 <= diff_months < int(inst["remaining_months"])


def calc_first_payment_date(purchase_date, card_payment_day):
    """Satın alma tarihi ve kart ödeme gününe göre ilk ödeme tarihini hesaplar."""
    p_day = int(card_payment_day)
    t_month = purchase_date.month
    t_year = purchase_date.year

    if purchase_date.day > p_day:
        t_month += 1
        if t_month > 12:
            t_month = 1
            t_year += 1

    max_days = calendar.monthrange(t_year, t_month)[1]
    actual_day = min(p_day, max_days)
    return datetime(t_year, t_month, actual_day)


def get_monthly_income(year, month, regular_incomes, irregular_incomes):
    """Belirli bir ay için düzenli + düzensiz toplam geliri hesaplar."""
    total = 0.0
    for inc in regular_incomes:
        if is_income_applicable(inc, year, month):
            total += inc["amount"]
    for inc in irregular_incomes:
        inc_date = datetime.strptime(inc["date"], "%Y-%m-%d")
        if inc_date.year == year and inc_date.month == month:
            total += inc["amount"]
    return total


def get_monthly_investment_expense(year, month, investments):
    """Belirli bir ay için tek seferlik yatırım alım giderini hesaplar."""
    total = 0.0
    for t in investments:
        if t["type"] != "Alım":
            continue
        if t.get("payment_type", "tek_seferlik") == "taksitli":
            continue
        try:
            tx_date = datetime.strptime(str(t["date"])[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if tx_date.year == year and tx_date.month == month:
            total += float(t["total"])
    return total


def clear_form_keys(keys):
    """Session state'ten form key'lerini temizler."""
    import streamlit as st
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
