"""Ticket Tailor: русскоязычные концерты и стендап (организатор Spotlight Production).

Список организаторов можно расширять в config.TICKETTAILOR_ORGANIZERS.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

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
    title = ld.get("name") or b["title"] or ""
    desc = ld.get("description") or b["description"]
    free, price = detect_price(b.get("text"))
    return Event(
        source="tickettailor",
        url=url,
        title=title,
        start=start,
        end=end,
        time=time,
        venue=venue,
        category="concert" if not re.search(r"стендап|stand.?up", title + (desc or ""), re.I) else "show",
        description=desc,
        image=b["image"],
        lang=detect_lang(title, desc),
        free=free,
        price_from=price,
    )


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
            if page:
                out.append(parse_detail(page, url))
    return out
