"""Интересы человека → настройка парсера.

Приложение тихо пишет каждый лайк/«мимо» в таблицу weekend_signals (Supabase). Перед сбором парсер читает сигналы
за последние 60 дней и считает «симпатию» к каждой категории (свежие сигналы весят больше):
  — берёт больше событий из любимых категорий (квота) и добавляет им бонус к score;
  — нелюбимых берёт меньше.
Читает сводку (функция weekend_profile: дни × категории × действия, без названий) публичным ключом — отдельных секретов не нужно.
При ошибке или малом числе данных парсер работает как раньше. Запасной вариант — файл data/profile.json {"n": 40, "cats": {"theater": 0.7}}.
"""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import requests

log = logging.getLogger(__name__)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://rdibhhnbqvrgujfxranx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_1190WjPfc4t11x7o_t6Gxw_llCobWE2")   # публичный ключ: только вставка и сводка
FILE = Path(__file__).resolve().parents[1] / "data" / "profile.json"
MIN_DECISIONS = 15      # на меньшем числе решений профиль ещё шумный
WINDOW_DAYS = 60
HALF_LIFE_DAYS = 60
SKIP_WEIGHT = 0.4       # «мимо» — слабый сигнал: часто это «не в эту дату», а не «не моё»
PRIOR = 3               # сглаживание: 1–2 лайка не делают из категории «любимую»


def affinities(rows: list[dict], now: datetime | None = None) -> dict[str, float]:
    """Строки сигналов → {категория: симпатия от -0.4 до +1}. Сигналы по местам считаются по их типу (kind)."""
    now = now or datetime.now(timezone.utc)
    like: dict[str, float] = {}
    skip: dict[str, float] = {}
    for r in rows:
        key = r.get("category") or (("kind:" + r["place_kind"]) if r.get("place_kind") else None)
        if not key:
            continue
        try:
            ts = datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00"))
            age = (now - (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc))).total_seconds() / 86400
        except (KeyError, ValueError):
            continue
        w = 0.5 ** (max(0.0, age) / HALF_LIFE_DAYS) * float(r.get("n", 1))
        a = r.get("action")
        if a == "like":
            like[key] = like.get(key, 0) + w
        elif a == "skip":
            skip[key] = skip.get(key, 0) + w
        elif a == "unlike":           # лайк отменили: он превращается в слабое «мимо»
            like[key] = max(0.0, like.get(key, 0) - w)
            skip[key] = skip.get(key, 0) + w
        elif a == "unskip":
            skip[key] = max(0.0, skip.get(key, 0) - w)
    out = {}
    for k in set(like) | set(skip):
        l, s = like.get(k, 0.0), skip.get(k, 0.0)
        out[k] = (l - SKIP_WEIGHT * s) / (l + s + PRIOR)
    return out


def fetch_rows(url: str = SUPABASE_URL, key: str = SUPABASE_KEY, days: int = WINDOW_DAYS) -> list[dict]:
    r = requests.post(f"{url.rstrip('/')}/rest/v1/rpc/weekend_profile", json={"days": days}, timeout=30,
                      headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r.raise_for_status()
    return [{"created_at": x["day"] + "T12:00:00+00:00", "action": x["action"], "category": x["category"],
             "place_kind": x["place_kind"], "n": x["n"]} for x in r.json()]


def load_file(path: Path = FILE) -> dict[str, float]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if d.get("n", 0) < MIN_DECISIONS:
        return {}
    return {k: float(v) for k, v in (d.get("cats") or {}).items()}


@lru_cache(maxsize=1)
def load() -> dict[str, float]:
    try:
        rows = fetch_rows()
    except Exception as e:  # noqa: BLE001 — профиль необязателен, сбор должен идти дальше
        log.warning("profile: не удалось прочитать сигналы (%s) — пробую файл", e)
        return load_file()
    n = sum(r["n"] for r in rows if r["action"] in ("like", "skip"))
    if n < MIN_DECISIONS:
        log.info("profile: решений %d < %d — профиль не используем", n, MIN_DECISIONS)
        return {}
    aff = affinities(rows)
    log.info("profile: решений %d, симпатии: %s", n, {k: round(v, 2) for k, v in sorted(aff.items(), key=lambda x: -x[1])})
    return aff


def quota(base: int, aff: float) -> int:
    """Сколько событий категории брать: любимых до ×2, нелюбимых до ×0.5 (но не меньше 10)."""
    return max(10, round(base * (1 + max(-0.5, min(1.0, aff)))))


def bonus(aff: float) -> float:
    return 2.5 * max(-0.4, min(1.0, aff))
