"""Постоянные места (docs/data/places.json): раз в день подтягиваем прямые ссылки на сайт и бронь.

Источник для каждого места — его страница на prague.eu или Kudy z nudy (поле url).
Ссылки, вписанные вручную (manual: true), не трогаем.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..extract import page_basics

log = logging.getLogger(__name__)
FILE = Path(__file__).resolve().parents[2] / "docs" / "data" / "places.json"


def enrich(fetcher, path: Path = FILE) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for p in data.get("places", []):
        url = p.get("url") or ""
        if p.get("manual") or not any(h in url for h in ("prague.eu", "kudyznudy.cz")):
            continue
        html = fetcher.get(url)
        if not html:
            continue
        b = page_basics(html)
        for key, val in (("site", b["site"]), ("booking", b["booking"])):
            if val and p.get(key) != val:
                p[key] = val
                changed += 1
        if not p.get("image") and b["image"]:
            p["image"] = b["image"]
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("places: обновлено полей %d", changed)
    return changed
