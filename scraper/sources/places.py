"""Постоянные места (docs/data/places.json): раз в день подтягиваем прямые ссылки на сайт и бронь.

Источник для каждого места — его страница на prague.eu или Kudy z nudy (поле url).
Ссылки, вписанные вручную (manual: true), не трогаем.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import re
import unicodedata
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from ..extract import page_basics, soup_of

log = logging.getLogger(__name__)
FILE = Path(__file__).resolve().parents[2] / "docs" / "data" / "places.json"


RANGE = re.compile(r"(\d{1,2})[:.](\d{2})\s*[—–-]\s*(\d{1,2})[:.](\d{2})")


def opening_hours(html: str) -> str | None:
    """Первый диапазон времени после «otevírací doba / opening hours» на странице места, напр. «10:00–22:00»."""
    soup = soup_of(html)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    m = re.search(r"otevírací doba|otevírací hodiny|provozní doba|opening hours|open daily|открыто", text, re.I)
    if not m:
        return None
    r = RANGE.search(text[m.end():m.end() + 200])
    if not r:
        return None
    a, b, c, d = r.groups()
    return f"{int(a):02d}:{b}–{int(c):02d}:{d}"


# агрегаторы, соцсети и карты — это не «собственный сайт места»
NOT_OWN_SITE = re.compile(
    r"(facebook|instagram|tiktok|youtube|google|bing|duckduckgo|firmy\.cz|mapy\.com|mapy\.cz|slevomat|tripadvisor|"
    r"kudyznudy|prague\.eu|goout|wikipedia|zivefirmy|kidsmap|inyourpocket|yelp|booking\.com|airbnb|"
    r"seznam\.cz|pinterest|twitter|x\.com|linkedin|blesk|denik|idnes|novinky|czechtourism|waymarking|"
    r"apple\.com|trip\.com|cvent|localczechia|govisit|everyrink|nakluziste|kluzistepraha|verejne-brusleni)", re.I)
GENERIC = {"praha", "prague", "prag", "bowling", "laser", "game", "tag", "club", "bar", "arena", "park", "the", "and",
           "centrum", "center", "wellness", "sauna", "lazne", "kurz", "kurzy", "rande", "art", "chill", "gaming", "space",
           "boulder", "stena", "lezecka", "kluziste", "ice", "rink", "vr", "pc", "sport", "basic", "zakladni", "kurz"}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def name_tokens(name: str) -> list[str]:
    """Отличительные слова названия: «Absolutní Bowling» -> [absolutni], «Mercuria Laser Game Braník» -> [mercuria, branik]."""
    words = re.findall(r"[a-z0-9]{3,}", _fold(re.sub(r"[—–].*$", "", name)))
    return [w for w in words if w not in GENERIC]


def search_results(html: str) -> list[str]:
    """Ссылки результатов выдачи DuckDuckGo (html-версия) или Bing, по порядку."""
    out: list[str] = []
    for a in soup_of(html).find_all("a", href=True):
        h = a["href"]
        if "uddg=" in h:
            h = unquote(parse_qs(urlparse(h if h.startswith("http") else "https:" + h).query).get("uddg", [""])[0])
        if h.startswith("http") and h not in out:
            out.append(h)
    return out


def pick_site(name: str, links: list[str]) -> str | None:
    """Первая ссылка, чей домен содержит отличительное слово названия и не является агрегатором. Возвращает корень сайта."""
    toks = name_tokens(name)
    if not toks:
        return None
    for link in links:
        host = urlparse(link).netloc.lower()
        if NOT_OWN_SITE.search(host):
            continue
        flat = re.sub(r"[^a-z0-9]", "", _fold(host))
        if toks[0] in flat or sum(t in flat for t in toks) >= 2:
            return f"{urlparse(link).scheme}://{urlparse(link).netloc}/"
    return None


def find_site(fetcher, name: str, area: str = "") -> str | None:
    """Ищем собственный сайт места по названию. Поисковики дёргаем напрямую (один запрос на место, результат сохраняется)."""
    q = quote_plus(f"{name} Praha {area}".strip())
    for url in (f"https://html.duckduckgo.com/html/?q={q}", f"https://www.bing.com/search?q={q}&setlang=cs"):
        try:
            r = fetcher.session.get(url, timeout=fetcher.timeout)
        except Exception as e:  # noqa: BLE001
            log.warning("поиск сайта %s: %s", name, e)
            continue
        if r.ok:
            site = pick_site(name, search_results(r.text))
            if site:
                return site
    return None


def enrich(fetcher, path: Path = FILE) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for p in data.get("places", []):
        url = p.get("url") or ""
        listing = any(h in url for h in ("prague.eu", "kudyznudy.cz"))
        manual = bool(p.get("manual"))
        if manual and not p.get("site") and not p.get("site_searched"):
            found = find_site(fetcher, p.get("name", ""), p.get("area", ""))
            p["site_searched"] = True  # не искать заново каждый прогон; сбросить флаг, чтобы повторить
            changed += 1
            if found:
                p["site"] = found
                log.info("places: %s -> %s", p.get("name"), found)
        if manual:
            # вручную внесённые места: ссылки не трогаем, подтягиваем только часы работы с их собственного сайта
            src = p.get("site") or ""
        else:
            src = url if listing else ""
        if not src:
            continue
        html = fetcher.get(src)
        if not html:
            continue
        b = page_basics(html)
        if not p.get("image") and b["image"]:
            p["image"] = b["image"]
            changed += 1
        if not manual:
            for key, val in (("site", b["site"]), ("booking", b["booking"])):
                if val and p.get(key) != val:
                    p[key] = val
                    changed += 1
        hours = opening_hours(html)
        if hours and not p.get("hours_fixed") and p.get("hours") != hours:
            p["hours"] = hours
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("places: обновлено полей %d", changed)
    return changed
