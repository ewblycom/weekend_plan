"""Публичные Telegram-каналы через веб-превью https://t.me/s/<канал>.

Без логина и API-ключей: это та же страница, что видна в браузере.
Посты неструктурированные, поэтому берём только те, где есть дата и
«афишные» слова, и помечаем дату как неточную, если не нашли её в тексте.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from .. import config
from ..dates import RU_MONTHS, parse_iso, parse_range
from ..extract import meta, soup_of
from ..models import Event
from ..pricing import detect_price

log = logging.getLogger(__name__)

EVENT_WORDS = re.compile(
    r"концерт|стендап|stand.?up|выставк|ярмарк|маркет|фестивал|мастер.?класс|воркшоп|"
    r"спектакл|театр|премьер|гастрол|вечеринк|квиз|кинопоказ|лекци|экскурси|билет|вход свободный|регистрац",
    re.I,
)


# Все каналы новостные: берём только посты с понятной датой, чтобы не тащить новости
CESKO_EVENT = re.compile(r"https?://(?:www\.)?the-?cesko\.cz/events/[\w-]+")
STRUCT_DATE = re.compile(r"Дата\s*:", re.I)
STRUCT_PLACE = re.compile(r"(?:Локация|Место|Адрес)\s*:\s*(.+)", re.I)
CATEGORY_HINTS = [
    (re.compile(r"выставк", re.I), "exhibition"),
    (re.compile(r"ярмарк|рынок|рынки|маркет", re.I), "market"),
    (re.compile(r"фестивал", re.I), "festival"),
    (re.compile(r"концерт|вечеринк|dj", re.I), "concert"),
    (re.compile(r"спектакл|театр", re.I), "theater"),
    (re.compile(r"мастер.?класс|воркшоп", re.I), "workshop"),
    (re.compile(r"стендап|stand.?up", re.I), "show"),
]
MONTHS_RX = "|".join(RU_MONTHS)
# «18-22 ноября», «30 ноября - 2 декабря»
RU_SPAN = re.compile(
    rf"(\d{{1,2}})(?:\s+({MONTHS_RX}))?\s*[-–—]\s*(\d{{1,2}})\s+({MONTHS_RX})(?:\s+(\d{{4}}))?", re.I)
RU_UNTIL = re.compile(rf"до\s+(\d{{1,2}})\s+({MONTHS_RX})(?:\s+(\d{{4}}))?", re.I)


def _text(el) -> str:
    """Текст поста: <br> → перенос строки, а ссылки и жирный шрифт НЕ рвут строку.

    (get_text("\\n") делил заголовки вида «В Праге пройдет <a>фестиваль</a>» на куски.)
    """
    for br in el.find_all("br"):
        br.replace_with("\n")
    return re.sub(r"[ \t\u00a0]*\n[ \t\u00a0]*", "\n", el.get_text()).strip()


def guess_category(text: str) -> str:
    for rx, cat in CATEGORY_HINTS:
        if rx.search(text):
            return cat
    return "other"


def ru_span(value: str, today: date):
    """Русская дата или диапазон → (start, end, time)."""
    m = RU_SPAN.search(value)
    if m:
        m2 = RU_MONTHS[m[4].lower()]
        m1 = RU_MONTHS[m[2].lower()] if m[2] else m2
        year = int(m[5]) if m[5] else today.year
        try:
            start, end = date(year, m1, int(m[1])), date(year, m2, int(m[3]))
        except ValueError:
            return None, None, None
        return start, end, None
    m = RU_UNTIL.search(value)
    if m:
        year = int(m[3]) if m[3] else today.year
        try:
            return today, date(year, RU_MONTHS[m[2].lower()], int(m[1])), None
        except ValueError:
            return None, None, None
    return parse_range(value, today)


BG_URL = re.compile(r"background-image:\s*url\(['\"]?([^'\")]+)")


def _post_image(msg) -> str | None:
    """Первое фото поста из веб-превью (у t.me/s оно в style=background-image)."""
    el = msg.select_one(".tgme_widget_message_photo_wrap, .tgme_widget_message_video_thumb, .link_preview_image")
    m = BG_URL.search(el.get("style", "")) if el else None
    return m.group(1) if m else None


def _clock(value: str | None) -> str | None:
    m = re.search(r"(\d{1,2}:\d{2})(?:\s*[-–—]\s*(\d{1,2}:\d{2}))?", value or "")
    return None if not m else (f"{m[1]}—{m[2]}" if m[2] else m[1])


def _short_venue(place: str) -> str:
    """«клуб в центре Праги - The Pitch» → «The Pitch»; «Westfield Chodov, первый этаж» → «Westfield Chodov»."""
    place = place.strip().rstrip(".")
    if " - " in place:
        place = place.rsplit(" - ", 1)[1]
    parts = [x.strip() for x in place.split(",")]
    head = parts[0]
    if re.search(r"\d", head) and len(parts) > 1:   # улица с номером — оставим и город
        head = f"{parts[0]}, {parts[1]}"
    return head[:90]


def parse_cesko_event(html: str, url: str, today: date, hint: str = "") -> Event | None:
    """Страница the-cesko.cz/events/…: блок «Дата / Время / Место / Вход» + заголовок."""
    soup = soup_of(html)
    title = (meta(soup, "og:title") or (soup.h1.get_text(" ", strip=True) if soup.h1 else "")).strip()
    body = re.sub(r"\s+", " ", soup.get_text(" "))
    body = body.split("Скопировать ссылку")[0] if body.count("Скопировать ссылку") > 1 else body
    fields: dict[str, str] = {}
    keys = "Дата|Время|Место|Вход|Цена|Стоимость|Билеты|Адрес|Сайт|Организатор"
    for m in re.finditer(rf"({keys}):\s*(.*?)(?=\s(?:{keys}):|\sСкопировать|\sРедакция|$)", body):
        fields.setdefault(m[1], m[2].strip())
    if "Дата" not in fields or not title:
        return None
    start, end, _ = ru_span(fields["Дата"], today)
    if not start or (end or start) < today:
        return None
    venue_raw = fields.get("Место") or fields.get("Адрес") or ""
    if not _is_prague(f"{title} {venue_raw} {hint}"):
        return None
    price_src = " ".join(fields.get(k, "") for k in ("Вход", "Цена", "Стоимость", "Билеты"))
    free, price = detect_price(price_src) if price_src else (None, None)
    desc = meta(soup, "og:description") or meta(soup, "description") or ""
    return Event(
        source="telegram:the_cesko", url=url, title=title[:140], start=start, end=end,
        image=meta(soup, "og:image"),
        time=_clock(fields.get("Время")), venue=_short_venue(venue_raw) if venue_raw else None,
        category=guess_category(title + " " + desc), description=desc[:400], lang="ru",
        free=free, price_from=price)


def cesko_links(html: str, today: date | None = None, max_age_days: int = 10) -> dict[str, str]:
    """Ссылки на страницы событий the-cesko.cz из свежих постов канала → {url: подсказка-заголовок}."""
    today = today or date.today()
    found: dict[str, str] = {}
    for msg in soup_of(html).select(".tgme_widget_message"):
        time_el = msg.select_one("time[datetime]")
        posted = parse_iso(time_el["datetime"]) if time_el else None
        if posted and posted < today - timedelta(days=max_age_days):
            continue
        for a in msg.select(".tgme_widget_message_text a[href]"):
            m = CESKO_EVENT.search(a["href"])
            if m:
                found.setdefault(m.group(0), a.get_text(" ", strip=True))
    return found
SHORT_DATE = re.compile(r"(?:до\s+)?(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\.(\d{1,2})(?:\.(\d{4}))?")
LEAD_JUNK = re.compile(r"^[^\w«\"]+", re.U)


def _is_prague(text: str) -> bool:
    t = text.lower()
    if any(w in t for w in config.PRAGUE_WORDS):
        return True
    return not any(w in t for w in config.OTHER_CITIES)


def _short_range(line: str, today: date):
    """«13-15.11», «14.11», «до 17.11» → (start, end)."""
    m = SHORT_DATE.search(line)
    if not m:
        return None, None
    d1, d2, mon = int(m[1]), int(m[2] or m[1]), int(m[3])
    year = int(m[4]) if m[4] else today.year
    try:
        end = date(year, mon, d2)
        start = date(year, mon, d1)
    except ValueError:
        return None, None
    if line.strip().lower().startswith("до") and not m[2]:
        start = max(today, end - timedelta(days=0))
    return start, end


def parse_pozor_digest(text: str, channel: str, url: str, today: date) -> list[Event]:
    """Дайджест «Чем заняться на выходных»: разделы БРНО/ПРАГА, пункты «▪️Название»."""
    out: list[Event] = []
    section, cur = None, None

    def flush():
        nonlocal cur
        if cur and section == "praha" and cur["title"]:
            start, end = _short_range(cur["date"], today) if cur["date"] else (None, None)
            if not (end and end < today):
                desc = " ".join(cur["desc"])
                free, price = detect_price(desc)
                out.append(Event(
                    source=f"telegram:{channel}", url=url, title=cur["title"][:140],
                    start=start, end=end, category="other",
                    description=desc[:400], lang="ru",
                    date_uncertain=start is None, free=free, price_from=price))
        cur = None

    for line in text.split("\n"):
        l = line.strip()
        up = l.upper()
        if "БРНО" in up and len(l) < 15:
            flush(); section = "brno"; continue
        if "ПРАГА" in up and len(l) < 15:
            flush(); section = "praha"; continue
        if l.startswith("▪"):
            flush()
            cur = {"title": LEAD_JUNK.sub("", l.lstrip("▪️ ")), "desc": [], "date": None}
        elif cur is not None:
            if l.startswith("📅"):
                cur["date"] = l.lstrip("📅 ")
            elif l.startswith("📱") or l.lower().startswith("подробнее") or l.startswith("___"):
                continue
            elif l and not cur["date"]:
                cur["desc"].append(l)
    flush()
    return out


def channel_url(channel: str) -> str:
    return f"https://t.me/s/{channel.lstrip('@')}"


def parse_channel(html: str, channel: str, today: date | None = None,
                  max_age_days: int = 10) -> list[Event]:
    today = today or date.today()
    soup = soup_of(html)
    out: list[Event] = []
    for msg in soup.select(".tgme_widget_message"):
        text_el = msg.select_one(".tgme_widget_message_text")
        if not text_el:
            continue
        text = _text(text_el)
        time_el = msg.select_one("time[datetime]")
        posted = parse_iso(time_el["datetime"]) if time_el else None
        if posted and posted < today - timedelta(days=max_age_days):
            continue
        link = msg.select_one("a.tgme_widget_message_date")
        post_url = link["href"] if link else channel_url(channel)
        ch = channel.lstrip("@")
        if "▪" in text and "ПРАГА" in text.upper():
            out.extend(parse_pozor_digest(text, ch, post_url, today))
            continue
        if "Афиша:" in text or CESKO_EVENT.search(text):
            continue  # афиша The Česko без дат: события берём со своих страниц (см. collect)
        structured = bool(STRUCT_DATE.search(text) and STRUCT_PLACE.search(text))
        if not structured and any(w in text.lower() for w in config.NOT_EVENT):
            continue
        if not (EVENT_WORDS.search(text) or structured) or not _is_prague(text):
            continue
        start, end, clock = parse_range(text, today)
        if start is None or start < today:
            continue   # без даты это новость, а не анонс
        first_line = text.split("\n", 1)[0]
        place = STRUCT_PLACE.search(text)
        free, price = detect_price(text)
        out.append(Event(
            source=f"telegram:{channel.lstrip('@')}",
            url=post_url,
            title=re.sub(r"^[^\wА-Яа-я]+", "", first_line)[:140] or "Пост в Telegram",
            start=start,
            end=end,
            time=clock or _clock(text),
            venue=_short_venue(place.group(1)) if place else None,
            image=_post_image(msg),
            category=guess_category(text),
            description=text[:600],
            lang="ru",
            free=free,
            price_from=price,
        ))
    return out


def collect(fetcher, channels: list[str], max_cesko_pages: int = 25) -> list[Event]:
    out: list[Event] = []
    today = date.today()
    for ch in channels:
        html = fetcher.get(channel_url(ch))
        if not html:
            continue
        items = parse_channel(html, ch, today)
        log.info("telegram/%s: %d афишных постов", ch, len(items))
        out.extend(items)
        if ch.lstrip("@") == "the_cesko":
            links = cesko_links(html, today)
            log.info("the_cesko: %d страниц афиши", len(links))
            for url, hint in list(links.items())[:max_cesko_pages]:
                page = fetcher.get(url)
                ev = parse_cesko_event(page, url, today, hint) if page else None
                if ev:
                    out.append(ev)
    return out
