"""Steam Games Insights - professional Steam-themed Streamlit dashboard.

Reads the processed outputs produced by ``etl.py`` and presents them across
distinct, business-facing sections with a Steam visual theme:

    Overview  |  Title Usage  |  Active Players  |  Market Snapshot
    Data Quality  |  Data

Each analytical section has its own filters (title, publisher, country, date).

Run:
    streamlit run app.py
"""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src import config

st.set_page_config(
    page_title="Steam Games Insights",
    page_icon="🎮",
    layout="wide",
)

# --------------------------------------------------------------------------
# Steam theme
# --------------------------------------------------------------------------
STEAM_COLORS = [
    "#66c0f4", "#1a9fff", "#a4d007", "#5c7e10", "#e74c3c", "#f1c40f",
    "#c586c0", "#00a5a5", "#ff7b00", "#8f98a0", "#4b6b8a", "#b8b6b4",
]

STEAM_CSS = """
<style>
.stApp {
  background: radial-gradient(1100px 550px at 18% -12%, #2a475e 0%, rgba(42,71,94,0) 60%),
              linear-gradient(180deg, #1b2838 0%, #10161d 100%);
}
[data-testid="stHeader"] { background: rgba(0,0,0,0); }
section[data-testid="stSidebar"] { background: #171a21; }
.hero {
  background: linear-gradient(90deg, rgba(102,192,244,0.20), rgba(26,159,255,0.04));
  border: 1px solid rgba(102,192,244,0.28);
  border-radius: 14px; padding: 20px 24px; margin-bottom: 10px;
}
.hero h1 { color: #ffffff; margin: 0; font-size: 2rem; letter-spacing: .5px; }
.hero p { color: #8f98a0; margin: 6px 0 0 0; }
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #2a475e 0%, #1b2838 100%);
  border: 1px solid rgba(102,192,244,0.22);
  border-radius: 12px; padding: 14px 16px;
}
[data-testid="stMetricValue"] { color: #66c0f4; }
[data-testid="stMetricLabel"] { color: #8f98a0; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
  background: #1b2838; border-radius: 8px 8px 0 0; padding: 8px 16px; color: #c7d5e0;
}
.stTabs [aria-selected="true"] { background: #2a475e; color: #66c0f4; }
.section-note { color: #6d7986; font-size: 0.82rem; }
</style>
"""
st.markdown(STEAM_CSS, unsafe_allow_html=True)


def style_fig(fig, height: int = 420, legend: bool = True):
    """Apply the Steam dark visual theme to a Plotly figure."""
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(23,40,56,0.35)",
        font=dict(color="#c7d5e0", family="Arial"),
        title_text="",
        legend=dict(bgcolor="rgba(0,0,0,0)", title_font_color="#8f98a0"),
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=legend,
        colorway=STEAM_COLORS,
    )
    grid = "rgba(102,192,244,0.12)"
    fig.update_xaxes(gridcolor=grid, zeroline=False)
    fig.update_yaxes(gridcolor=grid, zeroline=False)
    return fig


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    games = genre = usage = report = None
    if config.GAMES_FILE.exists():
        games = pd.read_csv(config.GAMES_FILE)
    if config.GENRE_SUMMARY_FILE.exists():
        genre = pd.read_csv(config.GENRE_SUMMARY_FILE)
    if config.USAGE_DAILY_FILE.exists():
        usage = pd.read_csv(config.USAGE_DAILY_FILE, parse_dates=["date"])
    if config.QUALITY_REPORT_FILE.exists():
        report = json.loads(config.QUALITY_REPORT_FILE.read_text(encoding="utf-8"))
    return games, genre, usage, report


games, genre_summary, usage, report = load_data()

st.markdown(
    '<div class="hero"><h1>🎮 Steam Games Insights</h1>'
    "<p>Analytics on the most-played Steam games &mdash; powered by the free, "
    "keyless SteamSpy API.</p></div>",
    unsafe_allow_html=True,
)

if games is None or usage is None:
    st.warning(
        "No processed data found. Please run the ETL pipeline first:\n\n"
        "```bash\npython etl.py\n```"
    )
    st.stop()


