"""Аккуратная загрузка страниц: свой User-Agent, robots.txt, пауза между запросами, повторы."""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

log = logging.getLogger(__name__)

USER_AGENT = "WeekendPragueBot/0.1 (personal, non-commercial; 1 run per day)"
DELAY_SECONDS = 1.5


class Fetcher:
    def __init__(self, delay: float = DELAY_SECONDS, timeout: int = 25):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "cs,ru;q=0.8,en;q=0.6",
        })
        self.delay = delay
        self.timeout = timeout
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.session.get(f"https://{host}/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.ok else [])
                self._robots[host] = rp
            except requests.RequestException:
                self._robots[host] = None  # robots недоступен — не блокируем
        rp = self._robots[host]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, retries: int = 2) -> str | None:
        if not self._allowed(url):
            log.warning("robots.txt запрещает %s — пропускаю", url)
            return None
        host = urlparse(url).netloc
        wait = self.delay - (time.monotonic() - self._last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=self.timeout)
                self._last_hit[host] = time.monotonic()
                if r.status_code == 200:
                    # requests по умолчанию ставит latin-1, если сервер не указал кодировку
                    if not r.encoding or r.encoding.lower() == "iso-8859-1":
                        r.encoding = r.apparent_encoding
                    return r.text
                log.warning("%s → HTTP %s", url, r.status_code)
                if r.status_code in (403, 404, 410):
                    return None
            except requests.RequestException as e:
                log.warning("%s → %s (попытка %d)", url, e, attempt + 1)
            time.sleep(2 * (attempt + 1))
        return None
