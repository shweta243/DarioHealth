"""Central configuration for the Steam Games Insights product.

Everything a reviewer might tweak (how many games to enrich, endpoints,
plausible value ranges) lives here so the rest of the code stays
declarative and easy to read.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Processed output files
GAMES_FILE = PROCESSED_DIR / "games.csv"
GENRE_SUMMARY_FILE = PROCESSED_DIR / "genre_summary.csv"
USAGE_DAILY_FILE = PROCESSED_DIR / "usage_daily.csv"
MONTHLY_METRICS_FILE = PROCESSED_DIR / "monthly_metrics.csv"
QUALITY_REPORT_FILE = PROCESSED_DIR / "data_quality_report.json"

# --------------------------------------------------------------------------
# API configuration (SteamSpy - free, keyless, no signup required)
# Docs: https://steamspy.com/api.php
# --------------------------------------------------------------------------
STEAMSPY_URL = "https://steamspy.com/api.php"

# Base list request. "top100in2weeks" = the 100 most-played games in the last
# two weeks, returned in a single keyless call (popularity, reviews, CCU).
BASE_REQUEST = "top100in2weeks"

# The base list does not include genre/tags, so we enrich the top N games with
# per-app `appdetails` calls. Keep this modest so `python etl.py` stays quick
# and stays well within SteamSpy's polite rate limit.
TOP_N_ENRICH = 50

# SteamSpy asks for no more than ~1 request/second for appdetails calls.
ENRICH_DELAY_SECONDS = 1.1

TIMEZONE = "auto"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, multiplied by attempt number

# --------------------------------------------------------------------------
# Data-quality thresholds (plausible ranges)
# --------------------------------------------------------------------------
PRICE_MAX_USD = 1000.0     # sanity upper bound for a store price
RATIO_MIN, RATIO_MAX = 0.0, 100.0
DISCOUNT_MIN, DISCOUNT_MAX = 0.0, 100.0

# --------------------------------------------------------------------------
# Analytics constants
# --------------------------------------------------------------------------
# Minimum reviews for a "rating label" to be considered meaningful.
MIN_REVIEWS_FOR_LABEL = 500
# Review-ratio thresholds for the rating label buckets.
RATING_POSITIVE = 70.0
RATING_MIXED = 40.0

# --------------------------------------------------------------------------
# Modeled daily-usage layer
# --------------------------------------------------------------------------
# NOTE: SteamSpy's free API returns a point-in-time *snapshot* only - it has no
# per-day history and no per-country breakdown. To power the time-series and
# country views in the dashboard, the pipeline derives a DETERMINISTIC,
# clearly-labeled daily-usage fact table from the real snapshot metrics
# (concurrent users, playtime, publisher). Values are estimates seeded per
# appid so runs are reproducible. This is documented in the README.
USAGE_DAYS = 30          # length of the modeled daily window
USAGE_TOP_N = 30         # how many top games to model (chart readability)
DAU_FACTOR = 9.0         # daily-active ≈ concurrent-users × this factor
WEEKEND_UPLIFT = 1.25    # weekend player multiplier

# Approximate share of the Steam player base by country (sums to ~1.0).
# Used only to allocate the modeled daily players across countries.
COUNTRIES = {
    "United States": 0.21,
    "China": 0.18,
    "Russia": 0.09,
    "Germany": 0.07,
    "Brazil": 0.06,
    "United Kingdom": 0.05,
    "South Korea": 0.05,
    "Canada": 0.04,
    "France": 0.04,
    "Japan": 0.03,
    "Australia": 0.03,
    "Other": 0.15,
}

# --------------------------------------------------------------------------
# Modeled monthly growth metrics (MAU / DAU / new users)
# --------------------------------------------------------------------------
# Same caveat as the daily layer: SteamSpy has no historical monthly series,
# so the monthly growth table is a DETERMINISTIC modeled series (seeded) built
# from the snapshot totals with a growth trend + seasonality. It powers the
# "Usage Worldwide" executive page (MAU, DAU, new users, YoY deltas).
GROWTH_START = "2024-01"     # first modeled month
GROWTH_END = "2026-06"       # last modeled month ("data available until")
MAU_BASE_MULTIPLIER = 2.0    # base monthly active users ≈ total CCU × this
MONTHLY_GROWTH = 0.015       # ~1.5% compound month-over-month growth
