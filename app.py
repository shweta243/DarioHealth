"""Steam Games Insights - Streamlit dashboard.

Business-facing view of the processed Steam data. Reads the CSV/JSON
outputs produced by ``etl.py`` and presents KPIs, popularity, reception,
pricing and genre insights plus a transparent data-quality panel.

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
# Data loading
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict | None]:
    """Load processed outputs. Returns (games, genre_summary, quality_report)."""
    games = genre = report = None
    if config.GAMES_FILE.exists():
        games = pd.read_csv(config.GAMES_FILE)
    if config.GENRE_SUMMARY_FILE.exists():
        genre = pd.read_csv(config.GENRE_SUMMARY_FILE)
    if config.QUALITY_REPORT_FILE.exists():
        report = json.loads(config.QUALITY_REPORT_FILE.read_text(encoding="utf-8"))
    return games, genre, report


games, genre_summary, report = load_data()

st.title("🎮 Steam Games Insights")
st.caption(
    "Analytics on the most-played Steam games, powered by the free, keyless "
    "[SteamSpy](https://steamspy.com) API."
)

if games is None:
    st.warning(
        "No processed data found. Please run the ETL pipeline first:\n\n"
        "```bash\npython etl.py\n```"
    )
    st.stop()


# --------------------------------------------------------------------------
# Sidebar filters
# --------------------------------------------------------------------------
st.sidebar.header("Filters")

all_genres = sorted(games["primary_genre"].dropna().unique())
selected_genres = st.sidebar.multiselect(
    "Genre", options=all_genres, default=all_genres
)

price_type = st.sidebar.radio("Price type", ["All", "Free only", "Paid only"])

max_price = float(games["price_usd"].fillna(0).max())
price_range = st.sidebar.slider(
    "Price range (USD)", 0.0, round(max_price, 2), (0.0, round(max_price, 2))
)

min_reviews = st.sidebar.number_input(
    "Minimum total reviews", min_value=0, value=0, step=1000
)

mask = (
    games["primary_genre"].isin(selected_genres)
    & games["price_usd"].fillna(0).between(price_range[0], price_range[1])
    & (games["total_reviews"].fillna(0) >= min_reviews)
)
if price_type == "Free only":
    mask &= games["is_free"]
elif price_type == "Paid only":
    mask &= ~games["is_free"]

view = games.loc[mask].copy()

if view.empty:
    st.info("No games match the selected filters.")
    st.stop()


# --------------------------------------------------------------------------
# KPI row
# --------------------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Games", len(view))
col2.metric("Avg review score", f"{view['review_ratio'].mean():.0f}%")
col3.metric("Live players (CCU)", f"{int(view['ccu'].sum()):,}")
col4.metric("Free games", int(view["is_free"].sum()))
col5.metric("Avg price", f"${view['price_usd'].mean():.2f}")

top_now = view.sort_values("ccu", ascending=False).iloc[0]
st.success(
    f"🔥 Most-played right now in this view: **{top_now['name']}** "
    f"({int(top_now['ccu']):,} concurrent players, "
    f"{top_now['review_ratio']:.0f}% positive)."
)

st.divider()


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
tab_pop, tab_recep, tab_price, tab_genre, tab_quality, tab_data = st.tabs(
    [
        "🏆 Popularity",
        "⭐ Reception",
        "💵 Pricing",
        "🎯 Genres",
        "✅ Data quality",
        "🗂️ Data",
    ]
)

with tab_pop:
    st.subheader("Live concurrent players (top 15)")
    top_ccu = view.sort_values("ccu", ascending=False).head(15)
    fig_ccu = px.bar(
        top_ccu,
        x="ccu",
        y="name",
        orientation="h",
        color="ccu",
        color_continuous_scale="Blues",
        labels={"ccu": "Concurrent players", "name": ""},
    )
    fig_ccu.update_layout(
        height=500, coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"}
    )
    st.plotly_chart(fig_ccu, width="stretch")

    st.subheader("Estimated owners (mid-point, top 15)")
    top_owners = view.sort_values("owners_mid", ascending=False).head(15)
    fig_owners = px.bar(
        top_owners,
        x="owners_mid",
        y="name",
        orientation="h",
        color="owners_mid",
        color_continuous_scale="Greens",
        labels={"owners_mid": "Estimated owners", "name": ""},
    )
    fig_owners.update_layout(
        height=500, coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"}
    )
    st.plotly_chart(fig_owners, width="stretch")

with tab_recep:
    st.subheader("Reception vs. popularity")
    fig_scatter = px.scatter(
        view,
        x="owners_mid",
        y="review_ratio",
        size="ccu",
        color="primary_genre",
        hover_name="name",
        labels={
            "owners_mid": "Estimated owners",
            "review_ratio": "Positive reviews (%)",
        },
        log_x=True,
    )
    fig_scatter.update_layout(height=480, legend_title_text="Genre")
    st.plotly_chart(fig_scatter, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Rating label mix")
        label_counts = (
            view["rating_label"].value_counts().rename_axis("label").reset_index(name="games")
        )
        fig_labels = px.pie(
            label_counts,
            names="label",
            values="games",
            color="label",
            color_discrete_map={
                "Positive": "#2ecc71",
                "Mixed": "#f1c40f",
                "Negative": "#e74c3c",
                "Insufficient data": "#95a5a6",
            },
        )
        fig_labels.update_layout(height=380)
        st.plotly_chart(fig_labels, width="stretch")
    with c2:
        st.subheader("Best reviewed (min reviews applied)")
        best = view.sort_values("review_ratio", ascending=False).head(10)[
            ["name", "review_ratio", "total_reviews"]
        ]
        st.dataframe(
            best.rename(
                columns={
                    "name": "Game",
                    "review_ratio": "Positive %",
                    "total_reviews": "Reviews",
                }
            ),
            width="stretch",
            hide_index=True,
        )

with tab_price:
    st.subheader("Price distribution (paid games)")
    paid = view[~view["is_free"]]
    if paid.empty:
        st.info("No paid games in the current selection.")
    else:
        fig_price = px.histogram(
            paid, x="price_usd", nbins=20, labels={"price_usd": "Price (USD)"}
        )
        fig_price.update_layout(height=380, yaxis_title="Games")
        st.plotly_chart(fig_price, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Free vs. paid")
        fp = pd.DataFrame(
            {
                "type": ["Free", "Paid"],
                "games": [int(view["is_free"].sum()), int((~view["is_free"]).sum())],
            }
        )
        fig_fp = px.bar(
            fp, x="type", y="games", color="type", labels={"games": "Games", "type": ""}
        )
        fig_fp.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_fp, width="stretch")
    with c2:
        st.subheader("Games on sale")
        on_sale = view[view["on_sale"]].sort_values("discount_pct", ascending=False)
        if on_sale.empty:
            st.info("No games are currently discounted in this selection.")
        else:
            st.dataframe(
                on_sale[["name", "price_usd", "initial_price_usd", "discount_pct"]]
                .rename(
                    columns={
                        "name": "Game",
                        "price_usd": "Price",
                        "initial_price_usd": "Was",
                        "discount_pct": "Discount %",
                    }
                )
                .head(15),
                width="stretch",
                hide_index=True,
            )

with tab_genre:
    genre_view = genre_summary[genre_summary["primary_genre"].isin(selected_genres)]
    st.subheader("Games per genre")
    fig_g1 = px.bar(
        genre_view.sort_values("games"),
        x="games",
        y="primary_genre",
        orientation="h",
        labels={"games": "Games", "primary_genre": ""},
    )
    fig_g1.update_layout(height=420)
    st.plotly_chart(fig_g1, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Avg review score by genre")
        fig_g2 = px.bar(
            genre_view.sort_values("avg_review_ratio"),
            x="avg_review_ratio",
            y="primary_genre",
            orientation="h",
            color="avg_review_ratio",
            color_continuous_scale="RdYlGn",
            labels={"avg_review_ratio": "Avg positive %", "primary_genre": ""},
        )
        fig_g2.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_g2, width="stretch")
    with c2:
        st.subheader("Live players by genre")
        fig_g3 = px.bar(
            genre_view.sort_values("total_ccu"),
            x="total_ccu",
            y="primary_genre",
            orientation="h",
            labels={"total_ccu": "Concurrent players", "primary_genre": ""},
        )
        fig_g3.update_layout(height=400)
        st.plotly_chart(fig_g3, width="stretch")

    st.subheader("Genre summary")
    st.dataframe(genre_view, width="stretch", hide_index=True)

with tab_quality:
    st.subheader("Data quality report")
    if report is None:
        st.info("No quality report found. Re-run `python etl.py`.")
    else:
        overall = report["overall_status"].upper()
        if overall == "PASS":
            st.success(
                f"Overall status: **{overall}** — "
                f"{report['checks_passed']}/{report['checks_total']} checks passed."
            )
        else:
            st.error(
                f"Overall status: **{overall}** — "
                f"{report['checks_failed']} check(s) failed."
            )
        q1, q2, q3 = st.columns(3)
        q1.metric("Games validated", report["rows"])
        q2.metric("Genres", report["genres"])
        q3.metric("Checks passed", f"{report['checks_passed']}/{report['checks_total']}")

        checks_df = pd.DataFrame(report["checks"])[["check", "status", "detail"]]
        st.dataframe(
            checks_df.rename(
                columns={"check": "Check", "status": "Status", "detail": "Detail"}
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(f"Report generated at {report['generated_at']}")

with tab_data:
    st.subheader("Processed games data")
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button(
        "Download filtered data (CSV)",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name="filtered_steam_games.csv",
        mime="text/csv",
    )

st.caption("Data source: SteamSpy · Built for the AI Data Engineer assignment.")
