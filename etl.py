"""Steam Games Insights - ETL entry point.

Runs the full pipeline end to end:

    Extract  ->  Transform  ->  Data Quality

Usage:
    python etl.py

Outputs (written to data/):
    data/raw/top100in2weeks.json      raw base list from SteamSpy
    data/raw/games_enriched.json      base list + genre/tags enrichment
    data/processed/games.csv          tidy per-game table
    data/processed/genre_summary.csv  per-genre aggregates
    data/processed/usage_daily.csv    modeled daily usage (by date & country)
    data/processed/monthly_metrics.csv modeled monthly growth (MAU/DAU/new users)
    data/processed/data_quality_report.json
"""
from __future__ import annotations

import sys

from src import config, extract, quality, transform, usage, growth, utils

logger = utils.get_logger()


def run() -> int:
    """Execute the pipeline. Returns a process exit code (0 == success)."""
    logger.info("=== Steam Games Insights ETL starting ===")
    try:
        records = extract.extract(config.TOP_N_ENRICH)
    except extract.ExtractionError as exc:
        logger.error("Extraction failed: %s", exc)
        return 1

    games, genre_summary = transform.transform(records)
    usage_daily = usage.build_and_save(games)
    monthly = growth.build_and_save(games)
    report = quality.run_quality_checks(games, expected_games=len(records))

    logger.info(
        "Done. %s games, %s genres, %s usage rows, %s months. Data quality: %s (%s/%s checks).",
        games.shape[0],
        genre_summary.shape[0],
        usage_daily.shape[0],
        monthly.shape[0],
        report["overall_status"].upper(),
        report["checks_passed"],
        report["checks_total"],
    )
    logger.info("Next step: streamlit run app.py")
    return 0


if __name__ == "__main__":
    sys.exit(run())
