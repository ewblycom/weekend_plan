"""«Поесть рядом»: для площадок ближайших событий берём рестораны рядом через Apify (Google Maps scraper).

Токен — секрет репозитория APIFY_TOKEN. Без него шаг пропускается, приложение просто не показывает блок.
Бережём бесплатный бюджет Apify ($5/мес ≈ 1000+ мест): на каждую площадку 5 мест, обновляем раз в 30 дней,
не больше MAX_VENUES_PER_RUN новых площадок за запуск. Результат: docs/data/food.json {ключ_площадки: [места]}.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

import requests

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "data" / "food.json"
CACHE = ROOT / "data" / "cache" / "food.json"
ACTOR = "compass~crawler-google-places"
API = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
PER_VENUE = 5
REFRESH_DAYS = 30
MAX_VENUES_PER_RUN = 20
BAD_VENUE = re.compile(r"^(praha|online|různá místa|various)$", re.I)


def venue_key(venue: str | None) -> str | None:
    """Ключ площадки: первая часть названия до запятой/тире, в нижнем регистре. Тот же алгоритм в app.js (foodKey)."""
    v = re.split(r"[,—]", venue or "")[0].strip().lower()
    return v[:60] if len(v) >= 3 and not BAD_VENUE.match(v) else None


def pick_venues(events: list[dict], today: date, horizon_days: int = 14) -> list[tuple[str, str]]:
    """Площадки ближайших событий в порядке важности (события уже отсортированы по score). → [(ключ, название для поиска)]"""
    until = (today + timedelta(days=horizon_days)).isoformat()
    seen: dict[str, str] = {}
    for e in events:
        if e.get("city") and e["city"] != "Прага":
            continue
        if e.get("start") and e["start"] > until:
            continue
        k = venue_key(e.get("venue"))
        if k and k not in seen:
            seen[k] = re.split(r"[,—]", e["venue"])[0].strip()
    return list(seen.items())


def parse_item(it: dict) -> dict | None:
    """Одно место из ответа Apify → компактная запись для приложения."""
    name = it.get("title")
    if not name or it.get("permanentlyClosed") or it.get("temporarilyClosed"):
        return None
    loc = it.get("location") or {}
    return {k: v for k, v in {
        "name": name, "rating": it.get("totalScore"), "reviews": it.get("reviewsCount"), "type": it.get("categoryName"),
        "price": it.get("price"), "address": it.get("address"), "url": it.get("url"),
        "lat": loc.get("lat"), "lng": loc.get("lng"),
    }.items() if v not in (None, "")}


def fetch_nearby(token: str, venue_name: str) -> list[dict]:
    r = requests.post(API, params={"token": token}, timeout=240, json={
        "searchStringsArray": [f"restaurace poblíž {venue_name}, Praha"],
        "maxCrawledPlacesPerSearch": PER_VENUE, "language": "cs", "skipClosedPlaces": True,
        "scrapeContacts": False, "scrapeReviewsPersonalData": False, "maxReviews": 0, "maxImages": 0,
    })
    r.raise_for_status()
    out = [p for p in (parse_item(i) for i in r.json()) if p]
    out.sort(key=lambda p: -(p.get("rating") or 0) * min(1, (p.get("reviews") or 0) / 50))   # оценка с поправкой на число отзывов
    return out[:PER_VENUE]


def collect(events: list[dict], today: date | None = None, token: str | None = None) -> int:
    token = token or os.environ.get("APIFY_TOKEN")
    if not token:
        log.info("food: APIFY_TOKEN не задан — пропускаю")
        return 0
    today = today or date.today()
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    stale = (today - timedelta(days=REFRESH_DAYS)).isoformat()
    todo = [(k, n) for k, n in pick_venues(events, today) if k not in cache or cache[k]["fetched"] < stale][:MAX_VENUES_PER_RUN]
    done = 0
    for k, name in todo:
        try:
            cache[k] = {"fetched": today.isoformat(), "places": fetch_nearby(token, name)}
            done += 1
        except Exception as e:  # noqa: BLE001 — одна площадка не должна ронять сбор
            log.warning("food: %s — %s", name, str(e).replace(token, "***"))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT.write_text(json.dumps({k: v["places"] for k, v in cache.items() if v["places"]}, ensure_ascii=False), encoding="utf-8")
    log.info("food: обновлено площадок %d, всего в кэше %d", done, len(cache))
    return done
