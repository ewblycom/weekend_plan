"""«Поесть рядом»: для площадок ближайших событий берём рестораны рядом через Apify (Google Maps scraper).

Токен — секрет репозитория APIFY_TOKEN. Без него шаг пропускается, приложение просто не показывает блок.
Для каждой площадки: геокод (1 место) + рестораны в радиусе ~10 минут пешком, оставляем лучшие по оценке.
Обновляем раз в 30 дней, не больше MAX_VENUES_PER_RUN площадок за запуск (бюджет Apify). Результат: docs/data/food.json {ключ_площадки: [места]}.
"""
from __future__ import annotations

import json
import logging
import math
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
MAX_WALK_MIN = 10          # «до 10 минут пешком»
WALK_M_PER_MIN = 80        # ~4,8 км/ч
DETOUR = 1.3               # по улицам дальше, чем по прямой
RADIUS_KM = round(MAX_WALK_MIN * WALK_M_PER_MIN / DETOUR / 1000 + 0.05, 2)   # ≈0,67 км по прямой
SEARCH_LIMIT = 20          # берём с запасом, потом фильтруем по расстоянию и качеству
KEEP = 6
MIN_RATING, MIN_REVIEWS = 4.0, 20
PRAGUE = (49.9, 50.2, 14.2, 14.75)   # lat_min, lat_max, lng_min, lng_max — защита от геокода «не в ту Прагу»
REFRESH_DAYS = 30
MAX_VENUES_PER_RUN = 15
CACHE_VERSION = 2
# Только рестораны: тип из Google Maps должен быть «…restaurace», бистро или хоспода/пивница с кухней.
FOOD_TYPE = re.compile(r"restaura|bistro|hospoda|pivnice|gastropub|trattoria|pizzerie|steak|taverna", re.I)
# Фастфуд и всё, что не про сесть поесть.
FAST_TYPE = re.compile(r"rychl|fast.?food|občerstven|kebab|bufet|food ?court|kavárn|bar$|čajovn|hotel|centrum|park", re.I)
FAST_NAME = re.compile(r"mcdonald|\bkfc\b|burger king|subway|starbucks|costa coffee|coffee fellows|bageterie|paul\b|wok to walk|"
                       r"bistro (makro|tesco)|ikea|pizza hut|domino|five guys|popeyes|t\.g\.i|vapiano|ugo\b|panda express", re.I)
# Корнеры в торговых центрах: по адресу/«находится в».
MALL = re.compile(r"palladium|quadrio|nový smíchov|novy smichov|arkády|arkady|westfield|chodov|černý most|cerny most|harfa|atrium flora|"
                  r"fénix|fenix|letňany|letnany|pop airport|novodvorská plaza|galerie|nákupní|obchodní centrum|shopping|outlet|metropole zličín|"
                  r"europark|central kladno|oc |o\.c\.|tesco|albert|globus|kaufland|lidl|billa|penny", re.I)
PRICE_CZK = re.compile(r"(kč|czk)", re.I)
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


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def walk_min(dist_m: float) -> int:
    return max(1, math.ceil(dist_m * DETOUR / WALK_M_PER_MIN))


def in_prague(lat: float, lng: float) -> bool:
    return PRAGUE[0] <= lat <= PRAGUE[1] and PRAGUE[2] <= lng <= PRAGUE[3]


def parse_item(it: dict, origin: tuple[float, float] | None = None) -> dict | None:
    """Одно место из ответа Apify → компактная запись. С origin считает расстояние и время пешком; дальше 10 минут → None."""
    name = it.get("title")
    if not name or it.get("permanentlyClosed") or it.get("temporarilyClosed"):
        return None
    loc = it.get("location") or {}
    lat, lng = loc.get("lat"), loc.get("lng")
    rec = {k: v for k, v in {
        "name": name, "rating": it.get("totalScore"), "reviews": it.get("reviewsCount"), "type": it.get("categoryName"),
        "price": czk_price(it.get("price")), "address": it.get("address"), "in": it.get("locatedIn"), "url": it.get("url"), "lat": lat, "lng": lng,
    }.items() if v not in (None, "")}
    if origin:
        if lat is None or lng is None:
            return None
        d = haversine_m(origin, (lat, lng))
        rec["m"] = round(d)
        rec["min"] = walk_min(d)
        if rec["min"] > MAX_WALK_MIN:
            return None
    return rec