# --------------------------------------------------------------------------
# Reusable per-section filter UI (title, publisher, country, date)
# --------------------------------------------------------------------------
def usage_filters(df: pd.DataFrame, key: str, default_titles: int = 8) -> pd.DataFrame:
    """Render a filter row for a usage section and return the filtered frame."""
    with st.expander("🔎 Filters — title · publisher · country · date", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        titles_all = sorted(df["name"].unique())
        top_titles = (
            df.groupby("name")["players"].sum()
            .sort_values(ascending=False)
            .head(default_titles)
            .index.tolist()
        )
        with c1:
            sel_titles = st.multiselect(
                "Title", titles_all, default=top_titles, key=f"title_{key}"
            )
        with c2:
            pubs = sorted(df["publisher"].unique())
            sel_pubs = st.multiselect(
                "Publisher", pubs, default=pubs, key=f"pub_{key}"
            )
        with c3:
            countries = sorted(df["country"].unique())
            sel_countries = st.multiselect(
                "Country", countries, default=countries, key=f"country_{key}"
            )
        with c4:
            dmin, dmax = df["date"].min().date(), df["date"].max().date()
            dr = st.date_input(
                "Date range", (dmin, dmax), min_value=dmin, max_value=dmax,
                key=f"date_{key}",
            )

    start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax))
    if not sel_titles:
        sel_titles = top_titles
    mask = (
        df["name"].isin(sel_titles)
        & df["publisher"].isin(sel_pubs or df["publisher"].unique())
        & df["country"].isin(sel_countries or df["country"].unique())
        & df["date"].dt.date.between(start, end)
    )
    return df.loc[mask].copy()


# --------------------------------------------------------------------------
# Header KPIs (snapshot)
# --------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Games tracked", len(games))
k2.metric("Avg review score", f"{games['review_ratio'].mean():.0f}%")
k3.metric("Live players (CCU)", f"{int(games['ccu'].sum()):,}")
k4.metric("Countries modeled", usage["country"].nunique())
k5.metric("Days of usage", usage["date"].dt.date.nunique())

st.divider()

tab_overview, tab_usage, tab_players, tab_market, tab_quality, tab_data = st.tabs(
    [
        "🏠 Overview",
        "🎮 Title Usage",
        "👥 Active Players",
        "📊 Market Snapshot",
        "✅ Data Quality",
        "🗂️ Data",
    ]
)

# ==========================================================================
# OVERVIEW
# ==========================================================================
with tab_overview:
    st.subheader("Live concurrent players — top 15")
    top_ccu = games.sort_values("ccu", ascending=False).head(15)
    fig = px.bar(
        top_ccu, x="ccu", y="name", orientation="h",
        labels={"ccu": "Concurrent players", "name": ""},
        color="ccu", color_continuous_scale=["#1a3a5c", "#66c0f4"],
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
    st.plotly_chart(style_fig(fig, 480, legend=False), width="stretch")

    st.subheader("Total active players by date (all tracked titles)")
    daily_total = usage.groupby("date", as_index=False)["players"].sum()
    fig = px.area(daily_total, x="date", y="players", labels={"players": "Players", "date": ""})
    fig.update_traces(line_color="#66c0f4", fillcolor="rgba(102,192,244,0.20)")
    st.plotly_chart(style_fig(fig, 340, legend=False), width="stretch")
    st.markdown(
        '<span class="section-note">Daily &amp; country figures are modeled '
        "estimates derived from the SteamSpy snapshot (see README).</span>",
        unsafe_allow_html=True,
    )

# ==========================================================================
# TITLE USAGE OVERVIEW  (usage of each game by date)
# ==========================================================================
with tab_usage:
    st.subheader("Title usage overview")
    st.caption("Engagement (player-hours) for each title over time.")
    f = usage_filters(usage, key="usage")
    if f.empty:
        st.info("No data for the selected filters.")
    else:
        by_date = f.groupby(["date", "name"], as_index=False)["usage_hours"].sum()
        fig = px.line(
            by_date, x="date", y="usage_hours", color="name", markers=False,
            labels={"usage_hours": "Usage (player-hours)", "date": "", "name": "Title"},
        )
        fig.update_traces(line=dict(width=2.4))
        st.plotly_chart(style_fig(fig, 460), width="stretch")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.subheader("Total usage by title")
            totals = (
                f.groupby("name", as_index=False)["usage_hours"].sum()
                .sort_values("usage_hours")
            )
            figb = px.bar(
                totals, x="usage_hours", y="name", orientation="h",
                labels={"usage_hours": "Usage (player-hours)", "name": ""},
                color="usage_hours", color_continuous_scale=["#1a3a5c", "#66c0f4"],
            )
            figb.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(figb, 420, legend=False), width="stretch")
        with c2:
            st.subheader("Usage share by country")
            by_country = (
                f.groupby("country", as_index=False)["usage_hours"].sum()
                .sort_values("usage_hours", ascending=False)
            )
            figc = px.pie(
                by_country, names="country", values="usage_hours", hole=0.45,
                color_discrete_sequence=STEAM_COLORS,
            )
            st.plotly_chart(style_fig(figc, 420), width="stretch")

