"""Цена и «бесплатно» из текста страницы/поста (cs/ru/en)."""
from __future__ import annotations

import re

FREE = re.compile(
    r"vstup\s+zdarma|vstupné\s*:?\s*zdarma|vstup\s+volný|zdarma|bez\s+vstupného|"
    r"вход\s+свободный|вход\s+бесплатн|бесплатн|free\s+(?:entry|admission)|admission\s+free",
    re.I,
)
# «od 250 Kč», «250 CZK», «350 крон», «1 200 Kč»
PRICE = re.compile(r"(\d{1,3}(?:[\s ]\d{3})+|\d{2,5})\s*(?:,-\s*)?(?:Kč|CZK|крон\w*|kc)\b", re.I)


def detect_price(text: str | None) -> tuple[bool | None, int | None]:
    """→ (free, цена «от» в CZK). Бесплатным считаем, только если нет явных платных сумм."""
    if not text:
        return None, None
    amounts = []
    for m in PRICE.finditer(text):
        v = int(re.sub(r"\D", "", m.group(1)))
        if 20 <= v <= 20000:
            amounts.append(v)
    price = min(amounts) if amounts else None
    free = True if (FREE.search(text) and price is None) else None
    if free is None and price is None and re.search(r"zdarma", text, re.I):
        free = True
    return free, price
