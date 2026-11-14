"""Единый формат события, в который приводятся все источники."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class Event:
    source: str                 # prague.eu / kudyznudy / tickettailor / telegram:<channel>
    url: str
    title: str
    start: date | None = None
    end: date | None = None     # для многодневных (ярмарки, выставки)
    time: str | None = None     # "19:00" или "10:00—18:00"
    venue: str | None = None
    category: str | None = None  # нормализованная: market/exhibition/concert/workshop/food/festival/show/other
    description: str | None = None
    image: str | None = None
    lang: str = "cs"            # cs / ru / en
    free: bool | None = None
    price_from: int | None = None   # CZK, «от»; None — цена неизвестна
    date_uncertain: bool = False
    score: float = 0.0
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Ключ для дедупликации: одно и то же событие из разных источников."""
        base = f"{normalize(self.title)}|{self.start or ''}"
        return hashlib.sha1(base.encode()).hexdigest()[:12]

    def to_json(self) -> dict:
        d = asdict(self)
        d["id"] = self.key
        d["start"] = self.start.isoformat() if self.start else None
        d["end"] = self.end.isoformat() if self.end else None
        return d


def normalize(text: str) -> str:
    """Без диакритики, регистра и пунктуации: 'Vánoční trhy!' -> 'vanocni trhy'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")


def detect_lang(*texts: str | None) -> str:
    joined = " ".join(t for t in texts if t)
    if len(CYRILLIC.findall(joined)) > 10:
        return "ru"
    return "cs"
