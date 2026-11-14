"""Vinegret.cz — русскоязычные новости Чехии с рубрикой «Афиша».

Ссылки на статьи берём с раздела /afisha и из постов канала @vinegret_cz,
оставляем только статьи рубрики «Афиша» про Прагу с понятной датой события.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from .. import config
from ..dates import parse_iso, parse_range
from ..extract import meta, page_basics, soup_of
from ..models import Event
from ..pricing import detect_price

log = logging.getLogger(__name__)

AFISHA_URL = "https://www.vinegret.cz/afisha"
CHANNEL_URL = "https://t.me/s/vinegret_cz"
ARTICLE = re.compile(r"^https?://(?:www\.)?vinegret\.cz/\d{5,}/[\w-]+/?$")
TIME = re.compile(r"(?:Время[^:\n]*:\s*)?с\s+(\d{1,2}:\d{2})(?:\s*до\s*(\d{1,2}:\d{2}))?|\bв\s+(\d{1,2}:\d{2})")
ADDRESS = re.compile(r"(?:Адрес|Место)[^:\n]*:\s*([^\n(]+)")
CATS = [
    (re.compile(r"концерт|выступ|стендап|джаз", re.I), "concert"),
    (re.compile(r"выставк", re.I), "exhibition"),
    (re.compile(r"ярмарк|рынок|рынки|маркет", re.I), "market"),
    (re.compile(r"фестивал", re.I), "festival"),
    (re.compile(r"спектакл|театр", re.I), "theater"),
    (re.compile(r"мастер.?класс|воркшоп|семинар", re.I), "workshop"),
    (re.compile(r"матч|забег|турнир|хоккей|футбол", re.I), "sport"),
]


def links_from(html: str) -> list[str]:
    out = []
    for a in soup_of(html).find_all("a", href=True):
        h = a["href"].split("?")[0].rstrip("/")
        if ARTICLE.match(h) and h not in out:
            out.append(h)
    return out


def parse_article(html: str, url: str, today: date) -> Event | None:
    soup = soup_of(html)
    section = (meta(soup, "article:section") or "") + " " + (meta(soup, "keywords") or "")
    if "Афиша" not in section:
        return None
    b = page_basics(html)
    title = (meta(soup, "og:title") or b["title"] or "").strip()
    text = b["text"]
    body = (b["description"] or "") + "\n" + text
    if not any(w in body.lower() for w in config.PRAGUE_WORDS):
        return None
    start, end, _ = parse_range(b["description"] or "", today)
    if not start:
        start, end, _ = parse_range(text, today)
    if not start or (end or start) < today:
        return None
    published = parse_iso(meta(soup, "article:modified_time") or meta(soup, "article:published_time"))
    if published and (start - published).days > 120:
        return None   # дата, скорее всего, взята не о событии
    tm = TIME.search(text)
    time = None
    if tm:
        time = f"{tm[1]}—{tm[2]}" if tm[1] and tm[2] else (tm[1] or tm[3])
    addr = ADDRESS.search(text)
    free, price = detect_price(text[:3000])
    cat = next((c for rx, c in CATS if rx.search(title)), "other")
    return Event(source="vinegret", url=url, title=title[:140], start=start, end=end, time=time,
                 venue=addr.group(1).strip()[:90] if addr else None, category=cat,
                 description=(b["description"] or "")[:400], image=b["image"], lang="ru",
                 free=free, price_from=price, link=b["site"])


def collect(fetcher, max_articles: int = 25) -> list[Event]:
    today = date.today()
    links: list[str] = []
    for src in (AFISHA_URL, CHANNEL_URL):
        html = fetcher.get(src)
        if html:
            links.extend(u for u in links_from(html) if u not in links)
    log.info("vinegret: %d статей-кандидатов", len(links))
    out, loaded, afisha = [], 0, 0
    for url in links[:max_articles]:
        page = fetcher.get(url)
        if not page:
            continue
        loaded += 1
        if "Афиша" in page:
            afisha += 1
        ev = parse_article(page, url, today)
        if ev:
            out.append(ev)
    if not out:
        # диагностика попадёт в errors в events.json
        raise RuntimeError(f"ссылок {len(links)}, загружено {loaded}, рубрика «Афиша» {afisha}, с датой в Праге 0")
    return out
