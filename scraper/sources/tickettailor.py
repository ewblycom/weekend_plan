"""Ticket Tailor: русскоязычные концерты и стендап (организатор Spotlight Production).

Список организаторов можно расширять в config.TICKETTAILOR_ORGANIZERS.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from .. import config
from ..dates import parse_iso, parse_range
from ..extract import jsonld_venue, page_basics, soup_of
from ..pricing import detect_price
from ..models import Event, detect_lang

log = logging.getLogger(__name__)

BASE = "https://www.tickettailor.com"


def listing_url(organizer: str) -> str:
    return f"{BASE}/events/{organizer}"


def parse_listing_links(html: str, organizer: str) -> list[str]:
    rx = re.compile(rf"/events/{re.escape(organizer)}/\d+")
    links = []
    for a in soup_of(html).find_all("a", href=True):
        m = rx.search(a["href"])
        if m:
            full = urljoin(BASE, m.group(0))
            if full not in links:
                links.append(full)
    return links


# "Wed 21 Oct 2026 20:00 - 22:30 Futurum Music Bar, 150 00"
VENUE_AFTER_TIME = re.compile(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s+(.+)")


BUY_PREFIX = re.compile(r"^\s*Купить билеты\s*[–—-]\s*", re.I)
TITLE_VENUE_TAIL = re.compile(r"\s+[–—-]\s+[^–—-]+$")
IN_CITY = re.compile(r"\bв\s+([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)")
# Почтовые индексы как запасной признак города, когда в заголовке города нет
POSTAL = [
    (re.compile(r"\b1[0-9]0 \d{2}\b"), "Прага"),
    (re.compile(r"\b1\d{3}\b(?!\s*\d)"), "Вена"),
    (re.compile(r"\b8[01]\d{3}\b"), "Мюнхен"),
    (re.compile(r"\b1[0-4]\d{3}\b"), "Берлин"),
]


def clean_title(title: str) -> str:
    """«Купить билеты – Название – Площадка» → «Название» (иначе одно событие попадает в список дважды)."""
    if BUY_PREFIX.search(title):
        title = TITLE_VENUE_TAIL.sub("", BUY_PREFIX.sub("", title))
    return title.strip()


def detect_city(title: str, venue: str | None) -> tuple[str | None, bool]:
    """(город, разрешён_ли). Сначала «в Вене» из заголовка, потом название города/индекс в адресе."""
    m = IN_CITY.search(title)
    if m:
        word = m.group(1).lower()
        city = config.CITY_FORMS.get(word)
        return (city, True) if city else (m.group(1), False)
    blob = (venue or "").lower()
    for form, city in config.CITY_FORMS.items():
        if re.search(rf"\b{re.escape(form)}\b", blob):
            return city, True
    for rx, city in POSTAL:
        if rx.search(venue or ""):
            return city, True
    return None, False


def parse_detail(html: str, url: str) -> Event:
    b = page_basics(html)
    ld = b["jsonld"] or {}
    start = parse_iso(ld.get("startDate"))
    end = parse_iso(ld.get("endDate")) or start
    time = None
    if not start:
        start, end, time = parse_range(b["text"])
    venue = jsonld_venue(ld) if ld else None
    if not venue:
        m = VENUE_AFTER_TIME.search(b["text"])
        venue = m.group(1).strip() if m else None
    title = clean_title(ld.get("name") or b["title"] or "")
    city, allowed = detect_city(title, venue)
    desc = ld.get("description") or b["description"]
    free, price = detect_price(b.get("text"))
    ev = Event(
        source="tickettailor",
        url=url,
        title=title,
        start=start,
        end=end,
        time=time,
        venue=venue,
        city=city if allowed else None,
        category="concert" if not re.search(r"стендап|stand.?up", title + (desc or ""), re.I) else "show",
        description=desc,
        image=b["image"],
        lang=detect_lang(title, desc),
        free=free,
        price_from=price,
    )
    ev.allowed = allowed  # служебный признак, в JSON не попадает
    return ev


def collect(fetcher, organizers: list[str], max_details: int = 20) -> list[Event]:
    out: list[Event] = []
    for org in organizers:
        html = fetcher.get(listing_url(org))
        if not html:
            continue
        links = parse_listing_links(html, org)
        log.info("tickettailor/%s: %d ссылок", org, len(links))
        for url in links[:max_details]:
            page = fetcher.get(url)
            if not page:
                continue
            ev = parse_detail(page, url)
            if not ev.allowed:
                log.info("tickettailor: пропуск (город не из списка): %s", ev.title)
                continue
            if ev.city == config.HOME_CITY:
                ev.city = None
            out.append(ev)
    return out
