"""Transformation layer.

Turns the raw SteamSpy records into two tidy analytical tables:

* ``games``          - one clean row per game with derived metrics.
* ``genre_summary``  - one row per primary genre aggregating the games.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from . import config, utils

logger = utils.get_logger()


def _parse_owners(value: Any) -> tuple[float, float]:
    """Parse SteamSpy owners bucket like '1,000,000 .. 2,000,000'.

    Returns (min, max). Missing/unparseable values yield (nan, nan).
    """
    if not isinstance(value, str) or ".." not in value:
        return float("nan"), float("nan")
    try:
        low, high = value.split("..")
        low_n = float(low.replace(",", "").strip())
        high_n = float(high.replace(",", "").strip())
        return low_n, high_n
    except (ValueError, AttributeError):
        return float("nan"), float("nan")


def _to_float(value: Any) -> float:
    """Best-effort numeric coercion (SteamSpy sends numbers as strings)."""
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, AttributeError, TypeError):
        return float("nan")


def _top_tags(tags: Any, n: int = 3) -> str:
    """Return the top-n tag names by vote count as a comma-joined string."""
    if isinstance(tags, dict) and tags:
        ranked = sorted(tags.items(), key=lambda kv: kv[1], reverse=True)
        return ", ".join(name for name, _ in ranked[:n])
    return ""


def _rating_label(row: pd.Series) -> str:
    """Bucket a game into a reception label based on review ratio + volume."""
    total = row.get("total_reviews", 0)
    ratio = row.get("review_ratio", float("nan"))
    if pd.isna(ratio) or total < config.MIN_REVIEWS_FOR_LABEL:
        return "Insufficient data"
    if ratio >= config.RATING_POSITIVE:
        return "Positive"
    if ratio >= config.RATING_MIXED:
        return "Mixed"
    return "Negative"


def build_games(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Combine raw game records into one tidy, typed, enriched table."""
    if not records:
        raise ValueError("No game records to transform.")

    rows: list[dict[str, Any]] = []
    for g in records:
        owners_min, owners_max = _parse_owners(g.get("owners"))
        positive = _to_float(g.get("positive"))
        negative = _to_float(g.get("negative"))
        total = (0 if pd.isna(positive) else positive) + (
            0 if pd.isna(negative) else negative
        )
        genre_raw = (g.get("genre") or "").strip()
        primary_genre = genre_raw.split(",")[0].strip() if genre_raw else "Unknown"

        rows.append(
            {
                "appid": g.get("appid"),
                "name": g.get("name"),
                "developer": g.get("developer") or "Unknown",
                "publisher": g.get("publisher") or "Unknown",
                "positive": positive,
                "negative": negative,
                "total_reviews": total,
                "ccu": _to_float(g.get("ccu")),
                "owners_min": owners_min,
                "owners_max": owners_max,
                "price_usd": _to_float(g.get("price")) / 100.0,
                "initial_price_usd": _to_float(g.get("initialprice")) / 100.0,
                "discount_pct": _to_float(g.get("discount")),
                "avg_playtime_hours": _to_float(g.get("average_forever")) / 60.0,
                "median_playtime_hours": _to_float(g.get("median_forever")) / 60.0,
                "primary_genre": primary_genre,
                "all_genres": genre_raw,
                "top_tags": _top_tags(g.get("tags")),
            }
        )

    df = pd.DataFrame(rows)

    # Derived metrics
    df["review_ratio"] = (df["positive"] / df["total_reviews"].replace(0, pd.NA)) * 100
    df["review_ratio"] = df["review_ratio"].round(1)
    df["owners_mid"] = (df["owners_min"] + df["owners_max"]) / 2
    df["is_free"] = df["price_usd"].fillna(0).eq(0)
    df["on_sale"] = df["discount_pct"].fillna(0) > 0
    df["rating_label"] = df.apply(_rating_label, axis=1)

    df = df.sort_values("ccu", ascending=False).reset_index(drop=True)
    logger.info(
        "Built games table: %s rows, %s genres",
        len(df),
        df["primary_genre"].nunique(),
    )
    return df


def build_genre_summary(games: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the games table into one row per primary genre."""
    summary = (
        games.groupby("primary_genre", as_index=False)
        .agg(
            games=("appid", "nunique"),
            avg_review_ratio=("review_ratio", "mean"),
            total_ccu=("ccu", "sum"),
            avg_price_usd=("price_usd", "mean"),
            total_owners_mid=("owners_mid", "sum"),
            free_games=("is_free", "sum"),
        )
    )
    numeric = summary.select_dtypes("number").columns
    summary[numeric] = summary[numeric].round(2)
    summary = summary.sort_values("total_ccu", ascending=False).reset_index(drop=True)
    return summary


def transform(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full transform step and persist the processed tables."""
    utils.ensure_directories()
    games = build_games(records)
    genre_summary = build_genre_summary(games)

    games.to_csv(config.GAMES_FILE, index=False)
    genre_summary.to_csv(config.GENRE_SUMMARY_FILE, index=False)
    logger.info(
        "Wrote %s and %s", config.GAMES_FILE.name, config.GENRE_SUMMARY_FILE.name
    )
    return games, genre_summary
