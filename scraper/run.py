"""Ежедневный сбор: источники → единый формат → дедупликация → оценка → docs/data/events.json.

Запуск:  python -m scraper.run
Только часть источников:  python -m scraper.run --only prague.eu,tickettailor
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config
from .dates import overlaps, upcoming_weekend
from .http import Fetcher
from .models import Event
from .score import score_event
from .sources import kudyznudy, prague_eu, telegram, tickettailor

log = logging.getLogger("scraper")
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "events.json"


def merge(events: list[Event]) -> list[Event]:
    """Одно событие из нескольких источников → одна запись с самыми полными полями."""
    by_key: dict[str, Event] = {}
    for ev in events:
        if not ev.title:
            continue
        cur = by_key.get(ev.key)
        if cur is None:
            by_key[ev.key] = ev
            continue
        for f in ("venue", "time", "description", "image", "category", "end", "free", "price_from"):
            if getattr(cur, f) in (None, "") and getattr(ev, f) not in (None, ""):
                setattr(cur, f, getattr(ev, f))
        if ev.lang == "ru":
            cur.lang = "ru"
    return list(by_key.values())


def in_horizon(ev: Event, today: date) -> bool:
    if ev.start is None:
        return ev.source.startswith("telegram")  # пост без даты — показываем во вкладке RU
    return overlaps(ev.start, ev.end, today, today + timedelta(days=config.HORIZON_DAYS))


def build(events: list[Event], today: date, errors: dict[str, str]) -> dict:
    weekend = upcoming_weekend(today)
    events = [score_event(e, weekend) for e in merge(events) if in_horizon(e, today)]
    events.sort(key=lambda e: (-e.score, e.start or date.max))
    counts: dict[str, int] = {}
    for e in events:
        src = e.source.split(":")[0]
        counts[src] = counts.get(src, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weekend": {"from": weekend[0].isoformat(), "to": weekend[1].isoformat()},
        "counts": counts,
        "errors": errors,
        "events": [e.to_json() for e in events],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="через запятую: prague.eu,kudyznudy,tickettailor,telegram")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    today = date.today()
    weekend = upcoming_weekend(today)
    fetcher = Fetcher()
    jobs = {
        "prague.eu": lambda: prague_eu.collect(fetcher),
        "kudyznudy": lambda: kudyznudy.collect(fetcher, weekend),
        "tickettailor": lambda: tickettailor.collect(fetcher, config.TICKETTAILOR_ORGANIZERS),
        "telegram": lambda: telegram.collect(fetcher, config.TELEGRAM_CHANNELS),
    }
    only = set(args.only.split(",")) if args.only else set(jobs)

    collected: list[Event] = []
    errors: dict[str, str] = {}
    for name, job in jobs.items():
        if name not in only:
            continue
        try:
            items = job()
            log.info("%s: всего %d", name, len(items))
            if not items:
                errors[name] = "0 событий — возможно, изменилась вёрстка сайта"
            collected.extend(items)
        except Exception as e:  # один сломанный источник не должен ронять весь сбор
            log.exception("%s упал", name)
            errors[name] = f"{type(e).__name__}: {e}"

    data = build(collected, today, errors)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Записано %d событий в %s; ошибки: %s", len(data["events"]), args.out, errors or "нет")
    # Код возврата 1 только если не собралось вообще ничего — чтобы Actions прислал письмо
    return 0 if data["events"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
