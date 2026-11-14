"""Разбор дат на чешском, русском и английском + логика «ближайших выходных»."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

DASH = r"\s*[—–-]\s*"

# "28. 7. 2026—20. 11. 2026, 8:00—19:00" / "21. 11. 2026, 11:00—17:00"
NUMERIC_RANGE = re.compile(
    r"(?P<d1>\d{1,2})\.\s*(?P<m1>\d{1,2})\.\s*(?P<y1>\d{4})"
    r"(?:" + DASH + r"(?P<d2>\d{1,2})\.\s*(?P<m2>\d{1,2})\.\s*(?P<y2>\d{4}))?"
    r"(?:,\s*(?P<time>\d{1,2}:\d{2}(?:" + DASH + r"\d{1,2}:\d{2})?))?"
)

CS_MONTHS = {
    "ledna": 1, "února": 2, "unora": 2, "března": 3, "brezna": 3, "dubna": 4,
    "května": 5, "kvetna": 5, "června": 6, "cervna": 6, "července": 7, "cervence": 7,
    "srpna": 8, "září": 9, "zari": 9, "října": 10, "rijna": 10,
    "listopadu": 11, "prosince": 12,
}
RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
EN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# "14. listopadu 2026"
CS_LONG = re.compile(r"(\d{1,2})\.\s*(" + "|".join(CS_MONTHS) + r")(?:\s+(\d{4}))?", re.I)
# "21 ноября" / "21 ноября 2026"
RU_LONG = re.compile(r"(\d{1,2})\s+(" + "|".join(RU_MONTHS) + r")(?:\s+(\d{4}))?", re.I)
# "Wed 21 Oct 2026 20:00"
EN_LONG = re.compile(
    r"(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})(?:\s+(\d{1,2}:\d{2}))?",
    re.I,
)
# "21.11." или "21.11.2026" в постах Telegram
SHORT_NUMERIC = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})?\b")


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _guess_year(m: int, d: int, today: date) -> int:
    """Без года: берём ближайшую будущую дату (в декабре '5. ledna' — это следующий год)."""
    candidate = _safe(today.year, m, d)
    if candidate and candidate < today - timedelta(days=30):
        return today.year + 1
    return today.year


def parse_range(text: str, today: date | None = None) -> tuple[date | None, date | None, str | None]:
    """Возвращает (start, end, time). Первое найденное совпадение в тексте."""
    today = today or date.today()
    if not text:
        return None, None, None

    m = NUMERIC_RANGE.search(text)
    if m:
        start = _safe(int(m["y1"]), int(m["m1"]), int(m["d1"]))
        end = _safe(int(m["y2"]), int(m["m2"]), int(m["d2"])) if m["d2"] else start
        time = re.sub(DASH, "—", m["time"]) if m["time"] else None
        return start, end, time

    m = EN_LONG.search(text)
    if m:
        d = _safe(int(m[3]), EN_MONTHS[m[2].lower()[:3]], int(m[1]))
        return d, d, m[4]

    for rx, months in ((CS_LONG, CS_MONTHS), (RU_LONG, RU_MONTHS)):
        m = rx.search(text)
        if m:
            mon = months[m[2].lower()]
            y = int(m[3]) if m[3] else _guess_year(mon, int(m[1]), today)
            d = _safe(y, mon, int(m[1]))
            return d, d, None

    m = SHORT_NUMERIC.search(text)
    if m and 1 <= int(m[2]) <= 12:
        y = int(m[3]) if m[3] else _guess_year(int(m[2]), int(m[1]), today)
        d = _safe(y, int(m[2]), int(m[1]))
        return d, d, None

    return None, None, None


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def upcoming_weekend(today: date | None = None) -> tuple[date, date]:
    """Пятница–воскресенье. В субботу/воскресенье — текущие выходные."""
    today = today or date.today()
    wd = today.weekday()  # пн=0 … вс=6
    if wd >= 4:
        friday = today - timedelta(days=wd - 4)
    else:
        friday = today + timedelta(days=4 - wd)
    return friday, friday + timedelta(days=2)


def overlaps(start: date | None, end: date | None, a: date, b: date) -> bool:
    if not start:
        return False
    end = end or start
    return start <= b and end >= a
