"""Integration-style tests for extract/usage/orchestration and final artifacts.

These tests stay offline by mocking the extract layer where needed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import requests

import etl
from src import config, extract, growth, quality, transform, usage


def _sample_records() -> list[dict]:
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


def test_extract_api_failure_raises_extraction_error(monkeypatch):
    def _boom(*args, **kwargs):
        raise requests.RequestException("simulated api failure")

    monkeypatch.setattr(extract.requests, "get", _boom)
    monkeypatch.setattr(extract.time, "sleep", lambda *_: None)
    monkeypatch.setattr(config, "MAX_RETRIES", 2)
    monkeypatch.setattr(config, "RETRY_BACKOFF", 0.0)

    with pytest.raises(extract.ExtractionError):
        extract._request_json({"request": config.BASE_REQUEST})


def test_usage_daily_model_outputs_expected_fields_and_ranges():
    games = transform.build_games(_sample_records())
    daily = usage.build_usage_daily(games, days=7, top_n=2)

    expected_cols = {
        "date",
        "appid",
        "name",
        "publisher",
        "primary_genre",
        "country",
        "players",
        "sessions",
        "usage_hours",
    }
    assert expected_cols.issubset(set(daily.columns))
    assert not daily.empty
    assert int(daily["players"].min()) >= 0
    assert int(daily["sessions"].min()) >= 0
    assert float(daily["usage_hours"].min()) >= 0
    assert set(daily["country"].unique()).issubset(set(config.COUNTRIES.keys()))
    assert daily["date"].nunique() == 7


def test_usage_daily_model_is_deterministic_for_same_input():
    games = transform.build_games(_sample_records())
    d1 = usage.build_usage_daily(games, days=5, top_n=2)
    d2 = usage.build_usage_daily(games, days=5, top_n=2)

    sort_cols = ["date", "appid", "country"]
    d1s = d1.sort_values(sort_cols).reset_index(drop=True)
    d2s = d2.sort_values(sort_cols).reset_index(drop=True)
    pd.testing.assert_frame_equal(d1s, d2s)


def test_etl_run_orchestrates_layers_in_order(monkeypatch):
    calls: list[str] = []
    records = _sample_records()
    games = transform.build_games(records)
    genre = transform.build_genre_summary(games)
    usage_df = pd.DataFrame({"x": [1, 2]})
    growth_df = pd.DataFrame({"x": [1, 2, 3]})
    quality_report = {"overall_status": "pass", "checks_passed": 1, "checks_total": 1}

    def _extract(_top_n):
        calls.append("extract")
        return records

    def _transform(_records):
        calls.append("transform")
        return games, genre

    def _usage(_games):
        calls.append("usage")
        return usage_df

    def _growth(_games):
        calls.append("growth")
        return growth_df

    def _quality(_games, expected_games):
        calls.append("quality")
        assert expected_games == len(records)
        return quality_report

    monkeypatch.setattr(etl.extract, "extract", _extract)
    monkeypatch.setattr(etl.transform, "transform", _transform)
    monkeypatch.setattr(etl.usage, "build_and_save", _usage)
    monkeypatch.setattr(etl.growth, "build_and_save", _growth)
    monkeypatch.setattr(etl.quality, "run_quality_checks", _quality)

    code = etl.run()
    assert code == 0
    assert calls == ["extract", "transform", "usage", "growth", "quality"]


def test_etl_run_returns_error_on_extract_failure(monkeypatch):
    def _fail(_top_n):
        raise extract.ExtractionError("boom")

    monkeypatch.setattr(etl.extract, "extract", _fail)
    assert etl.run() == 1


def test_pipeline_writes_and_validates_final_processed_files(tmp_path, monkeypatch):
    processed_dir = tmp_path / "processed"
    raw_dir = tmp_path / "raw"

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_DIR", raw_dir)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(config, "GAMES_FILE", processed_dir / "games.csv")
    monkeypatch.setattr(config, "GENRE_SUMMARY_FILE", processed_dir / "genre_summary.csv")
    monkeypatch.setattr(config, "USAGE_DAILY_FILE", processed_dir / "usage_daily.csv")
    monkeypatch.setattr(config, "MONTHLY_METRICS_FILE", processed_dir / "monthly_metrics.csv")
    monkeypatch.setattr(config, "QUALITY_REPORT_FILE", processed_dir / "data_quality_report.json")

    monkeypatch.setattr(etl.extract, "extract", lambda _top_n: _sample_records())

    code = etl.run()
    assert code == 0

    assert config.GAMES_FILE.exists()
    assert config.GENRE_SUMMARY_FILE.exists()
    assert config.USAGE_DAILY_FILE.exists()
    assert config.MONTHLY_METRICS_FILE.exists()
    assert config.QUALITY_REPORT_FILE.exists()

    games = pd.read_csv(config.GAMES_FILE)
    genre = pd.read_csv(config.GENRE_SUMMARY_FILE)
    usage_daily = pd.read_csv(config.USAGE_DAILY_FILE)
    monthly = pd.read_csv(config.MONTHLY_METRICS_FILE)
    report = json.loads(Path(config.QUALITY_REPORT_FILE).read_text(encoding="utf-8"))

    assert {"appid", "name", "review_ratio", "owners_mid", "is_free"}.issubset(games.columns)
    assert {"primary_genre", "games", "total_ccu"}.issubset(genre.columns)
    assert {"date", "appid", "country", "players", "sessions", "usage_hours"}.issubset(usage_daily.columns)
    assert {"month", "mau", "dau", "new_users", "sessions", "hours"}.issubset(monthly.columns)

    assert report["overall_status"] in {"pass", "fail"}
    assert isinstance(report.get("checks"), list)
    assert report.get("checks_total", 0) >= 1