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
