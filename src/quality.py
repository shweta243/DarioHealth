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

from . import config, utils

logger = utils.get_logger()


def _check(name: str, passed: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "check": name,
        "status": "pass" if passed else "fail",
        "detail": detail,
        **extra,
    }


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

    # 2. Expected coverage
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

    # 3. No duplicate appids
    dup = int(games.duplicated(subset=["appid"]).sum())
    checks.append(
        _check("no_duplicate_appids", dup == 0, f"{dup} duplicate appids", duplicates=dup)
    )

    # 4. No missing names
    missing_names = int(games["name"].isna().sum() + (games["name"] == "").sum())
    checks.append(
        _check(
            "names_present",
            missing_names == 0,
            f"{missing_names} games with missing name",
            missing=missing_names,
        )
    )

    # 5. Non-negative review counts
    neg_reviews = int(((games["positive"] < 0) | (games["negative"] < 0)).sum())
    checks.append(
        _check(
            "reviews_non_negative",
            neg_reviews == 0,
            f"{neg_reviews} rows with negative review counts",
            invalid=neg_reviews,
        )
    )

    # 6. Review ratio within 0-100
    ratio = games["review_ratio"].dropna()
    ratio_bad = int(((ratio < config.RATIO_MIN) | (ratio > config.RATIO_MAX)).sum())
    checks.append(
        _check(
            "review_ratio_in_range",
            ratio_bad == 0,
            f"{ratio_bad} review ratios outside 0-100",
            invalid=ratio_bad,
        )
    )

    # 7. Price non-negative and bounded
    price_bad = int(
        ((games["price_usd"] < 0) | (games["price_usd"] > config.PRICE_MAX_USD)).sum()
    )
    checks.append(
        _check(
            "price_valid",
            price_bad == 0,
            f"{price_bad} prices out of [0, {config.PRICE_MAX_USD}] USD",
            invalid=price_bad,
        )
    )

    # 8. Discount within 0-100
    disc_bad = int(
        (
            (games["discount_pct"] < config.DISCOUNT_MIN)
            | (games["discount_pct"] > config.DISCOUNT_MAX)
        ).sum()
    )
    checks.append(
        _check(
            "discount_in_range",
            disc_bad == 0,
            f"{disc_bad} discounts outside 0-100%",
            invalid=disc_bad,
        )
    )

    # 9. Logical relationship: owners_min <= owners_max
    rel_bad = int((games["owners_min"] > games["owners_max"]).sum())
    checks.append(
        _check(
            "owners_min_le_max",
            rel_bad == 0,
            f"{rel_bad} rows where owners_min > owners_max",
            violations=rel_bad,
        )
    )

    passed = sum(1 for c in checks if c["status"] == "pass")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": n_rows,
        "genres": int(games["primary_genre"].nunique()),
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
