"""Extraction layer.

Talks to the free, keyless SteamSpy API:

1. Pull the base "top 100 played in the last two weeks" list (popularity,
   reviews, concurrent users, owners, price) in a single call.
2. Enrich the top N games with per-app ``appdetails`` calls to add genre,
   tags and languages (throttled to respect SteamSpy's rate limit).

Raw responses are persisted locally so the pipeline is fully reproducible
without hitting the network again.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from . import config, utils

logger = utils.get_logger()


class ExtractionError(RuntimeError):
    """Raised when required data cannot be retrieved."""


def _request_json(params: dict[str, Any]) -> dict[str, Any]:
    """GET the SteamSpy API with retries and return the parsed JSON body."""
    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = requests.get(
                config.STEAMSPY_URL, params=params, timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Request failed (attempt %s/%s): %s -> retrying in %.1fs",
                attempt,
                config.MAX_RETRIES,
                exc,
                wait,
            )
            if attempt < config.MAX_RETRIES:
                time.sleep(wait)
    raise ExtractionError(f"Failed SteamSpy request {params}: {last_error}")


def fetch_base_list() -> dict[str, Any]:
    """Fetch the base top-games list keyed by appid."""
    payload = _request_json({"request": config.BASE_REQUEST})
    if not isinstance(payload, dict) or not payload:
        raise ExtractionError("SteamSpy returned an empty base list.")
    utils.save_json(payload, config.RAW_DIR / f"{config.BASE_REQUEST}.json")
    logger.info("Fetched base list: %s games", len(payload))
    return payload


def fetch_appdetails(appid: int) -> dict[str, Any]:
    """Fetch per-app details (adds genre, tags, languages)."""
    return _request_json({"request": "appdetails", "appid": appid})


def extract(top_n: int | None = None) -> list[dict[str, Any]]:
    """Full extract: base list + enrichment for the top N games.

    Individual enrichment failures are logged and skipped; the base fields
    are always retained so one bad response never loses a game.
    """
    utils.ensure_directories()
    top_n = top_n or config.TOP_N_ENRICH

    base = fetch_base_list()
    games = list(base.values())
    to_enrich = games[:top_n]
    logger.info("Enriching top %s games with genre/tags...", len(to_enrich))

    enriched: list[dict[str, Any]] = []
    for i, game in enumerate(to_enrich, start=1):
        appid = game.get("appid")
        record = dict(game)
        try:
            details = fetch_appdetails(appid)
            record["genre"] = details.get("genre", "")
            record["tags"] = details.get("tags", {})
            record["languages"] = details.get("languages", "")
        except ExtractionError as exc:
            logger.warning("Enrichment failed for appid %s: %s", appid, exc)
            record.setdefault("genre", "")
            record.setdefault("tags", {})
            record.setdefault("languages", "")
        enriched.append(record)
        if i % 10 == 0:
            logger.info("  ...enriched %s/%s", i, len(to_enrich))
        # Polite throttle between appdetails calls.
        if i < len(to_enrich):
            time.sleep(config.ENRICH_DELAY_SECONDS)

    payload = {
        "meta": {
            "base_request": config.BASE_REQUEST,
            "games_enriched": len(enriched),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        },
        "games": enriched,
    }
    utils.save_json(payload, config.RAW_DIR / "games_enriched.json")
    logger.info("Saved enriched raw data for %s games", len(enriched))
    return enriched
