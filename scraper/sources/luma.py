"""Luma (luma.com/prague) — комьюнити-события: йога, танцы, забеги, настолки, лекции, вечеринки.

Список Праги отдаёт ссылки luma.com/<id>; дату, место и цену берём со страницы события (JSON-LD Event).
"""
from __future__ import annotations

import logging
import re

from ..dates import parse_iso
from ..extract import jsonld_venue, page_basics, soup_of
from ..models import Event, detect_lang
from ..pricing import detect_price

log = logging.getLogger(__name__)

LIST_URL = "https://luma.com/prague"
SKIP = {"discover", "signin", "pricing", "app", "prague", "create", "home", "explore", "calendar", "user", "terms", "privacy"}
LINK = re.compile(r"^https://luma\.com/([\w.-]+)/?$")
HINTS = [
    (re.compile(r"\byoga|pilates|run\b|running|běh|fitness|sauna|wellness|climb", re.I), "sport"),
    (re.compile(r"workshop|class|kurz|dílna|masterclass|ceramic|keramik|paint|draw", re.I), "workshop"),
    (re.compile(r"rave|party|dj\b|concert|live\b|koncert|jazz", re.I), "concert"),
    (re.compile(r"theat|divad|představení|stand.?up|comedy", re.I), "theater"),
    (re.compile(r"games|quiz|kvíz|board", re.I), "active"),
    (re.compile(r"market|trh|food|wine|víno|tasting|degust|pizza|brunch", re.I), "food"),
    (re.compile(r"exhibit|výstav|gallery|galerie", re.I), "exhibition"),
]
BUSINESS = re.compile(r"\bAI\b|startup|founder|product|developer|summit|conference|konference|networking|"
                      r"budoucnost práce|supply chain|data day|agentic|pitch|investor|fuck-?up night", re.I)


def _lang(*t) -> str:
    l = detect_lang(*t)
    if l == "ru":
        return l
    return "cs" if re.search(r"[ěščřžýáíéůú]", " ".join(x or "" for x in t), re.I) else "en"


def parse_listing(html: str) -> list[str]:
    out = []
    for a in soup_of(html).find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = "https://luma.com" + href
        m = LINK.match(href.split("?")[0])
        if m and m.group(1).lower() not in SKIP and href not in out:
            out.append(href.split("?")[0])
    return out


def parse_detail(html: str, url: str) -> Event | None:
    b = page_basics(html)
    ld = b["jsonld"] or {}
    title = (ld.get("name") or b["title"] or "").replace(" · Luma", "").strip()
    if not title or BUSINESS.search(title):
        return None              # рабочие митапы и конференции — не про отдых вдвоём
    raw = ld.get("startDate") or ""
    start = parse_iso(raw)
    if not start:
        return None
    end = parse_iso(ld.get("endDate")) or start
    time = raw[11:16] if len(raw) >= 16 else None
    offers = ld.get("offers")
    offers = offers[0] if isinstance(offers, list) and offers else offers
    free = price = None
    if isinstance(offers, dict):
        try:
            p = float(offers.get("price") or 0)
            cur = (offers.get("priceCurrency") or "CZK").upper()
            if p == 0:
                free = True
            elif cur == "CZK":
                price = int(p)
            elif cur == "EUR":
                price = int(p * 25)
        except (TypeError, ValueError):
            pass
    if free is None and price is None:
        free, price = detect_price(b["text"][:1500])
    blob = f"{title} {b['description'] or ''}"
    cat = next((c for rx, c in HINTS if rx.search(blob)), "other")
    return Event(source="luma", url=url, title=title, start=start, end=end, time=time,
                 venue=jsonld_venue(ld) if ld else None, category=cat, description=b["description"],
                 image=b["image"], lang=_lang(title, b["description"]), free=free, price_from=price,
                 booking=url, slots=[{"date": start.isoformat(), "time": time}] if time and start == end else [])


def collect(fetcher, max_details: int = 30) -> list[Event]:
    html = fetcher.get(LIST_URL)
    if not html:
        return []
    links = parse_listing(html)
    log.info("luma: %d ссылок", len(links))
    out = []
    for url in links[:max_details]:
        page = fetcher.get(url)
        ev = parse_detail(page, url) if page else None
        if ev:
            out.append(ev)
    return out