# ==========================================================================
# ACTIVE PLAYERS BY DATE  (number of users playing by date)
# ==========================================================================
with tab_players:
    st.subheader("Active players by date")
    st.caption("Estimated number of users playing each title over time.")
    f = usage_filters(usage, key="players")
    if f.empty:
        st.info("No data for the selected filters.")
    else:
        by_date = f.groupby(["date", "name"], as_index=False)["players"].sum()
        fig = px.line(
            by_date, x="date", y="players", color="name",
            labels={"players": "Active players", "date": "", "name": "Title"},
        )
        fig.update_traces(line=dict(width=2.4))
        st.plotly_chart(style_fig(fig, 460), width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Players by country")
            by_country = (
                f.groupby("country", as_index=False)["players"].sum()
                .sort_values("players")
            )
            figb = px.bar(
                by_country, x="players", y="country", orientation="h",
                labels={"players": "Active players", "country": ""},
                color="players", color_continuous_scale=["#1a3a5c", "#66c0f4"],
            )
            figb.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(figb, 420, legend=False), width="stretch")
        with c2:
            st.subheader("Average daily players by title")
            avg_players = (
                f.groupby(["date", "name"])["players"].sum().reset_index()
                .groupby("name", as_index=False)["players"].mean()
                .sort_values("players")
            )
            figc = px.bar(
                avg_players, x="players", y="name", orientation="h",
                labels={"players": "Avg daily players", "name": ""},
                color="players", color_continuous_scale=["#1a3a5c", "#a4d007"],
            )
            figc.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(figc, 420, legend=False), width="stretch")

        st.subheader("Daily players by country (stacked)")
        stacked = f.groupby(["date", "country"], as_index=False)["players"].sum()
        figs = px.bar(
            stacked, x="date", y="players", color="country",
            labels={"players": "Active players", "date": "", "country": "Country"},
        )
        st.plotly_chart(style_fig(figs, 420), width="stretch")

# ==========================================================================
# MARKET SNAPSHOT  (reception, pricing, genres)
# ==========================================================================
with tab_market:
    st.subheader("Market snapshot")
    with st.expander("🔎 Filters — genre · price · publisher", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            genres = sorted(games["primary_genre"].dropna().unique())
            sel_g = st.multiselect("Genre", genres, default=genres, key="mkt_genre")
        with c2:
            price_type = st.radio("Price type", ["All", "Free", "Paid"], key="mkt_price")
        with c3:
            pubs = sorted(games["publisher"].dropna().unique())
            sel_p = st.multiselect("Publisher", pubs, default=pubs, key="mkt_pub")

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
            st.subheader("Reception vs. audience size")
            fig = px.scatter(
                gv, x="owners_mid", y="review_ratio", size="ccu",
                color="primary_genre", hover_name="name", log_x=True,
                labels={"owners_mid": "Estimated owners", "review_ratio": "Positive %"},
            )
            st.plotly_chart(style_fig(fig, 430), width="stretch")
        with c2:
            st.subheader("Price distribution (paid)")
            paid = gv[~gv["is_free"]]
            if paid.empty:
                st.info("No paid games in this selection.")
            else:
                fig = px.histogram(paid, x="price_usd", nbins=20, labels={"price_usd": "Price (USD)"})
                fig.update_traces(marker_color="#66c0f4")
                st.plotly_chart(style_fig(fig, 430, legend=False), width="stretch")

        gsel = genre_summary[genre_summary["primary_genre"].isin(sel_g)]
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Live players by genre")
            fig = px.bar(
                gsel.sort_values("total_ccu"), x="total_ccu", y="primary_genre",
                orientation="h", labels={"total_ccu": "Concurrent players", "primary_genre": ""},
                color="total_ccu", color_continuous_scale=["#1a3a5c", "#66c0f4"],
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")
        with c4:
            st.subheader("Avg review score by genre")
            fig = px.bar(
                gsel.sort_values("avg_review_ratio"), x="avg_review_ratio",
                y="primary_genre", orientation="h",
                labels={"avg_review_ratio": "Avg positive %", "primary_genre": ""},
                color="avg_review_ratio", color_continuous_scale="RdYlGn",
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")

# ==========================================================================
# DATA QUALITY
# ==========================================================================
with tab_quality:
    st.subheader("Data quality report")
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
# DATA
# ==========================================================================
with tab_data:
    st.subheader("Processed games (snapshot)")
    st.dataframe(games, width="stretch", hide_index=True)
    st.subheader("Modeled daily usage")
    st.dataframe(usage.head(1000), width="stretch", hide_index=True)
    st.download_button(
        "Download usage data (CSV)",
        data=usage.to_csv(index=False).encode("utf-8"),
        file_name="usage_daily.csv",
        mime="text/csv",
    )

st.caption("Data source: SteamSpy · Daily & country figures are modeled estimates · AI Data Engineer assignment.")
