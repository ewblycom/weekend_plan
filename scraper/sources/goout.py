"""GoOut (goout.net) — крупнейший чешский агрегатор с билетами. Экспериментальный источник.

Берём ссылки на события со списков Праги и открываем страницы событий:
дата — из JSON-LD/мета, место, адрес, цена («Vstupné»), ссылка на билеты GoOut и сайт площадки.
У GoOut бывает «виртуальная очередь» против перегрузки — тогда страница пустая, и источник
просто вернёт меньше событий (это видно в counts/errors в events.json).
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from ..dates import parse_iso, parse_range
from ..extract import external_links, jsonld_venue, meta, page_basics, soup_of
from ..models import Event, detect_lang
from ..pricing import detect_price

log = logging.getLogger(__name__)

BASE = "https://goout.net"
LISTINGS = [
    "/cs/praha/akce/leznyvlkk/",
    "/cs/praha/akce/leznyvlkk/?sort=popularity",
    "/cs/praha/koncerty/leznyvlkkzf/",
    "/cs/praha/jine-akce/leznyvlkkzu/",
]
EVENT_HREF = re.compile(r"^/cs/[^/]+/sz[a-z]+/?$")
WAITING = re.compile(r"virtuální frontu|virtual queue|Waiting Room", re.I)
CATEGORY = {"koncerty": "concert", "divadlo": "theater", "vystavy": "exhibition", "festivaly": "festival",
            "sport": "sport", "vecirky": "concert", "party": "concert", "jine-akce": "other",
            "workshopy": "workshop", "pro-deti": "kids", "film": "other", "gastro": "food"}
TITLE_TAIL = re.compile(r"\s+-\s+.*?-\s+GoOut$")


def parse_listing(html: str) -> list[str]:
    out = []
    for a in soup_of(html).find_all("a", href=True):
        path = a["href"].replace(BASE, "").split("?")[0]
        if EVENT_HREF.match(path) and not path.startswith("/cs/listky/"):
            url = urljoin(BASE, path)
            if url not in out:
                out.append(url)
    return out


def _field(text: str, label: str) -> str | None:
    m = re.search(rf"\n{label}\n+([^\n]+)", "\n" + text)
    return m.group(1).strip() if m else None


def parse_detail(html: str, url: str) -> Event | None:
    if WAITING.search(html[:3000]):
        return None
    b = page_basics(html)
    soup = soup_of(html)
    ld = b["jsonld"] or {}
    title = ld.get("name") or TITLE_TAIL.sub("", meta(soup, "og:title") or "") or ""
    if not title:
        return None
    start = parse_iso(ld.get("startDate") or meta(soup, "event:start_time") or meta(soup, "article:published_time"))
    end = parse_iso(ld.get("endDate")) or start
    raw = ld.get("startDate") or ""
    time = raw[11:16] if len(raw) >= 16 and raw[11:16] != "00:00" else None
    text = b["text"]
    if not time:   # «Health + VOWWS - zítra 19:00 - ARCHA+ - GoOut»
        m = re.search(r"\b(\d{1,2}:\d{2})\b", meta(soup, "og:title") or "")
        time = m.group(1) if m else None
    if not start:
        start, end, time = parse_range(text)
    venue = jsonld_venue(ld) if ld else None
    venue = venue or _field(text, "Místo")
    cat = None
    for a in soup.find_all("a", href=True):
        m = re.search(r"/cs/praha/([a-z-]+)/", a["href"])
        if m and m.group(1) in CATEGORY:
            cat = CATEGORY[m.group(1)]
            break
    tickets = next((urljoin(BASE, a["href"]) for a in soup.find_all("a", href=True) if "/listky/" in a["href"]), None)
    site, _ = external_links(soup)
    price_txt = _field(text, "Vstupné") or ""
    free, price = detect_price(price_txt + " Kč" if price_txt and "Kč" not in price_txt else price_txt)
    if re.search(r"zdarma|free", price_txt, re.I):
        free, price = True, None
    return Event(
        source="goout", url=url, title=title.strip(), start=start, end=end, time=time,
        venue=venue, category=cat or "other", description=b["description"] if b["description"] and "GoOut" not in b["description"] else None,
        image=b["image"], lang=detect_lang(title, text[:800]), free=free, price_from=price,
        booking=tickets, link=site,
        slots=[{"date": start.isoformat(), "time": time}] if start and time and start == end else [],
    )


def collect(fetcher, max_details: int = 45) -> list[Event]:
    links: list[str] = []
    for path in LISTINGS:
        html = fetcher.get(urljoin(BASE, path))
        if not html:
            continue
        if WAITING.search(html[:3000]):
            log.warning("goout: виртуальная очередь на %s", path)
            continue
        found = parse_listing(html)
        log.info("goout%s: %d ссылок", path, len(found))
        links.extend(u for u in found if u not in links)
    out: list[Event] = []
    for url in links[:max_details]:
        page = fetcher.get(url)
        ev = parse_detail(page, url) if page else None
        if ev:
            out.append(ev)
    return out
