"""Steam Games Insights - Power BI-style analytics dashboard.

A multi-page, Steam-themed (blue/purple) dashboard with a left "Pages"
navigation, compact dropdown filters, a title-usage table with
TotalHours / TotalSessions / UniqueUsers, Top-5 bar charts, and an
agentic Summary page that narrates the key insights from the data.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from src import config

st.set_page_config(
    page_title="Steam Cloud Analytics",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Steam "Dark Blue & Purple" theme
# --------------------------------------------------------------------------
STEAM_COLORS = [
    "#66c0f4", "#8f6fff", "#4fb0ff", "#a679ff", "#37c6d0", "#5c7cff",
    "#c58bff", "#2aa7ff", "#7f5af0", "#00d4ff", "#9d7bff", "#3d5afe",
]
ACCENT = "#66c0f4"
PURPLE = "#a679ff"

STEAM_CSS = """
<style>
.stApp {
  background:
    radial-gradient(1000px 600px at 50% -8%, #33507a 0%, rgba(51,80,122,0) 55%),
    radial-gradient(900px 700px at 100% 105%, #3a2b5e 0%, rgba(58,43,94,0) 52%),
    linear-gradient(160deg, #1b2838 0%, #172033 45%, #191533 100%);
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: rgba(0,0,0,0); }
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #141b2b 0%, #17132a 100%);
  border-right: 1px solid rgba(102,192,244,0.15);
}
/* Sidebar "Pages" nav styled as menu items */
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  display: flex; align-items: center;
  padding: 9px 12px; margin: 2px 0; border-radius: 8px;
  color: #c7d5e0; cursor: pointer; transition: background .15s;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(102,192,244,0.08);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(102,192,244,0.20), rgba(166,121,255,0.12));
  border-left: 3px solid #66c0f4;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display:none; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(90deg, rgba(102,192,244,0.12), rgba(166,121,255,0.08));
  border: 1px solid rgba(102,192,244,0.22);
  border-radius: 12px; padding: 14px 20px; margin-bottom: 14px;
}
.brand { color:#66c0f4; font-weight:700; letter-spacing:1.5px; font-size:.9rem; }
.brand-mark {
  display:inline-block; background:#66c0f4; color:#0b1220; border-radius:6px;
  padding:0 7px; margin-right:8px; font-size:.85rem;
}
.page-title { color:#eaf2fb; font-size:1.5rem; font-weight:600; letter-spacing:.5px; }
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #24314a 0%, #1b2338 100%);
  border: 1px solid rgba(102,192,244,0.22);
  border-radius: 12px; padding: 14px 16px;
}
[data-testid="stMetricValue"] { color:#66c0f4; }
[data-testid="stMetricLabel"] { color:#9fb0c3; }
.insight-card {
  background: linear-gradient(180deg, rgba(36,49,74,0.7), rgba(25,21,51,0.7));
  border: 1px solid rgba(166,121,255,0.28);
  border-radius: 12px; padding: 16px 20px; margin-top: 6px;
}
.insight-card ul { margin:0; padding-left:18px; }
.insight-card li { color:#d6e2f0; margin:7px 0; line-height:1.5; }
.filter-label { color:#8b9ab0; font-size:.78rem; letter-spacing:.6px; margin-bottom:2px; }
.note { color:#6d7c90; font-size:.8rem; }
div[data-testid="stPopover"] > button {
  background:#1e2942; border:1px solid rgba(102,192,244,0.28); color:#c7d5e0;
}
</style>
"""
st.markdown(STEAM_CSS, unsafe_allow_html=True)


def style_fig(fig, height: int = 400, legend: bool = True):
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,27,43,0.45)",
        font=dict(color="#c7d5e0", family="Arial"),
        title_text="",
        legend=dict(bgcolor="rgba(0,0,0,0)", title_font_color="#8b9ab0"),
        margin=dict(l=10, r=10, t=36, b=10),
        showlegend=legend,
        colorway=STEAM_COLORS,
    )
    grid = "rgba(102,192,244,0.10)"
    fig.update_xaxes(gridcolor=grid, zeroline=False)
    fig.update_yaxes(gridcolor=grid, zeroline=False)
    return fig


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    games = genre = usage = monthly = report = None
    if config.GAMES_FILE.exists():
        games = pd.read_csv(config.GAMES_FILE)
    if config.GENRE_SUMMARY_FILE.exists():
        genre = pd.read_csv(config.GENRE_SUMMARY_FILE)
    if config.USAGE_DAILY_FILE.exists():
        usage = pd.read_csv(config.USAGE_DAILY_FILE, parse_dates=["date"])
    if config.MONTHLY_METRICS_FILE.exists():
        monthly = pd.read_csv(config.MONTHLY_METRICS_FILE, parse_dates=["month_date"])
    if config.QUALITY_REPORT_FILE.exists():
        report = json.loads(config.QUALITY_REPORT_FILE.read_text(encoding="utf-8"))
    return games, genre, usage, monthly, report


games, genre_summary, usage, monthly, report = load_data()


def fmt_big(n: float) -> str:
    """Human-friendly large-number formatting (bn / M / K)."""
    n = float(n)
    if abs(n) >= 1e9:
        return f"{n / 1e9:.2f}bn"
    if abs(n) >= 1e6:
        return f"{n / 1e6:.2f}M"
    if abs(n) >= 1e3:
        return f"{n / 1e3:.0f}K"
    return f"{n:.0f}"


# --------------------------------------------------------------------------
# Compact dropdown filter helpers (popover-based)
# --------------------------------------------------------------------------
def dd_multi(label: str, options: list, default: list, key: str) -> list:
    """Compact multi-select rendered inside a popover 'dropdown' button."""
    current = st.session_state.get(key, default)
    with st.popover(f"{label}  ·  {len(current)}/{len(options)}"):
        sel = st.multiselect(label, options, default=default, key=key,
                             label_visibility="collapsed")
    return sel or default


def usage_filters(df: pd.DataFrame, key: str, default_titles: int = 8) -> pd.DataFrame:
    """A compact filter bar (Title / Publisher / Country / Date) for a page."""
    st.markdown('<div class="filter-label">FILTERS</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
    titles = sorted(df["name"].unique())
    top_titles = (
        df.groupby("name")["players"].sum().sort_values(ascending=False)
        .head(default_titles).index.tolist()
    )
    pubs = sorted(df["publisher"].unique())
    countries = sorted(df["country"].unique())
    with c1:
        sel_t = dd_multi("🎮 Title", titles, top_titles, f"t_{key}")
    with c2:
        sel_p = dd_multi("🏢 Publisher", pubs, pubs, f"p_{key}")
    with c3:
        sel_c = dd_multi("🌍 Country", countries, countries, f"c_{key}")
    with c4:
        dmin, dmax = df["date"].min().date(), df["date"].max().date()
        dr = st.date_input("📅 Date range", (dmin, dmax), min_value=dmin,
                           max_value=dmax, key=f"d_{key}")
    start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax))
    mask = (
        df["name"].isin(sel_t)
        & df["publisher"].isin(sel_p)
        & df["country"].isin(sel_c)
        & df["date"].dt.date.between(start, end)
    )
    return df.loc[mask].copy()


# --------------------------------------------------------------------------
# Agentic summary (insights computed from the data)
# --------------------------------------------------------------------------
def build_insights(games: pd.DataFrame, usage: pd.DataFrame,
                   genre_summary: pd.DataFrame) -> list[str]:
    out: list[str] = []
    daily = usage.groupby("date")["players"].sum().sort_index()
    if len(daily) >= 4:
        half = len(daily) // 2
        first, last = daily.iloc[:half].mean(), daily.iloc[half:].mean()
        pct = (last - first) / first * 100 if first else 0
        arrow = "📈 up" if pct >= 0 else "📉 down"
        out.append(
            f"Total active players are trending {arrow} **{abs(pct):.1f}%** across "
            f"the {len(daily)}-day window."
        )
    wk = usage.assign(dow=usage["date"].dt.dayofweek)
    we, wd = wk[wk["dow"] >= 5]["players"].mean(), wk[wk["dow"] < 5]["players"].mean()
    if wd:
        out.append(
            f"Weekend engagement runs **{(we - wd) / wd * 100:.0f}% higher** than "
            f"weekdays — plan events and releases accordingly."
        )
    tp = usage.groupby("name")["players"].sum().sort_values(ascending=False)
    th = usage.groupby("name")["usage_hours"].sum().sort_values(ascending=False)
    out.append(
        f"**{tp.index[0]}** draws the largest modeled audience, while "
        f"**{th.index[0]}** leads on total engagement (player-hours)."
    )
    tc = usage.groupby("country")["players"].sum().sort_values(ascending=False)
    out.append(
        f"**{tc.index[0]}** is the top market (~{tc.iloc[0] / tc.sum() * 100:.0f}% "
        f"of players), followed by **{tc.index[1]}** and **{tc.index[2]}**."
    )
    now = games.sort_values("ccu", ascending=False).iloc[0]
    out.append(
        f"Live right now: **{now['name']}** leads concurrency with "
        f"**{int(now['ccu']):,}** players and a {now['review_ratio']:.0f}% review score."
    )
    if genre_summary is not None and not genre_summary.empty:
        bg = genre_summary.sort_values("avg_review_ratio", ascending=False).iloc[0]
        out.append(
            f"**{bg['primary_genre']}** is the best-received genre "
            f"(avg {bg['avg_review_ratio']:.0f}% positive)."
        )
    free = games["is_free"].mean() * 100
    out.append(
        f"**{free:.0f}%** of tracked titles are free-to-play; the median paid price "
        f"is **${games.loc[~games['is_free'], 'price_usd'].median():.2f}**."
    )
    return out


# --------------------------------------------------------------------------
# Sidebar "Pages" navigation
# --------------------------------------------------------------------------
st.sidebar.markdown(
    '<div style="padding:6px 4px 12px 4px;">'
    '<span class="brand"><span class="brand-mark">▶</span>STEAM · CLOUD</span>'
    "</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown('<div class="filter-label">PAGES</div>', unsafe_allow_html=True)

PAGES = [
    "🧠  Summary",
    "🌐  Usage Worldwide",
    "📈  Title Usage Overview",
    "📋  Title Usage by Metric",
    "👥  Active Players",
    "🎯  Genre Distribution",
    "📊  Market Snapshot",
    "✅  Data Quality",
    "🗂️  Data",
]
page = st.sidebar.radio("Pages", PAGES, label_visibility="collapsed")
st.sidebar.markdown(
    '<div class="note" style="margin-top:18px;">Daily &amp; country figures are '
    "modeled estimates derived from the SteamSpy snapshot.</div>",
    unsafe_allow_html=True,
)

if games is None or usage is None:
    st.warning("No processed data found. Run `python etl.py` first.")
    st.stop()


def topbar(title: str):
    st.markdown(
        f'<div class="topbar"><div class="brand"><span class="brand-mark">▶</span>'
        f"STEAM · CLOUD ANALYTICS</div>"
        f'<div class="page-title">{title}</div></div>',
        unsafe_allow_html=True,
    )


page_name = page.strip()

# ==========================================================================
# PAGE: SUMMARY (agentic)
# ==========================================================================
if page_name.endswith("Summary"):
    topbar("EXECUTIVE SUMMARY")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Games tracked", len(games))
    k2.metric("Live players (CCU)", f"{int(games['ccu'].sum()):,}")
    k3.metric("Avg review score", f"{games['review_ratio'].mean():.0f}%")
    k4.metric("Total player-hours", f"{usage['usage_hours'].sum() / 1e6:.1f}M")
    k5.metric("Markets", usage["country"].nunique())

    st.markdown("### 🤖 AI-generated insights")
    insights = build_insights(games, usage, genre_summary)
    insights_html = [re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", i) for i in insights]
    st.markdown(
        '<div class="insight-card"><ul>'
        + "".join(f"<li>{i}</li>" for i in insights_html)
        + "</ul></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Insights are generated automatically from the processed data each run "
        "(trend, seasonality, market mix, reception, pricing)."
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("#### Total active players by date")
        daily = usage.groupby("date", as_index=False)["players"].sum()
        fig = px.area(daily, x="date", y="players", labels={"players": "Players", "date": ""})
        fig.update_traces(line_color=ACCENT, fillcolor="rgba(102,192,244,0.18)")
        st.plotly_chart(style_fig(fig, 320, legend=False), width="stretch")
    with c2:
        st.markdown("#### Players by market")
        by_c = usage.groupby("country", as_index=False)["players"].sum()
        fig = px.pie(by_c, names="country", values="players", hole=0.5,
                     color_discrete_sequence=STEAM_COLORS)
        st.plotly_chart(style_fig(fig, 320), width="stretch")

# ==========================================================================
# PAGE: USAGE WORLDWIDE  (MAU / DAU / new users + YoY deltas)
# ==========================================================================
elif page_name.endswith("Worldwide"):
    if monthly is None or monthly.empty:
        topbar("USAGE WORLDWIDE")
        st.info("Monthly metrics not found. Re-run `python etl.py`.")
    else:
        m = monthly.sort_values("month_date").reset_index(drop=True)
        latest = m.iloc[-1]
        yoy = m.iloc[-13] if len(m) >= 13 else m.iloc[0]

        def delta_pct(cur, prev):
            return (cur - prev) / prev * 100 if prev else 0.0

        avail = latest["month_date"].strftime("%Y-%m")
        st.markdown(
            f'<div class="topbar"><div class="brand"><span class="brand-mark">▶</span>'
            f"USAGE ON CLOUD GAMING WORLDWIDE</div>"
            f'<div class="page-title">Data available until&nbsp;·&nbsp;{avail}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # KPI cards with increment / decrement vs same month last year
        k = st.columns(6)
        k[0].metric("MAU (monthly active users)", fmt_big(latest["mau"]),
                    f"{delta_pct(latest['mau'], yoy['mau']):+.1f}% YoY")
        k[1].metric("DAU (avg daily active)", fmt_big(latest["dau"]),
                    f"{delta_pct(latest['dau'], yoy['dau']):+.1f}% YoY")
        k[2].metric("New users (this month)", fmt_big(latest["new_users"]),
                    f"{delta_pct(latest['new_users'], yoy['new_users']):+.1f}% YoY")
        k[3].metric("Total sessions", fmt_big(latest["sessions"]),
                    f"{delta_pct(latest['sessions'], yoy['sessions']):+.1f}% YoY")
        k[4].metric("Total hours", fmt_big(latest["hours"]),
                    f"{delta_pct(latest['hours'], yoy['hours']):+.1f}% YoY")
        k[5].metric("Hours per user", f"{latest['hours_per_user']:.2f}",
                    f"{delta_pct(latest['hours_per_user'], yoy['hours_per_user']):+.1f}% YoY")
        st.caption(
            "Deltas compare the latest month to the same month last year "
            "(green ▲ = growth, red ▼ = decline)."
        )

        # Year filter (compact dropdown) for the year-over-year comparison
        years = sorted(m["year"].unique())
        sel_years = dd_multi("📅 Year", years, years, "ww_year")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Unique users by month (MAU)")
            fig = px.line(m, x="month_date", y="mau", markers=True,
                          labels={"mau": "MAU", "month_date": ""})
            fig.update_traces(line_color=ACCENT, line_width=2.6)
            st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")
        with c2:
            st.markdown("#### DAU by month")
            fig = px.line(m, x="month_date", y="dau", markers=True,
                          labels={"dau": "DAU", "month_date": ""})
            fig.update_traces(line_color=PURPLE, line_width=2.6)
            st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### New users by month")
            fig = px.bar(m, x="month_date", y="new_users",
                         labels={"new_users": "New users", "month_date": ""})
            fig.update_traces(marker_color="#37c6d0")
            st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")
        with c4:
            st.markdown("#### Net MAU change month-over-month")
            mc = m.copy()
            mc["mau_change"] = mc["mau"].diff()
            mc["dir"] = mc["mau_change"].apply(lambda v: "Increase" if v >= 0 else "Decrease")
            fig = px.bar(mc.dropna(subset=["mau_change"]), x="month_date", y="mau_change",
                         color="dir", color_discrete_map={"Increase": "#4fd18b", "Decrease": "#e46a6a"},
                         labels={"mau_change": "MAU change", "month_date": "", "dir": ""})
            st.plotly_chart(style_fig(fig, 300), width="stretch")

        c5, c6 = st.columns(2)
        with c5:
            st.markdown("#### Hours played by month")
            fig = px.line(m, x="month_date", y="hours", markers=True,
                          labels={"hours": "Hours", "month_date": ""})
            fig.update_traces(line_color=ACCENT, line_width=2.6)
            st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")
        with c6:
            st.markdown("#### Sessions by month (year over year)")
            order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            cmp = m[m["year"].isin(sel_years)]
            fig = px.line(cmp, x="month_name", y="sessions", color="year", markers=True,
                          category_orders={"month_name": order},
                          labels={"sessions": "Sessions", "month_name": "", "year": "Year"})
            fig.update_traces(line_width=2.6)
            st.plotly_chart(style_fig(fig, 300), width="stretch")

# ==========================================================================
# PAGE: TITLE USAGE OVERVIEW
# ==========================================================================
elif page_name.endswith("Overview"):
    topbar("TITLE USAGE OVERVIEW")
    f = usage_filters(usage, key="overview")
    if f.empty:
        st.info("No data for the selected filters.")
    else:
        st.markdown("#### Usage (player-hours) by date")
        by_date = f.groupby(["date", "name"], as_index=False)["usage_hours"].sum()
        fig = px.line(by_date, x="date", y="usage_hours", color="name",
                      labels={"usage_hours": "Player-hours", "date": "", "name": "Title"})
        fig.update_traces(line=dict(width=2.4))
        st.plotly_chart(style_fig(fig, 440), width="stretch")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("#### Total usage by title")
            totals = f.groupby("name", as_index=False)["usage_hours"].sum().sort_values("usage_hours")
            fig = px.bar(totals, x="usage_hours", y="name", orientation="h",
                         labels={"usage_hours": "Player-hours", "name": ""},
                         color="usage_hours", color_continuous_scale=["#22345a", ACCENT])
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, 420, legend=False), width="stretch")
        with c2:
            st.markdown("#### Usage share by country")
            by_c = f.groupby("country", as_index=False)["usage_hours"].sum()
            fig = px.pie(by_c, names="country", values="usage_hours", hole=0.5,
                         color_discrete_sequence=STEAM_COLORS)
            st.plotly_chart(style_fig(fig, 420), width="stretch")

# ==========================================================================
# PAGE: TITLE USAGE BY METRIC  (Power BI-style table + Top 5 charts)
# ==========================================================================
elif page_name.endswith("by Metric"):
    topbar("TITLE USAGE BY METRIC")

    # "Modality"-style dropdown = Genre, plus the standard filters.
    gcol, _ = st.columns([1, 3])
    with gcol:
        genres = ["All genres"] + sorted(usage["primary_genre"].dropna().unique())
        sel_genre = st.selectbox("Genre", genres, key="metric_genre")
    base = usage if sel_genre == "All genres" else usage[usage["primary_genre"] == sel_genre]
    f = usage_filters(base, key="metric", default_titles=30)

    if f.empty:
        st.info("No data for the selected filters.")
    else:
        daily = f.groupby(["name", "date"], as_index=False).agg(
            players=("players", "sum"),
            sessions=("sessions", "sum"),
            hours=("usage_hours", "sum"),
        )
        table = daily.groupby("name", as_index=False).agg(
            TotalHours=("hours", "sum"),
            TotalSessions=("sessions", "sum"),
            PeakDAU=("players", "max"),
        )
        table["UniqueUsers"] = (table["PeakDAU"] * 1.5).round().astype(int)
        table["TotalHours"] = table["TotalHours"].round().astype(int)
        table = table.rename(columns={"name": "TitleName"})[
            ["TitleName", "TotalHours", "TotalSessions", "UniqueUsers"]
        ].sort_values("TotalHours", ascending=False)

        st.markdown("#### Title usage table")
        st.dataframe(
            table, width="stretch", hide_index=True, height=360,
            column_config={
                "TotalHours": st.column_config.NumberColumn("Total Hours", format="%d"),
                "TotalSessions": st.column_config.NumberColumn("Total Sessions", format="%d"),
                "UniqueUsers": st.column_config.NumberColumn("Unique Users", format="%d"),
            },
        )

        st.markdown("#### Top 5 titles")
        c1, c2, c3 = st.columns(3)
        specs = [
            (c1, "TotalSessions", "by number of sessions", ACCENT),
            (c2, "TotalHours", "by game play hours", PURPLE),
            (c3, "UniqueUsers", "by unique users", "#37c6d0"),
        ]
        for col, metric, caption, color in specs:
            with col:
                st.markdown(f"**Top 5 {caption}**")
                top5 = table.nlargest(5, metric)
                fig = px.bar(top5, x="TitleName", y=metric,
                             labels={"TitleName": "", metric: ""})
                fig.update_traces(marker_color=color)
                fig.update_xaxes(tickangle=-40)
                st.plotly_chart(style_fig(fig, 320, legend=False), width="stretch")

# ==========================================================================
# PAGE: ACTIVE PLAYERS
# ==========================================================================
elif page_name.endswith("Active Players"):
    topbar("ACTIVE PLAYERS BY DATE")
    f = usage_filters(usage, key="players")
    if f.empty:
        st.info("No data for the selected filters.")
    else:
        st.markdown("#### Active players by date")
        by_date = f.groupby(["date", "name"], as_index=False)["players"].sum()
        fig = px.line(by_date, x="date", y="players", color="name",
                      labels={"players": "Active players", "date": "", "name": "Title"})
        fig.update_traces(line=dict(width=2.4))
        st.plotly_chart(style_fig(fig, 440), width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Players by country")
            by_c = f.groupby("country", as_index=False)["players"].sum().sort_values("players")
            fig = px.bar(by_c, x="players", y="country", orientation="h",
                         labels={"players": "Active players", "country": ""},
                         color="players", color_continuous_scale=["#22345a", ACCENT])
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, 420, legend=False), width="stretch")
        with c2:
            st.markdown("#### Daily players by country (stacked)")
            stacked = f.groupby(["date", "country"], as_index=False)["players"].sum()
            fig = px.bar(stacked, x="date", y="players", color="country",
                         labels={"players": "Active players", "date": "", "country": "Country"})
            st.plotly_chart(style_fig(fig, 420), width="stretch")

# ==========================================================================
# PAGE: GENRE DISTRIBUTION
# ==========================================================================
elif page_name.endswith("Distribution"):
    topbar("GENRE DISTRIBUTION")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Games per genre")
        fig = px.bar(genre_summary.sort_values("games"), x="games", y="primary_genre",
                     orientation="h", labels={"games": "Games", "primary_genre": ""},
                     color="games", color_continuous_scale=["#22345a", PURPLE])
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")
    with c2:
        st.markdown("#### Live players by genre")
        fig = px.bar(genre_summary.sort_values("total_ccu"), x="total_ccu", y="primary_genre",
                     orientation="h", labels={"total_ccu": "Concurrent players", "primary_genre": ""},
                     color="total_ccu", color_continuous_scale=["#22345a", ACCENT])
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")

    st.markdown("#### Players by genre over time (modeled)")
    by = usage.groupby(["date", "primary_genre"], as_index=False)["players"].sum()
    fig = px.area(by, x="date", y="players", color="primary_genre",
                  labels={"players": "Active players", "date": "", "primary_genre": "Genre"})
    st.plotly_chart(style_fig(fig, 380), width="stretch")

# ==========================================================================
# PAGE: MARKET SNAPSHOT
# ==========================================================================
elif page_name.endswith("Market Snapshot"):
    topbar("MARKET SNAPSHOT")
    c1, c2, c3 = st.columns(3)
    with c1:
        genres = sorted(games["primary_genre"].dropna().unique())
        sel_g = dd_multi("🎯 Genre", genres, genres, "mkt_g")
    with c2:
        price_type = st.selectbox("💵 Price type", ["All", "Free", "Paid"], key="mkt_price")
    with c3:
        pubs = sorted(games["publisher"].dropna().unique())
        sel_p = dd_multi("🏢 Publisher", pubs, pubs, "mkt_p")

    gv = games[games["primary_genre"].isin(sel_g) & games["publisher"].isin(sel_p)].copy()
    if price_type == "Free":
        gv = gv[gv["is_free"]]
    elif price_type == "Paid":
        gv = gv[~gv["is_free"]]

    if gv.empty:
        st.info("No games match the selected filters.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Reception vs. audience size")
            fig = px.scatter(gv, x="owners_mid", y="review_ratio", size="ccu",
                             color="primary_genre", hover_name="name", log_x=True,
                             labels={"owners_mid": "Estimated owners", "review_ratio": "Positive %"})
            st.plotly_chart(style_fig(fig, 420), width="stretch")
        with c2:
            st.markdown("#### Price distribution (paid)")
            paid = gv[~gv["is_free"]]
            if paid.empty:
                st.info("No paid games in this selection.")
            else:
                fig = px.histogram(paid, x="price_usd", nbins=20, labels={"price_usd": "Price (USD)"})
                fig.update_traces(marker_color=PURPLE)
                st.plotly_chart(style_fig(fig, 420, legend=False), width="stretch")

        st.markdown("#### Top games by live concurrent players")
        top = gv.sort_values("ccu", ascending=False).head(15)
        fig = px.bar(top, x="name", y="ccu", labels={"ccu": "Concurrent players", "name": ""},
                     color="ccu", color_continuous_scale=["#22345a", ACCENT])
        fig.update_layout(coloraxis_showscale=False)
        fig.update_xaxes(tickangle=-40)
        st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")

# ==========================================================================
# PAGE: DATA QUALITY
# ==========================================================================
elif page_name.endswith("Data Quality"):
    topbar("DATA QUALITY")
    if report is None:
        st.info("No quality report found. Re-run `python etl.py`.")
    else:
        overall = report["overall_status"].upper()
        (st.success if overall == "PASS" else st.error)(
            f"Overall status: **{overall}** — "
            f"{report['checks_passed']}/{report['checks_total']} checks passed."
        )
        q1, q2, q3 = st.columns(3)
        q1.metric("Games validated", report["rows"])
        q2.metric("Genres", report["genres"])
        q3.metric("Checks passed", f"{report['checks_passed']}/{report['checks_total']}")
        checks_df = pd.DataFrame(report["checks"])[["check", "status", "detail"]]
        st.dataframe(
            checks_df.rename(columns={"check": "Check", "status": "Status", "detail": "Detail"}),
            width="stretch", hide_index=True,
        )
        st.caption(f"Report generated at {report['generated_at']}")

# ==========================================================================
# PAGE: DATA
# ==========================================================================
else:
    topbar("DATA")
    st.markdown("#### Processed games (snapshot)")
    st.dataframe(games, width="stretch", hide_index=True)
    st.markdown("#### Modeled daily usage")
    st.dataframe(usage.head(1000), width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Download usage data (CSV)",
        data=usage.to_csv(index=False).encode("utf-8"),
        file_name="usage_daily.csv",
        mime="text/csv",
    )

st.caption("Data source: SteamSpy · Daily & country figures are modeled estimates · AI Data Engineer assignment.")
