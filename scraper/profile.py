"""Интересы человека → настройка парсера.

Приложение считает вкус на устройстве. Кнопка «Профиль для парсера» копирует JSON вида
{"n": 40, "cats": {"theater": 0.7, "exhibition": -0.2}}; его кладут в data/profile.json.
Дальше парсер: (1) берёт больше событий из любимых категорий, (2) даёт им бонус к score.
Без файла всё работает как раньше.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "data" / "profile.json"
MIN_DECISIONS = 15   # на меньшем числе решений профиль ещё шумный


def load(path: Path = FILE) -> dict[str, float]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if d.get("n", 0) < MIN_DECISIONS:
        return {}
    return {k: float(v) for k, v in (d.get("cats") or {}).items()}


def quota(base: int, aff: float) -> int:
    """Сколько событий категории брать: любимых до ×2, нелюбимых до ×0.5 (но не меньше 10)."""
    return max(10, round(base * (1 + max(-0.5, min(1.0, aff)))))


def bonus(aff: float) -> float:
    return 2.5 * max(-0.4, min(1.0, aff))
