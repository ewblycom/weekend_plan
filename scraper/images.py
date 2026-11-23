"""Картинки из Telegram: скачиваем к себе и отдаём с сайта приложения.

Фото из постов лежат на cdn*.telesco.pe — оно не грузится в мини-приложении (hotlink/реферер/прокси картинок),
поэтому у телеграм-событий вместо фото была пустая заглушка. Локальная копия лежит в docs/data/img/ и не зависит
ни от Telegram, ни от внешнего прокси. Неиспользуемые файлы удаляются, чтобы репозиторий не рос.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import requests

log = logging.getLogger(__name__)

IMG_DIR = Path(__file__).resolve().parent.parent / "docs" / "data" / "img"
REL = "data/img"
REMOTE = re.compile(r"^https?://[^/]*(?:telesco\.pe|telegram-cdn\.org|cdn\.telegram\.org)/", re.I)
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 2_500_000


def local_name(url: str, ctype: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:14] + EXT.get(ctype.split(";")[0].strip().lower(), ".jpg")


def localize(events: list[dict], session: requests.Session | None = None, out_dir: Path = IMG_DIR) -> int:
    """Заменяет удалённые telegram-картинки у событий на docs/data/img/<hash>.<ext>. → число скачанных."""
    session = session or requests.Session()
    out_dir.mkdir(parents=True, exist_ok=True)
    have = {p.stem: p for p in out_dir.iterdir() if p.is_file()}
    used: set[str] = set()
    new = 0
    for e in events:
        url = e.get("image")
        if not url:
            continue
        if url.startswith(REL):
            used.add(Path(url).name)
            continue
        if not REMOTE.match(url):
            continue
        stem = hashlib.sha1(url.encode()).hexdigest()[:14]
        if stem in have:
            e["image"] = f"{REL}/{have[stem].name}"
            used.add(have[stem].name)
            continue
        try:
            r = session.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (compatible; WeekendPragueBot/0.1)"})
            ctype = r.headers.get("content-type", "")
            if r.status_code != 200 or not ctype.startswith("image/") or not r.content or len(r.content) > MAX_BYTES:
                log.warning("img: %s → HTTP %s %s %d байт — оставляю ссылку", url[:70], r.status_code, ctype, len(r.content or b""))
                continue
        except requests.RequestException as ex:
            log.warning("img: %s → %s", url[:70], ex)
            continue
        name = local_name(url, ctype)
        (out_dir / name).write_bytes(r.content)
        e["image"] = f"{REL}/{name}"
        used.add(name)
        new += 1
    for p in out_dir.iterdir():                      # чистим то, на что больше никто не ссылается
        if p.is_file() and p.name not in used and p.name != ".gitkeep":
            p.unlink()
    return new
