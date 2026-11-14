"""Постоянные места (docs/data/places.json): раз в день подтягиваем прямые ссылки на сайт и бронь.

Источник для каждого места — его страница на prague.eu или Kudy z nudy (поле url).
Ссылки, вписанные вручную (manual: true), не трогаем.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import re

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


def enrich(fetcher, path: Path = FILE) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for p in data.get("places", []):
        url = p.get("url") or ""
        listing = any(h in url for h in ("prague.eu", "kudyznudy.cz"))
        manual = bool(p.get("manual"))
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
