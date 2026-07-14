"""Modeled daily-usage layer.

SteamSpy's free API is a point-in-time *snapshot*: it has no per-day history
and no per-country breakdown. To power the dashboard's time-series and country
views, this module derives a **deterministic, clearly-labeled** daily-usage
fact table from the real snapshot metrics (concurrent users, playtime,
publisher).

The output is an *estimate*, not measured data. It is seeded per appid so the
result is fully reproducible across runs, and it is documented as modeled in
the README and surfaced with a caption in the dashboard.

Output columns (``usage_daily.csv``):
    date, appid, name, publisher, primary_genre, country, players, sessions, usage_hours
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, utils

logger = utils.get_logger()


def build_usage_daily(
    games: pd.DataFrame, days: int | None = None, top_n: int | None = None
) -> pd.DataFrame:
    """Derive a deterministic daily usage fact table from the games table."""
    days = days or config.USAGE_DAYS
    top_n = top_n or config.USAGE_TOP_N

    country_names = list(config.COUNTRIES.keys())
    country_weights = np.array(list(config.COUNTRIES.values()), dtype=float)

    end = pd.Timestamp.today().normalize()
    dates = pd.date_range(end - pd.Timedelta(days=days - 1), end, freq="D")
    span = max(len(dates) - 1, 1)

    subset = games.sort_values("ccu", ascending=False).head(top_n)
    rows: list[dict] = []

    for _, g in subset.iterrows():
        appid = int(g["appid"])
        rng = np.random.default_rng(appid)  # deterministic per game

        ccu = float(g["ccu"]) if not pd.isna(g["ccu"]) else 0.0
        dau_base = max(ccu * config.DAU_FACTOR, 100.0)

        median_h = (
            float(g["median_playtime_hours"])
            if not pd.isna(g.get("median_playtime_hours"))
            else 0.0
        )
        session_hours = float(np.clip(median_h / 10 if median_h > 0 else 1.5, 0.5, 4.0))
        # Average number of sessions a user starts per day for this title.
        sessions_per_user = float(np.clip(rng.normal(1.6, 0.3), 1.0, 3.0))
        trend = rng.uniform(-0.15, 0.20)  # gentle rise/decline over the window

        for i, day in enumerate(dates):
            weekend = config.WEEKEND_UPLIFT if day.weekday() >= 5 else 1.0
            trend_factor = 1 + trend * (i / span)
            noise = max(rng.normal(1.0, 0.06), 0.5)
            global_players = dau_base * weekend * trend_factor * noise

            cnoise = np.clip(rng.normal(1.0, 0.05, size=len(country_names)), 0.7, 1.3)
            shares = country_weights * cnoise
            shares = shares / shares.sum()

            for cname, share in zip(country_names, shares):
                players = int(round(global_players * share))
                if players <= 0:
                    continue
                sessions = int(
                    round(
                        players
                        * sessions_per_user
                        * float(np.clip(rng.normal(1.0, 0.05), 0.85, 1.15))
                    )
                )
                usage_hours = round(
                    players
                    * session_hours
                    * float(np.clip(rng.normal(1.0, 0.05), 0.8, 1.2)),
                    1,
                )
                rows.append(
                    {
                        "date": day,
                        "appid": appid,
                        "name": g["name"],
                        "publisher": g["publisher"],
                        "primary_genre": g["primary_genre"],
                        "country": cname,
                        "players": players,
                        "sessions": sessions,
                        "usage_hours": usage_hours,
                    }
                )

    df = pd.DataFrame(rows)
    logger.info(
        "Built modeled usage table: %s rows (%s games x %s days x %s countries)",
        len(df),
        subset.shape[0],
        len(dates),
        len(country_names),
    )
    return df


def build_and_save(games: pd.DataFrame) -> pd.DataFrame:
    """Build the usage table and persist it to processed/."""
    utils.ensure_directories()
    df = build_usage_daily(games)
    df.to_csv(config.USAGE_DAILY_FILE, index=False)
    logger.info("Wrote %s", config.USAGE_DAILY_FILE.name)
    return df
