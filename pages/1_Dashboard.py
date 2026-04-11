import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar
from utils.data_handler import load_data
from utils.finance import (
    get_monthly_income, get_monthly_investment_expense,
    is_income_applicable, is_installment_active, resolve_day,
    MONTH_NAMES_SHORT, MONTH_NAMES_FULL
)
from utils.prices import calculate_portfolio_totals

from utils.auth import check_login
check_login()
current_user = st.session_state["logged_in_user"]

st.title(":material/monitoring: Finansal Kontrol Paneli")
st.markdown("Gelir, gider ve yatırım durumunuzun büyük resmi.")

# Verileri Yükle
installments = load_data(f"installments_{current_user}")
investments = load_data(f"investments_{current_user}")
regular_incomes = load_data(f"regular_income_{current_user}")
irregular_incomes = load_data(f"irregular_income_{current_user}")
expenses = load_data(f"expenses_{current_user}")

fixed_expenses = sum(exp["amount"] for exp in expenses)

# --- HIZLI ÖZET KARTLARI ---
now = datetime.now()

total_active_debt = sum(item["total_remaining"] for item in installments)
current_month_load = 0
for inst in installments:
    if is_installment_active(inst, now.year, now.month):
        current_month_load += inst["monthly_payment"]

monthly_income = get_monthly_income(now.year, now.month, regular_incomes, irregular_incomes)
monthly_inv_expense = get_monthly_investment_expense(now.year, now.month, investments)

total_portfolio_cost, total_current_value = calculate_portfolio_totals(investments)
total_pl = total_current_value - total_portfolio_cost
total_pl_pct = (total_pl / total_portfolio_cost) * 100 if total_portfolio_cost > 0 else 0

# Üst satır: Taksitler
col1, col2 = st.columns(2)
col1.metric("Kalan Toplam Taksit Borcu", f"{total_active_debt:,.0f} TL")
col2.metric("Bu Ayki Taksit Yükü", f"{current_month_load:,.0f} TL",
            delta=f"Net Kalan: {(monthly_income - fixed_expenses - current_month_load - monthly_inv_expense):,.0f} TL",
            delta_color="normal")

# Alt satır: Yatırımlar
col3, col4 = st.columns(2)
col3.metric("Toplam Yatırım (Maliyet)", f"{total_portfolio_cost:,.0f} TL")
col4.metric("Anlık Portföy Değeri", f"{total_current_value:,.0f} TL",
            delta=f"{total_pl:,.0f} TL ({total_pl_pct:,.1f}%)",
            delta_color="normal")

st.divider()

# --- 6 AYLIK PROJEKSİYON ---
st.markdown("### :material/query_stats: 6 Aylık Harcanabilir Nakit Projeksiyonu")
st.caption("Gelir - (Sabit Giderler + Taksitler + Tek Seferlik Yatırımlar). Taksitli yatırımlar zaten taksit yükünde sayılır.")


labels = []
net_values = []
net_hovers = []
inst_values = []
inst_hovers = []
inv_values = []
inv_hovers = []

