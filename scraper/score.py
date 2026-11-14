"""Оценка «насколько это нам интересно на выходных». Чем выше score — тем выше в списке."""
from __future__ import annotations

from datetime import date

from . import config
from .dates import overlaps
from .models import Event


def _has(text: str, markers: list[str]) -> bool:
    return any(m in text for m in markers)


def score_event(ev: Event, weekend: tuple[date, date]) -> Event:
    title = (ev.title or "").lower()
    blob = " ".join(filter(None, [ev.title, ev.venue, ev.description])).lower()
    s = config.CATEGORY_WEIGHT.get(ev.category, 1.0)
    tags: list[str] = []

    if ev.lang == "ru":
        s += 3
        tags.append("на русском")
    if _has(blob, config.COUPLE_MARKERS):
        s += 1.5
        tags.append("для двоих")
    if _has(" ".join(filter(None, [ev.title, ev.venue])).lower(), config.TOURIST_MARKERS):
        s -= 4
        tags.append("туристический центр")
    if _has(title, config.KIDS_MARKERS):
        s -= 2
    if _has(blob, config.NEAR_HOME):
        s += 0.5
        tags.append("рядом с домом")
    if ev.free:
        s += 0.3
        tags.append("бесплатно")

    if ev.start:
        length = ((ev.end or ev.start) - ev.start).days
        if length > 21:
            s -= 1.5          # идёт месяцами — не срочно
            tags.append("идёт долго")
        elif overlaps(ev.start, ev.end, *weekend) and length <= 2:
            s += 1.0          # только в эти выходные — не пропустить
            tags.append("только сейчас")
    if ev.date_uncertain:
        s -= 1

    ev.score = round(s, 2)
    ev.tags = tags
    return ev
