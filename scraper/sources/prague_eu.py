"""prague.eu (Prague City Tourism): списки событий по категориям.

На странице списка у каждой карточки есть всё нужное: категория, название (h2),
даты/время и площадка. Разбор не завязан на CSS-классы (они могут смениться):
ищем ссылки вида /cs/akce/<slug>/ и поднимаемся к ближайшему блоку с одним <h2>.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from ..dates import NUMERIC_RANGE, parse_range
from ..extract import soup_of
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


def collect(fetcher, max_per_category: int = 40) -> list[Event]:
    out: list[Event] = []
    for slug, cat in CATEGORIES.items():
        html = fetcher.get(listing_url(slug))
        if not html:
            continue
        items = parse_listing(html, cat)[:max_per_category]
        log.info("prague.eu/%s: %d событий", slug, len(items))
        out.extend(items)
    return out
