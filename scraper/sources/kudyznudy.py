"""Kudy z nudy (Czechtourism): календарь событий по региону на даты выходных.

Список отдаёт только ссылки /akce/<slug>, поэтому дату, место и описание
берём со страницы события (JSON-LD, если есть; иначе Open Graph + текст).
Берём Прагу и Среднечешский край — у вас есть машина.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin

from ..dates import parse_iso, parse_range
from ..extract import jsonld_venue, page_basics, soup_of
from ..models import Event
from ..pricing import detect_price

log = logging.getLogger(__name__)

BASE = "https://www.kudyznudy.cz"
REGIONS = {"hlavni-mesto-praha": "Praha", "stredocesky-kraj": "Středočeský kraj"}
DETAIL_HREF = re.compile(r"^/akce/[^/?#]+$")
REGION_LINE = re.compile(r"Region:\s*([^\n]+)")

# Kudy z nudy пишет категорию в «хлебных крошках»: Úvod > Kalendář akcí > <категория>
CATEGORY_MAP = {
    "lidová řemesla a trhy": "market",
    "výstavy": "exhibition",
    "expozice a dlouhodobé akce": "exhibition",
    "hudební a divadelní akce": "concert",
    "kurzy a workshopy": "workshop",
    "gastronomické akce": "food",
    "festivaly": "festival",
    "společenské akce": "other",
    "sportovní akce": "sport",
    "akce pro děti": "kids",
    "komentované prohlídky": "tour",
    "historické a vojenské akce": "history",
}


def listing_url(region_slug: str, a: date, b: date) -> str:
    return f"{BASE}/kalendar-akci/{region_slug}?datum={a.isoformat()},{b.isoformat()}"


def parse_listing_links(html: str) -> list[str]:
    soup = soup_of(html)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        path = href.replace(BASE, "")
        if DETAIL_HREF.match(path):
            full = urljoin(BASE, path)
            if full not in links:
                links.append(full)
    return links


def parse_detail(html: str, url: str, fallback_start: date | None = None,
                 fallback_end: date | None = None) -> Event:
    basics = page_basics(html)
    text = basics["text"]
    ld = basics["jsonld"] or {}

    start = parse_iso(ld.get("startDate"))
    end = parse_iso(ld.get("endDate")) or start
    time = None
    if not start:
        start, end, time = parse_range(basics["description"] or "")
    if not start:
        start, end, time = parse_range(text)
    uncertain = False
    if not start and fallback_start:
        start, end, uncertain = fallback_start, fallback_end, True

    category = None
    low = text.lower()
    for label, cat in CATEGORY_MAP.items():
        # первая встреча метки в начале страницы (крошки) решает
        idx = low.find(label)
        if 0 <= idx < 600:
            category = cat
            break

    region = REGION_LINE.search(text)
    venue = jsonld_venue(ld) if ld else None
    if not venue and region:
        venue = region.group(1).strip()

    free, price = detect_price(text[:4000])
    return Event(
        source="kudyznudy",
        url=url,
        title=ld.get("name") or basics["title"] or url.rsplit("/", 1)[-1],
        start=start,
        end=end,
        time=time,
        venue=venue,
        category=category,
        description=basics["description"],
        image=basics["image"],
        free=free,
        price_from=price,
        date_uncertain=uncertain,
    )


def collect(fetcher, weekend: tuple[date, date], max_details: int = 45) -> list[Event]:
    a, b = weekend
    links: list[str] = []
    for slug in REGIONS:
        html = fetcher.get(listing_url(slug, a, b))
        if html:
            found = parse_listing_links(html)
            log.info("kudyznudy/%s: %d ссылок", slug, len(found))
            links.extend(l for l in found if l not in links)

    out: list[Event] = []
    for url in links[:max_details]:
        html = fetcher.get(url)
        if html:
            out.append(parse_detail(html, url, a, b))
    return out
