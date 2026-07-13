"""Data-quality layer.

Runs explicit, business-meaningful checks over the processed games table
and returns a structured report. Each check reports pass/fail plus
supporting numbers so issues are visible in the dashboard rather than
silently ignored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype, is_object_dtype, is_string_dtype

from . import config, utils

logger = utils.get_logger()


EXPECTED_COLUMNS = {
    "appid",
    "name",
    "developer",
    "publisher",
    "positive",
    "negative",
    "total_reviews",
    "ccu",
    "owners_min",
    "owners_max",
    "owners_mid",
    "price_usd",
    "initial_price_usd",
    "discount_pct",
    "avg_playtime_hours",
    "median_playtime_hours",
    "primary_genre",
    "all_genres",
    "top_tags",
    "review_ratio",
    "is_free",
    "on_sale",
    "rating_label",
}

NUMERIC_COLUMNS = {
    "appid",
    "positive",
    "negative",
    "total_reviews",
    "ccu",
    "owners_min",
    "owners_max",
    "owners_mid",
    "price_usd",
    "initial_price_usd",
    "discount_pct",
    "avg_playtime_hours",
    "median_playtime_hours",
    "review_ratio",
}

TEXT_COLUMNS = {
    "name",
    "developer",
    "publisher",
    "primary_genre",
    "all_genres",
    "top_tags",
    "rating_label",
}

BOOL_COLUMNS = {"is_free", "on_sale"}
KEY_COLUMNS = {"appid", "name", "developer", "publisher", "primary_genre"}


def _check(name: str, passed: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "check": name,
        "status": "pass" if passed else "fail",
        "detail": detail,
        **extra,
    }


def _missing_columns(df: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required - set(df.columns))


def _valid_bool_series(series: pd.Series) -> bool:
    if is_bool_dtype(series):
        return True
    valid = {True, False, 0, 1}
    values = set(series.dropna().unique().tolist())
    return values.issubset(valid)


def run_quality_checks(
    games: pd.DataFrame, expected_games: int | None = None, save: bool = True
) -> dict[str, Any]:
    """Validate the processed games table and return a report dict."""
    checks: list[dict[str, Any]] = []
    n_rows = len(games)

    # 1. Non-empty dataset
    checks.append(
        _check("non_empty", n_rows > 0, f"{n_rows} games produced", rows=n_rows)
    )

    # 2. Schema columns present
    missing = _missing_columns(games, EXPECTED_COLUMNS)
    checks.append(
        _check(
            "schema_columns_present",
            len(missing) == 0,
            "All expected columns are present"
            if not missing
            else f"Missing columns: {', '.join(missing)}",
            missing_count=len(missing),
            missing_columns=missing,
        )
    )

    # 3. Schema data types are compatible (numeric/text/boolean)
    bad_numeric = sorted(c for c in NUMERIC_COLUMNS if c in games and not is_numeric_dtype(games[c]))
    bad_text = sorted(
        c
        for c in TEXT_COLUMNS
        if c in games and not (is_string_dtype(games[c]) or is_object_dtype(games[c]))
    )
    bad_bool = sorted(c for c in BOOL_COLUMNS if c in games and not _valid_bool_series(games[c]))
    type_ok = not (bad_numeric or bad_text or bad_bool)
    checks.append(
        _check(
            "schema_types_valid",
            type_ok,
            "Column dtypes are compatible with expected schema"
            if type_ok
            else "Invalid dtypes found",
            invalid_numeric=bad_numeric,
            invalid_text=bad_text,
            invalid_bool=bad_bool,
        )
    )

    # 4. Key fields are not null/empty
    key_missing_total = 0
    key_missing_by_column: dict[str, int] = {}
    for col in sorted(KEY_COLUMNS):
        if col not in games:
            key_missing_by_column[col] = n_rows
            key_missing_total += n_rows
            continue
        missing_n = int(games[col].isna().sum())
        if is_object_dtype(games[col]) or is_string_dtype(games[col]):
            missing_n += int(games[col].astype(str).str.strip().eq("").sum())
        key_missing_by_column[col] = missing_n
        key_missing_total += missing_n
    checks.append(
        _check(
            "key_fields_not_null",
            key_missing_total == 0,
            "All key fields are populated"
            if key_missing_total == 0
            else f"{key_missing_total} null/empty key values found",
            missing_total=key_missing_total,
            missing_by_column=key_missing_by_column,
        )
    )

    # 5. Expected coverage
    expected = expected_games if expected_games is not None else n_rows
    checks.append(
        _check(
            "game_coverage",
            n_rows >= expected,
            f"{n_rows}/{expected} games present",
            games_present=n_rows,
            games_expected=expected,
        )
    )

    # 6. No duplicate appids
    dup = int(games.duplicated(subset=["appid"]).sum()) if "appid" in games else n_rows
    checks.append(
        _check("no_duplicate_appids", dup == 0, f"{dup} duplicate appids", duplicates=dup)
    )

    # 7. No missing names
    missing_names = (
        int(games["name"].isna().sum() + games["name"].astype(str).str.strip().eq("").sum())
        if "name" in games
        else n_rows
    )
    checks.append(
        _check(
            "names_present",
            missing_names == 0,
            f"{missing_names} games with missing name",
            missing=missing_names,
        )
    )

    # 8. Non-negative review counts
    if {"positive", "negative"}.issubset(games.columns):
        neg_reviews = int(((games["positive"] < 0) | (games["negative"] < 0)).sum())
    else:
        neg_reviews = n_rows
    checks.append(
        _check(
            "reviews_non_negative",
            neg_reviews == 0,
            f"{neg_reviews} rows with negative review counts",
            invalid=neg_reviews,
        )
    )

    # 9. Total reviews are consistent with positive + negative
    if {"positive", "negative", "total_reviews"}.issubset(games.columns):
        expected_total = games["positive"].fillna(0) + games["negative"].fillna(0)
        bad_total = int((games["total_reviews"].fillna(0) != expected_total).sum())
    else:
        bad_total = n_rows
    checks.append(
        _check(
            "total_reviews_consistent",
            bad_total == 0,
            f"{bad_total} rows where total_reviews != positive + negative",
            invalid=bad_total,
        )
    )

    # 10. Review ratio within 0-100
    if "review_ratio" in games:
        ratio = games["review_ratio"].dropna()
        ratio_bad = int(((ratio < config.RATIO_MIN) | (ratio > config.RATIO_MAX)).sum())
    else:
        ratio_bad = n_rows
    checks.append(
        _check(
            "review_ratio_in_range",
            ratio_bad == 0,
            f"{ratio_bad} review ratios outside 0-100",
            invalid=ratio_bad,
        )
    )

    # 11. CCU non-negative
    if "ccu" in games:
        ccu_bad = int((games["ccu"] < 0).sum())
    else:
        ccu_bad = n_rows
    checks.append(
        _check(
            "ccu_non_negative",
            ccu_bad == 0,
            f"{ccu_bad} rows with negative concurrent users",
            invalid=ccu_bad,
        )
    )

    # 12. Price non-negative and bounded
    if "price_usd" in games:
        price_bad = int(
            ((games["price_usd"] < 0) | (games["price_usd"] > config.PRICE_MAX_USD)).sum()
        )
    else:
        price_bad = n_rows
    checks.append(
        _check(
            "price_valid",
            price_bad == 0,
            f"{price_bad} prices out of [0, {config.PRICE_MAX_USD}] USD",
            invalid=price_bad,
        )
    )

    # 13. Initial price is valid and bounded
    if "initial_price_usd" in games:
        init_price_bad = int(
            (
                (games["initial_price_usd"] < 0)
                | (games["initial_price_usd"] > config.PRICE_MAX_USD)
            ).sum()
        )
    else:
        init_price_bad = n_rows
    checks.append(
        _check(
            "initial_price_valid",
            init_price_bad == 0,
            f"{init_price_bad} initial prices out of [0, {config.PRICE_MAX_USD}] USD",
            invalid=init_price_bad,
        )
    )

    # 14. Sale price should not exceed initial price when discount > 0
    if {"discount_pct", "price_usd", "initial_price_usd"}.issubset(games.columns):
        discounted = games["discount_pct"].fillna(0) > 0
        price_rel_bad = int((games.loc[discounted, "price_usd"] > games.loc[discounted, "initial_price_usd"]).sum())
    else:
        price_rel_bad = n_rows
    checks.append(
        _check(
            "discount_price_relationship",
            price_rel_bad == 0,
            f"{price_rel_bad} discounted rows where price_usd > initial_price_usd",
            invalid=price_rel_bad,
        )
    )

    # 15. Discount within 0-100
    if "discount_pct" in games:
        disc_bad = int(
            (
                (games["discount_pct"] < config.DISCOUNT_MIN)
                | (games["discount_pct"] > config.DISCOUNT_MAX)
            ).sum()
        )
    else:
        disc_bad = n_rows
    checks.append(
        _check(
            "discount_in_range",
            disc_bad == 0,
            f"{disc_bad} discounts outside 0-100%",
            invalid=disc_bad,
        )
    )

    # 16. Owners are non-negative
    if {"owners_min", "owners_max", "owners_mid"}.issubset(games.columns):
        owners_neg_bad = int(
            ((games["owners_min"] < 0) | (games["owners_max"] < 0) | (games["owners_mid"] < 0)).sum()
        )
    else:
        owners_neg_bad = n_rows
    checks.append(
        _check(
            "owners_non_negative",
            owners_neg_bad == 0,
            f"{owners_neg_bad} rows with negative owners values",
            invalid=owners_neg_bad,
        )
    )

    # 17. Logical relationship: owners_min <= owners_max
    if {"owners_min", "owners_max"}.issubset(games.columns):
        rel_bad = int((games["owners_min"] > games["owners_max"]).sum())
    else:
        rel_bad = n_rows
    checks.append(
        _check(
            "owners_min_le_max",
            rel_bad == 0,
            f"{rel_bad} rows where owners_min > owners_max",
            violations=rel_bad,
        )
    )

    # 18. owners_mid should lie within [owners_min, owners_max]
    if {"owners_min", "owners_mid", "owners_max"}.issubset(games.columns):
        mid_bad = int(((games["owners_mid"] < games["owners_min"]) | (games["owners_mid"] > games["owners_max"])).sum())
    else:
        mid_bad = n_rows
    checks.append(
        _check(
            "owners_mid_in_bounds",
            mid_bad == 0,
            f"{mid_bad} rows where owners_mid is outside owners range",
            invalid=mid_bad,
        )
    )

    passed = sum(1 for c in checks if c["status"] == "pass")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": n_rows,
        "genres": int(games["primary_genre"].nunique()) if "primary_genre" in games else 0,
        "checks_total": len(checks),
        "checks_passed": passed,
        "checks_failed": len(checks) - passed,
        "overall_status": "pass" if passed == len(checks) else "fail",
        "checks": checks,
    }

    if save:
        utils.ensure_directories()
        utils.save_json(report, config.QUALITY_REPORT_FILE)
    logger.info(
        "Data quality: %s/%s checks passed (%s)",
        passed,
        len(checks),
        report["overall_status"].upper(),
    )
    return report
