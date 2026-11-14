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
from ..dates import parse_iso, parse_range
from ..extract import soup_of
from ..models import Event
from ..pricing import detect_price

log = logging.getLogger(__name__)

EVENT_WORDS = re.compile(
    r"концерт|стендап|stand.?up|выставк|ярмарк|маркет|фестивал|мастер.?класс|воркшоп|"
    r"спектакл|театр|премьер|гастрол|вечеринк|квиз|кинопоказ|лекци|экскурси|билет|вход свободный|регистрац",
    re.I,
)


# Новостные каналы: берём только посты с понятной датой, чтобы не тащить новости
NEWS_CHANNELS = {"pozor_brno", "the_cesko"}
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


def parse_cesko_afisha(text: str, channel: str, url: str, today: date) -> list[Event]:
    """В ежедневном дайджесте блок «Афиша:» — список заголовков без дат. Берём только Прагу."""
    if "Афиша:" not in text:
        return []
    block = text.split("Афиша:", 1)[1].split("Акции:", 1)[0]
    out = []
    for line in block.split("\n"):
        title = LEAD_JUNK.sub("", line.strip()).rstrip(";.")
        if len(title) < 12:
            continue
        low = title.lower()
        if not any(w in low for w in config.PRAGUE_WORDS):
            continue
        out.append(Event(source=f"telegram:{channel}", url=url, title=title[:140],
                         category="other", description=title, lang="ru", date_uncertain=True))
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
        text = text_el.get_text("\n", strip=True)
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
        if "Афиша:" in text:
            out.extend(parse_cesko_afisha(text, ch, post_url, today))
            continue
        if not EVENT_WORDS.search(text) or not _is_prague(text):
            continue
        start, end, _ = parse_range(text, today)
        if start and start < today:
            continue
        if ch in NEWS_CHANNELS and start is None:
            continue
        first_line = text.split("\n", 1)[0]
        free, price = detect_price(text)
        out.append(Event(
            source=f"telegram:{channel.lstrip('@')}",
            url=post_url,
            title=re.sub(r"^[^\wА-Яа-я]+", "", first_line)[:140] or "Пост в Telegram",
            start=start,
            end=end,
            category="other",
            description=text[:600],
            lang="ru",
            date_uncertain=start is None,
            free=free,
            price_from=price,
        ))
    return out


def collect(fetcher, channels: list[str]) -> list[Event]:
    out: list[Event] = []
    for ch in channels:
        html = fetcher.get(channel_url(ch))
        if html:
            items = parse_channel(html, ch)
            log.info("telegram/%s: %d афишных постов", ch, len(items))
            out.extend(items)
    return out
