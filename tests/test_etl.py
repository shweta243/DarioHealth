"""Unit tests for the transform and quality layers.

These tests use synthetic in-memory records so they run fast and never
touch the network - a reviewer can run `pytest` offline.
"""
from __future__ import annotations

import pandas as pd

from src import quality, transform


def _sample_records() -> list[dict]:
    """Three synthetic games covering free/paid, genres and reviews."""
    return [
        {
            "appid": 730,
            "name": "Test Shooter",
            "developer": "Valve",
            "publisher": "Valve",
            "positive": 9000,
            "negative": 1000,
            "ccu": 500000,
            "owners": "100,000,000 .. 200,000,000",
            "price": "0",
            "initialprice": "0",
            "discount": "0",
            "average_forever": 6000,
            "median_forever": 3000,
            "genre": "Action, Free To Play",
            "tags": {"FPS": 100, "Shooter": 80, "Multiplayer": 60},
            "languages": "English",
        },
        {
            "appid": 570,
            "name": "Test MOBA",
            "developer": "Valve",
            "publisher": "Valve",
            "positive": 700000,
            "negative": 300000,
            "ccu": 400000,
            "owners": "50,000,000 .. 100,000,000",
            "price": "0",
            "initialprice": "0",
            "discount": "0",
            "average_forever": 12000,
            "median_forever": 6000,
            "genre": "Strategy",
            "tags": {"MOBA": 200, "Strategy": 150},
            "languages": "English",
        },
        {
            "appid": 1091500,
            "name": "Test RPG",
            "developer": "CD Projekt",
            "publisher": "CD Projekt",
            "positive": 400000,
            "negative": 100000,
            "ccu": 20000,
            "owners": "10,000,000 .. 20,000,000",
            "price": "5999",
            "initialprice": "5999",
            "discount": "0",
            "average_forever": 3000,
            "median_forever": 1500,
            "genre": "RPG",
            "tags": {"RPG": 300, "Open World": 250},
            "languages": "English",
        },
    ]


def test_build_games_shape_and_metrics():
    df = transform.build_games(_sample_records())
    assert len(df) == 3
    for col in ["review_ratio", "owners_mid", "is_free", "rating_label", "top_tags"]:
        assert col in df.columns
    # Free vs paid
    assert df.set_index("appid").loc[730, "is_free"]
    assert not df.set_index("appid").loc[1091500, "is_free"]


def test_owners_parsing():
    df = transform.build_games(_sample_records())
    row = df.set_index("appid").loc[730]
    assert row["owners_min"] == 100_000_000
    assert row["owners_max"] == 200_000_000
    assert row["owners_mid"] == 150_000_000


def test_review_ratio_bounds():
    df = transform.build_games(_sample_records())
    assert df["review_ratio"].between(0, 100).all()
    # 9000 / 10000 = 90%
    assert df.set_index("appid").loc[730, "review_ratio"] == 90.0


def test_price_conversion_cents_to_usd():
    df = transform.build_games(_sample_records())
    assert df.set_index("appid").loc[1091500, "price_usd"] == 59.99


def test_genre_summary_one_row_per_genre():
    df = transform.build_games(_sample_records())
    summary = transform.build_genre_summary(df)
    assert summary["primary_genre"].nunique() == len(summary)
    assert {"games", "avg_review_ratio", "total_ccu"} <= set(summary.columns)


def test_quality_passes_on_clean_data():
    df = transform.build_games(_sample_records())
    report = quality.run_quality_checks(df, expected_games=3, save=False)
    assert report["overall_status"] == "pass"
    assert report["checks_failed"] == 0


def test_quality_flags_duplicates():
    df = transform.build_games(_sample_records())
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    report = quality.run_quality_checks(dup, expected_games=3, save=False)
    statuses = {c["check"]: c["status"] for c in report["checks"]}
    assert statuses["no_duplicate_appids"] == "fail"


def test_quality_flags_bad_price():
    df = transform.build_games(_sample_records())
    df.loc[0, "price_usd"] = 99999.0
    report = quality.run_quality_checks(df, expected_games=3, save=False)
    statuses = {c["check"]: c["status"] for c in report["checks"]}
    assert statuses["price_valid"] == "fail"
    assert report["overall_status"] == "fail"


def test_quality_flags_missing_schema_column():
    df = transform.build_games(_sample_records()).drop(columns=["review_ratio"])
    report = quality.run_quality_checks(df, expected_games=3, save=False)
    statuses = {c["check"]: c["status"] for c in report["checks"]}
    assert statuses["schema_columns_present"] == "fail"
    assert report["overall_status"] == "fail"


def test_quality_flags_null_key_fields():
    df = transform.build_games(_sample_records())
    df.loc[0, "name"] = ""
    report = quality.run_quality_checks(df, expected_games=3, save=False)
    statuses = {c["check"]: c["status"] for c in report["checks"]}
    assert statuses["key_fields_not_null"] == "fail"
    assert report["overall_status"] == "fail"
