"""Общие извлекатели со страницы события: Open Graph, JSON-LD (schema.org/Event), видимый текст."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

TITLE_SUFFIXES = re.compile(r"\s*[|–-]\s*(Kudy z nudy|Prague City Tourism|Tickets.*|Ticket Tailor.*)$", re.I)


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return tag.get("content").strip() if tag and tag.get("content") else None


def clean_title(title: str | None) -> str | None:
    return TITLE_SUFFIXES.sub("", title).strip() if title else None


def jsonld_events(soup: BeautifulSoup) -> list[dict]:
    """Все объекты типа *Event из <script type="application/ld+json">."""
    found: list[dict] = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and x.endswith("Event") for x in types):
                found.append(node)
            for key in ("@graph", "itemListElement", "item", "subEvent"):
                if key in node:
                    walk(node[key])

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return found


def jsonld_venue(ev: dict) -> str | None:
    loc = ev.get("location")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        name = loc.get("name")
        addr = loc.get("address")
        if isinstance(addr, dict):
            addr = ", ".join(filter(None, [addr.get("streetAddress"), addr.get("addressLocality")]))
        return ", ".join(filter(None, [name, addr if isinstance(addr, str) else None])) or None
    return loc if isinstance(loc, str) else None


def visible_text(soup: BeautifulSoup, limit: int = 6000) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text[:limit]


SKIP_HOSTS = ("kudyznudy.cz", "prague.eu", "praguecitytourism", "czechtourism", "visitczechia", "praha.eu",
              "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com", "linkedin.com",
              "pinterest.", "google.", "mapy.cz", "apple.com", "sharethis", "cdn.", "storage.googleapis.com", "t.me",
              "telegram", "seznam.cz", "vinegret.cz", "wa.me", "mailto:", "tel:")
NOT_SITE = ("goout.net", "luma.com", "lu.ma", "ticketportal", "ticketmaster", "eventim")   # годятся только как «билеты»
BOOKING_WORDS = re.compile(
    r"rezerv|booking|reservio|vstupenk|v?stupenky|l[ií]stk|ticket|goout|smsticket|eventim|colosseum|"
    r"predprodej|předprodej|luma\.com|eventbrite|kupvstupenku|/koncert/|/program|/event", re.I)


def external_links(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """(сайт, бронь/билеты) — первые внешние ссылки страницы, без соцсетей и самого агрегатора."""
    site = booking = None
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http") or any(h in href.lower() for h in SKIP_HOSTS):
            continue
        if re.search(r"\.(jpe?g|png|webp|pdf)(\?|$)", href, re.I):
            continue
        label = a.get_text(" ", strip=True)
        if booking is None and (BOOKING_WORDS.search(href) or BOOKING_WORDS.search(label)):
            booking = href
        elif site is None and not any(h in href.lower() for h in NOT_SITE):
            site = href
        if site and booking:
            break
    return site, booking


def page_basics(html: str) -> dict:
    """Минимум, который есть почти на любой странице события."""
    soup = soup_of(html)
    events = jsonld_events(soup)
    data = {
        "title": clean_title(meta(soup, "og:title") or (soup.title.string if soup.title else None)),
        "description": meta(soup, "og:description") or meta(soup, "description"),
        "image": meta(soup, "og:image"),
        "jsonld": events[0] if events else None,
    }
    data["text"] = visible_text(soup)          # убирает шапку/подвал — ниже ссылки только из содержимого
    data["site"], data["booking"] = external_links(soup)
    return data