for i in range(6):
    target_month = (now.month + i - 1) % 12 + 1
    target_year = now.year + (now.month + i - 1) // 12
    label = f"{MONTH_NAMES_SHORT[target_month - 1]} {target_year}"
    labels.append(label)

    # --- Gelir detayı ---
    income_lines = []
    income_total = 0.0
    for inc in regular_incomes:
        if is_income_applicable(inc, target_year, target_month):
            income_total += inc["amount"]
            income_lines.append(f"  {inc['name']}: {inc['amount']:,.0f} TL")
    for inc in irregular_incomes:
        inc_date = datetime.strptime(inc["date"], "%Y-%m-%d")
        if inc_date.year == target_year and inc_date.month == target_month:
            income_total += inc["amount"]
            income_lines.append(f"  {inc['name']}: {inc['amount']:,.0f} TL")

    # --- Gider detayı ---
    expense_lines = []
    for exp in expenses:
        expense_lines.append(f"  {exp['name']}: {exp['amount']:,.0f} TL")

    # --- Taksit detayı ---
    month_load = 0.0
    inst_lines = []
    for inst in installments:
        if is_installment_active(inst, target_year, target_month):
            amt = inst["monthly_payment"]
            month_load += amt
            inst_lines.append(f"  {inst['item']} ({inst['bank']}): {amt:,.0f} TL")

    # --- Yatırım gideri detayı ---
    inv_expense = 0.0
    inv_lines = []
    for t in investments:
        if t["type"] != "Alım":
            continue
        if t.get("payment_type", "tek_seferlik") == "taksitli":
            continue
        try:
            tx_date = datetime.strptime(str(t["date"])[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if tx_date.year == target_year and tx_date.month == target_month:
            amt = float(t["total"])
            inv_expense += amt
            inv_lines.append(f"  {t.get('asset_name', t['asset'])}: {amt:,.0f} TL")

    net_cash = income_total - fixed_expenses - month_load - inv_expense

    # Hover metinleri
    net_hover = f"<b>Net Harcanabilir: {net_cash:,.0f} TL</b><br>"
    net_hover += f"<br><b>Gelirler ({income_total:,.0f} TL):</b><br>" + "<br>".join(income_lines) if income_lines else ""
    net_hover += f"<br><b>Sabit Giderler ({fixed_expenses:,.0f} TL):</b><br>" + "<br>".join(expense_lines) if expense_lines else ""

    inst_hover = f"<b>Taksit Yükü: {month_load:,.0f} TL</b>"
    if inst_lines:
        inst_hover += "<br>" + "<br>".join(inst_lines)

    inv_hover = f"<b>Yatırım Gideri: {inv_expense:,.0f} TL</b>"
    if inv_lines:
        inv_hover += "<br>" + "<br>".join(inv_lines)

    net_values.append(net_cash)
    net_hovers.append(net_hover)
    inst_values.append(month_load)
    inst_hovers.append(inst_hover)
    inv_values.append(inv_expense)
    inv_hovers.append(inv_hover)

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(name="Net Harcanabilir", x=labels, y=net_values,
                         marker_color="#2ca02c", hovertext=net_hovers, hoverinfo="text"))
fig_bar.add_trace(go.Bar(name="Taksit Yükü", x=labels, y=inst_values,
                         marker_color="#d62728", hovertext=inst_hovers, hoverinfo="text"))
fig_bar.add_trace(go.Bar(name="Yatırım Gideri", x=labels, y=inv_values,
                         marker_color="#3b82f6", hovertext=inv_hovers, hoverinfo="text"))

fig_bar.update_layout(
    barmode="stack", title="Gelecek Aylardaki Bütçe Durumu",
    yaxis_title="Tutar (TL)", legend_title="Kalem",
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
)
st.plotly_chart(fig_bar, width='stretch')

st.divider()

# --- AYLIK GÜNLÜK NAKİT AKIŞI ---
st.markdown("### :material/calendar_month: Aylık Günlük Nakit Akışı")
st.caption("Seçilen ay içinde hangi gün ne kadar para giriş/çıkışı olacağını gösterir.")

# Ay seçici
col_m1, col_m2 = st.columns(2)
with col_m1:
    sel_month = st.selectbox("Ay", range(1, 13), index=now.month - 1,
                             format_func=lambda x: MONTH_NAMES_FULL[x - 1], key="daily_month")
with col_m2:
    sel_year = st.selectbox("Yıl", range(2024, 2031), index=now.year - 2024, key="daily_year")

days_in_month = calendar.monthrange(sel_year, sel_month)[1]


# Her gün için olayları topla
daily_events = {d: {"gelir": [], "gider": []} for d in range(1, days_in_month + 1)}

# Düzenli gelirler
for inc in regular_incomes:
    if is_income_applicable(inc, sel_year, sel_month):
        day = resolve_day(inc.get("day_type", "specific"), inc["day"], sel_year, sel_month)
        daily_events[day]["gelir"].append({"name": inc["name"], "amount": inc["amount"]})

# Düzensiz gelirler
for inc in irregular_incomes:
    try:
        inc_date = datetime.strptime(inc["date"], "%Y-%m-%d")
        if inc_date.year == sel_year and inc_date.month == sel_month:
            daily_events[inc_date.day]["gelir"].append({"name": inc["name"], "amount": inc["amount"]})
    except (ValueError, TypeError):
        pass

# Sabit giderler
for exp in expenses:
    day = resolve_day(exp.get("day_type", "specific"), exp.get("day", 1), sel_year, sel_month)
    daily_events[day]["gider"].append({"name": exp["name"], "amount": exp["amount"]})

# Taksit ödemeleri
for inst in installments:
    if is_installment_active(inst, sel_year, sel_month):
        p_day = min(datetime.strptime(inst["first_payment_date"], "%Y-%m-%d").day, days_in_month)
        daily_events[p_day]["gider"].append({"name": f"{inst['item']} ({inst['bank']})", "amount": inst["monthly_payment"]})

# Tek seferlik yatırım alımları
for t in investments:
    if t["type"] != "Alım":
        continue
    if t.get("payment_type", "tek_seferlik") == "taksitli":
        continue
    try:
        tx_date = datetime.strptime(str(t["date"])[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        continue
    if tx_date.year == sel_year and tx_date.month == sel_month:
        amt = float(t["total"])
        daily_events[tx_date.day]["gider"].append({
            "name": f"Yatırım: {t.get('asset_name', t['asset'])}",
            "amount": amt
        })

# Sadece olay olan günleri göster
event_days = [d for d in range(1, days_in_month + 1)
              if daily_events[d]["gelir"] or daily_events[d]["gider"]]

if event_days:
    day_labels = []
    gelir_vals = []
    gider_vals = []
    gelir_hover_texts = []
    gider_hover_texts = []

    for d in event_days:
        ev = daily_events[d]
        g_total = sum(item["amount"] for item in ev["gelir"])
        c_total = sum(item["amount"] for item in ev["gider"])

        day_labels.append(f"{d} {MONTH_NAMES_FULL[sel_month-1]}")
        gelir_vals.append(g_total)
        gider_vals.append(-c_total)

        if ev["gelir"]:
            lines = [f"  {item['name']}: +{item['amount']:,.0f} TL" for item in ev["gelir"]]
            gelir_hover_texts.append(f"<b>{d} {MONTH_NAMES_FULL[sel_month-1]} — Gelir: +{g_total:,.0f} TL</b><br>" + "<br>".join(lines))
        else:
            gelir_hover_texts.append("")

        if ev["gider"]:
            lines = [f"  {item['name']}: -{item['amount']:,.0f} TL" for item in ev["gider"]]
            gider_hover_texts.append(f"<b>{d} {MONTH_NAMES_FULL[sel_month-1]} — Gider: -{c_total:,.0f} TL</b><br>" + "<br>".join(lines))
        else:
            gider_hover_texts.append("")

    fig_daily = go.Figure()

    fig_daily.add_trace(go.Bar(
        name="Gelir", x=day_labels, y=gelir_vals,
        marker_color="#2ca02c", hovertext=gelir_hover_texts, hoverinfo="text"
    ))

    fig_daily.add_trace(go.Bar(
        name="Gider", x=day_labels, y=gider_vals,
        marker_color="#d62728", hovertext=gider_hover_texts, hoverinfo="text"
    ))

    fig_daily.update_layout(
        barmode="relative",
        title=f"{MONTH_NAMES_FULL[sel_month-1]} {sel_year} — Planlı Nakit Akışı",
        xaxis_title="", yaxis_title="Tutar (TL)",
        legend_title="Kalem",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig_daily, width='stretch')
else:
    st.info("Bu ay için planlı gelir veya gider bulunmuyor.")

st.divider()

# --- PORTFÖY DAĞILIMI ---
st.markdown("### :material/pie_chart: Yatırım Dağılımı (Maliyet Bazlı)")

portfolio_summary = {}
for t in investments:
    asset = t.get("asset_name", t["asset"])
    if asset not in portfolio_summary:
        portfolio_summary[asset] = 0.0
    if t["type"] == "Alım":
        portfolio_summary[asset] += float(t["total"])
    elif t["type"] == "Satım":
        portfolio_summary[asset] -= float(t["total"])

active_portfolio = {k: v for k, v in portfolio_summary.items() if v > 1}

if active_portfolio:
    df_pie = pd.DataFrame({
        "Varlık": list(active_portfolio.keys()),
        "Tutar": list(active_portfolio.values())
    })
    fig_pie = px.pie(
        df_pie, names="Varlık", values="Tutar", hole=0.4,
        title="Yatırımların Maliyet Bazlı Oranları",
        color_discrete_sequence=px.colors.sequential.Teal
    )
    st.plotly_chart(fig_pie, width='stretch')
else:
    st.info("Portföyünüzde henüz aktif bir yatırım bulunmuyor.")
