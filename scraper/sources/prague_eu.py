"""prague.eu (Prague City Tourism): списки событий по категориям.

На странице списка у каждой карточки есть всё нужное: категория, название (h2),
даты/время и площадка. Разбор не завязан на CSS-классы (они могут смениться):
ищем ссылки вида /cs/akce/<slug>/ и поднимаемся к ближайшему блоку с одним <h2>.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from datetime import date, timedelta

from ..dates import NUMERIC_RANGE, overlaps, parse_range
from ..extract import external_links, facebook_event, meta, soup_of
from .. import profile
from ..models import Event

log = logging.getLogger(__name__)

BASE = "https://prague.eu"
# slug категории на сайте → наша категория
CATEGORIES = {
    "trhy": "market",
    "trhy-gourmet": "food",
    "vystavy-expozice": "exhibition",
    "koncerty": "concert",
    "festivaly-oslavy": "festival",
    "predstaveni": "show",
    "akce": "other",
    "sport": "sport",
    "trendy-a-tipy": "other",
}
# подкатегории театра на prague.eu (строка над заголовком карточки) → наша категория
THEATER_LABELS = {
    "činohra": "theater", "opera": "theater", "balet": "theater",
    "muzikály a hudební divadlo": "theater", "alternativní divadlo": "theater",
    "současný tanec": "theater", "nový cirkus a fyzické divadlo": "theater",
    "černé a stínové divadlo": "theater", "loutkové divadlo": "kids",
}
DETAIL_HREF = re.compile(r"/cs/akce/[^/?#]+/?$")
NOISE = {"sdílet", "oblíbené", "nahoru", "filtry", "zobrazit 20 dalších"}


CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prague_eu.json"
REFRESH_DAYS = 7
PAUSE = 10   # секунд между страницами событий


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(data: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def listing_url(slug: str) -> str:
    return f"{BASE}/cs/akce-kategorie/{slug}/"


def _card_for(anchor):
    """Поднимаемся от ссылки, пока в блоке есть ровно один заголовок карточки."""
    node, best = anchor, None
    for _ in range(8):
        node = node.parent
        if node is None or node.name in ("body", "html"):
            break
        headings = node.find_all(["h2", "h3"])
        if len(headings) == 1:
            best = node
        elif len(headings) > 1:
            break
    return best


def parse_listing(html: str, category: str) -> list[Event]:
    soup = soup_of(html)
    events, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        if not DETAIL_HREF.search(href) or "akce-kategorie" in href or href in seen:
            continue
        card = _card_for(a)
        if card is None:
            continue
        seen.add(href)
        title = card.find(["h2", "h3"]).get_text(" ", strip=True)
        lines = [l.strip() for l in card.get_text("\n").split("\n") if l.strip()]
        date_line = next((l for l in lines if NUMERIC_RANGE.search(l)), None)
        start, end, time = parse_range(date_line or "")
        # площадка — первая «содержательная» строка после даты
        venue = None
        if date_line:
            after = lines[lines.index(date_line) + 1:]
            venue = next((l for l in after if l != title and l.lower() not in NOISE), None)
        img = card.find("img")
        label = None
        if title in lines and lines.index(title) > 0:
            label = lines[lines.index(title) - 1].lower()
        cat = THEATER_LABELS.get(label, category) if category == "show" else category
        events.append(Event(
            source="prague.eu",
            url=href,
            title=title,
            start=start,
            end=end,
            time=time,
            venue=venue,
            category=cat,
            image=img.get("src") if img else None,
        ))
    return events


SLOT = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4}),\s*(\d{1,2}:\d{2})")


def parse_detail(html: str) -> dict:
    """Страница события: все сеансы из блока «datum a čas», ссылка на билеты и сайт площадки."""
    # Не используем page_basics: на prague.eu даты и кнопка «vstupenky» лежат внутри <header>,
    # который общий разбор вырезает как шапку сайта.
    soup = soup_of(html)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    low = text.lower()
    i = low.find("datum a čas")
    block = text[i:i + 3000] if i >= 0 else ""
    slots, seen = [], set()
    for d, m, y, t in SLOT.findall(block):
        try:
            key = (date(int(y), int(m), int(d)).isoformat(), t if len(t) == 5 else "0" + t)
        except ValueError:
            continue
        if key not in seen:
            seen.add(key)
            slots.append({"date": key[0], "time": key[1]})
    site, booking = external_links(soup)
    site = site or facebook_event(soup)
    return {"slots": slots, "booking": booking, "link": site,
            "description": meta(soup, "og:description") or meta(soup, "description")}


def collect(fetcher, max_per_category: int = 40, today: date | None = None,
            horizon_days: int = 21, max_details: int = 60) -> list[Event]:
    today = today or date.today()
    out: list[Event] = []
    interests = profile.load()
    for slug, cat in CATEGORIES.items():
        html = fetcher.get(listing_url(slug))
        if not html:
            continue
        # театр лежит внутри «predstaveni», поэтому квоту смотрим по любой из его категорий
        aff = max(interests.get(c, 0.0) for c in ({cat, "theater"} if cat == "show" else {cat}))
        items = parse_listing(html, cat)[:profile.quota(max_per_category, aff) if interests else max_per_category]
        log.info("prague.eu/%s: %d событий", slug, len(items))
        out.extend(items)
    # Страницы событий открываем только для ближайших дат: оттуда берём сеансы и прямые ссылки.
    # Щадящий режим: каждую страницу открываем один раз и запоминаем (кэш в репозитории),
    # повторно — не чаще раза в REFRESH_DAYS; за запуск не больше max_details страниц с паузой PAUSE.
    cache = load_cache()
    near = [e for e in out if overlaps(e.start, e.end, today, today + timedelta(days=horizon_days))]
    fresh = lambda u: u in cache and cache[u]["fetched"] >= (today - timedelta(days=REFRESH_DAYS)).isoformat()
    todo, seen = [], set()
    for ev in sorted(near, key=lambda e: (e.url in cache, e.start or date.max)):   # сначала ни разу не открытые
        if ev.url not in seen and not fresh(ev.url):
            seen.add(ev.url); todo.append(ev.url)
    for i, url in enumerate(todo[:max_details]):
        if i:
            time.sleep(PAUSE)
        page = fetcher.get(url)
        if page:
            cache[url] = {"fetched": today.isoformat(), **parse_detail(page)}
    log.info("prague.eu: открыто страниц %d, из кэша %d", min(len(todo), max_details), len({e.url for e in near}) - len(todo))
    for ev in near:
        d = cache.get(ev.url)
        if not d:
            continue
        ev.slots = [x for x in d["slots"] if x["date"] >= today.isoformat()]   # прошедшие сеансы не нужны
        ev.booking, ev.link = d["booking"], d["link"]
        ev.description = ev.description or d["description"]
        if ev.slots and not ev.time:
            times = {x["time"] for x in ev.slots}
            ev.time = times.pop() if len(times) == 1 else None
    keep = {e.url for e in out}
    save_cache({u: v for u, v in cache.items() if u in keep})   # прошедшие события из кэша убираем
    # одно событие встречается в нескольких категориях — переносим найденное на дубли
    by_url = {e.url: e for e in near if e.slots or e.booking or e.link}
    for e in out:
        src = by_url.get(e.url)
        if src and src is not e:
            e.slots, e.booking, e.link = src.slots, src.booking, src.link
    return out