def czk_price(v) -> str | None:
    """Цена только в кронах: «200–400 Kč». Чужая валюта (HNL, €, $) → не показываем."""
    if not isinstance(v, str) or not PRICE_CZK.search(v):
        return None
    return re.sub(r"\s*(kč|czk)\s*", " Kč", v.replace("\xa0", " "), flags=re.I).strip()


def is_restaurant(p: dict) -> bool:
    """Ресторан, не фастфуд и не корнер в ТЦ."""
    t = p.get("type") or ""
    if not FOOD_TYPE.search(t) or FAST_TYPE.search(t) or FAST_NAME.search(p.get("name") or ""):
        return False
    return not MALL.search(" ".join(str(p.get(k) or "") for k in ("in", "address", "name")))


def good(p: dict) -> bool:
    return is_restaurant(p) and (p.get("rating") or 0) >= MIN_RATING and (p.get("reviews") or 0) >= MIN_REVIEWS


def rank(p: dict) -> float:
    """Выше — лучше: оценка с поправкой на число отзывов, небольшой бонус за близость."""
    return (p.get("rating") or 0) * min(1, (p.get("reviews") or 0) / 100) - (p.get("min") or 0) * 0.03


def _run(token: str, payload: dict) -> list[dict]:
    r = requests.post(API, params={"token": token}, timeout=240, json={
        "language": "cs", "skipClosedPlaces": True, "scrapeContacts": False, "scrapeReviewsPersonalData": False,
        "maxReviews": 0, "maxImages": 0, **payload,
    })
    r.raise_for_status()
    return r.json()


def geocode(token: str, venue_name: str) -> tuple[float, float] | None:
    """Координаты площадки: ищем её саму в Google Maps (1 место). Не в Праге — считаем промахом."""
    for it in _run(token, {"searchStringsArray": [f"{venue_name}, Praha"], "maxCrawledPlacesPerSearch": 1}):
        loc = it.get("location") or {}
        if loc.get("lat") is not None and in_prague(loc["lat"], loc["lng"]):
            return (loc["lat"], loc["lng"])
    return None


def fetch_nearby(token: str, origin: tuple[float, float]) -> list[dict]:
    """Рестораны в радиусе ~10 минут пешком от точки. Радиус просим у Apify, а расстояние всё равно проверяем сами."""
    items = _run(token, {
        "searchStringsArray": ["restaurace"], "maxCrawledPlacesPerSearch": SEARCH_LIMIT,
        "customGeolocation": {"type": "Point", "coordinates": [origin[1], origin[0]], "radiusKm": RADIUS_KM},
    })
    places = [p for p in (parse_item(i, origin) for i in items) if p and good(p)]
    places.sort(key=rank, reverse=True)
    return places[:KEEP]


def clean(p: dict) -> dict:
    q = {k: v for k, v in p.items() if k != "in"}
    q["price"] = czk_price(p.get("price"))
    return {k: v for k, v in q.items() if v not in (None, "")}


def write_out(cache: dict) -> None:
    """Публичный файл: фильтр применяется и к старому кэшу — правка правил не требует новых запросов в Apify."""
    out = {}
    for k, v in cache.items():
        places = [clean(p) for p in v.get("places", []) if good(p)][:KEEP]
        if places:
            out[k] = places
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


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
    todo = [(k, n) for k, n in pick_venues(events, today)
            if k not in cache or cache[k].get("v") != CACHE_VERSION or cache[k]["fetched"] < stale][:MAX_VENUES_PER_RUN]
    done = 0
    for k, name in todo:
        try:
            old = cache.get(k) or {}
            origin = (old["lat"], old["lng"]) if old.get("lat") is not None else geocode(token, name)
            if not origin:
                cache[k] = {"v": CACHE_VERSION, "fetched": today.isoformat(), "places": []}   # не нашли площадку — повтор через 30 дней
                log.info("food: %s — не нашёл координаты", name)
                continue
            cache[k] = {"v": CACHE_VERSION, "fetched": today.isoformat(), "lat": origin[0], "lng": origin[1], "places": fetch_nearby(token, origin)}
            done += 1
        except Exception as e:  # noqa: BLE001 — одна площадка не должна ронять сбор
            log.warning("food: %s — %s", name, str(e).replace(token, "***"))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    write_out(cache)
    log.info("food: обновлено площадок %d, с едой %d из %d в кэше", done, sum(1 for v in cache.values() if v["places"]), len(cache))
    return done
