"""Modeled monthly growth-metrics layer.

Builds a deterministic monthly time-series (MAU, DAU, new users, sessions,
hours) spanning ~30 months so the dashboard can show month-over-month and
year-over-year growth, increments/decrements, and new-user acquisition.

Like the daily layer, this is a **modeled estimate** (SteamSpy has no
historical monthly data). It is seeded so runs are reproducible and is
clearly labeled as modeled in the README and the dashboard.

Output columns (``monthly_metrics.csv``):
    month, month_date, year, month_num, month_name,
    mau, dau, new_users, sessions, hours, hours_per_user
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, utils

logger = utils.get_logger()


def build_monthly_metrics(
    games: pd.DataFrame, start: str | None = None, end: str | None = None
) -> pd.DataFrame:
    """Derive a deterministic monthly growth series from the snapshot."""
    start = start or config.GROWTH_START
    end = end or config.GROWTH_END
    rng = np.random.default_rng(2024)

    total_ccu = float(games["ccu"].sum()) if "ccu" in games else 1_000_000.0
    base_mau = max(total_ccu * config.MAU_BASE_MULTIPLIER, 1_000_000.0)

    months = pd.period_range(start, end, freq="M")
    rows: list[dict] = []
    for i, m in enumerate(months):
        growth = (1 + config.MONTHLY_GROWTH) ** i
        # Seasonality: peaks in winter (Dec/Jan), dips mid-year.
        seasonal = 1 + 0.12 * np.cos((m.month - 1) / 12 * 2 * np.pi)
        noise = float(np.clip(rng.normal(1.0, 0.03), 0.9, 1.1))

        mau = base_mau * growth * seasonal * noise
        dau = mau * float(np.clip(rng.normal(0.18, 0.02), 0.12, 0.26))
        new_users = mau * float(np.clip(rng.normal(0.11, 0.02), 0.05, 0.20))
        sessions = mau * float(np.clip(rng.normal(9.0, 1.0), 6.0, 13.0))
        hours_per_user = float(np.clip(rng.normal(7.5, 1.0), 4.0, 12.0))
        hours = mau * hours_per_user

        rows.append(
            {
                "month": str(m),
                "month_date": m.to_timestamp(),
                "year": int(m.year),
                "month_num": int(m.month),
                "month_name": m.strftime("%b"),
                "mau": int(round(mau)),
                "dau": int(round(dau)),
                "new_users": int(round(new_users)),
                "sessions": int(round(sessions)),
                "hours": int(round(hours)),
                "hours_per_user": round(hours_per_user, 2),
            }
        )

    df = pd.DataFrame(rows)
    logger.info("Built modeled monthly metrics: %s months", len(df))
    return df


def build_and_save(games: pd.DataFrame) -> pd.DataFrame:
    """Build the monthly metrics table and persist it to processed/."""
    utils.ensure_directories()
    df = build_monthly_metrics(games)
    df.to_csv(config.MONTHLY_METRICS_FILE, index=False)
    logger.info("Wrote %s", config.MONTHLY_METRICS_FILE.name)
    return df
