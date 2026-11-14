from datetime import date
from pathlib import Path

from scraper.dates import parse_range, upcoming_weekend
from scraper.models import Event
from scraper.run import build
from scraper.sources import kudyznudy, prague_eu, telegram, tickettailor

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)  # суббота


def read(name):
    return (FX / name).read_text(encoding="utf-8")


def test_dates():
    assert parse_range("28. 7. 2026—20. 11. 2026, 8:00—19:00") == (date(2026, 7, 28), date(2026, 11, 20), "8:00—19:00")
    assert parse_range("21. 11. 2026, 11:00—17:00") == (date(2026, 11, 21), date(2026, 11, 21), "11:00—17:00")
    assert parse_range("v sobotu 14. listopadu 2026")[0] == date(2026, 11, 14)
    assert parse_range("Wed 21 Oct 2026 20:00 - 22:30")[:2] == (date(2026, 10, 21), date(2026, 10, 21))
    assert parse_range("21 ноября, 19:00", TODAY)[0] == date(2026, 11, 21)
    assert parse_range("5. ledna", date(2026, 12, 20))[0] == date(2027, 1, 5)


def test_weekend():
    assert upcoming_weekend(date(2026, 11, 14)) == (date(2026, 11, 13), date(2026, 11, 15))
    assert upcoming_weekend(date(2026, 11, 16)) == (date(2026, 11, 20), date(2026, 11, 22))


def test_prague_eu_listing():
    evs = prague_eu.parse_listing(read("prague_eu_trhy.html"), "market")
    titles = [e.title for e in evs]
    assert titles == ["Dyzajn market Zima", "Zimní apetit piknik",
                      "Vánoční trhy Staroměstské náměstí", "Trhy Anděl"]
    dm = evs[0]
    assert dm.url == "https://prague.eu/cs/akce/dyzajn-market-zima/"
    assert (dm.start, dm.end, dm.time) == (date(2026, 12, 12), date(2026, 12, 13), "10:00—18:00")
    assert dm.venue == "Holešovická tržnice"
    assert evs[1].venue == "Národní zemědělské muzeum"


def test_kudyznudy_detail():
    ev = kudyznudy.parse_detail(read("kudyznudy_detail.html"), "https://www.kudyznudy.cz/akce/x")
    assert ev.title == "Letenská husa a košt svatomartinského vína 2026"
    assert ev.start == date(2026, 11, 14)
    assert ev.category == "food"
    assert ev.venue == "Praha"
    assert not ev.date_uncertain


def test_kudyznudy_listing_links():
    html = '<a href="/akce/foo">a</a><a href="https://www.kudyznudy.cz/akce/bar#x">b</a><a href="/aktivity/baz">c</a>'
    assert kudyznudy.parse_listing_links(html) == [
        "https://www.kudyznudy.cz/akce/foo", "https://www.kudyznudy.cz/akce/bar"]


def test_tickettailor_detail():
    ev = tickettailor.parse_detail(read("tickettailor_detail.html"), "https://www.tickettailor.com/events/spotlightproduction/1")
    assert ev.lang == "ru"
    assert ev.start == date(2026, 5, 8)
    assert ev.venue == "Divadlo Na Maninách, 170 00"
    assert ev.category == "show"


def test_telegram():
    evs = telegram.parse_channel(read("telegram_channel.html"), "czech_info", TODAY)
    assert len(evs) == 1  # новости без афишных слов и старые посты отброшены
    assert evs[0].start == date(2026, 11, 21)
    assert evs[0].url == "https://t.me/czech_info/9002"


def test_scoring_and_build():
    evs = prague_eu.parse_listing(read("prague_eu_trhy.html"), "market")
    evs.append(Event(source="tickettailor", url="u", title="Стендап", start=date(2026, 11, 21),
                     category="show", lang="ru"))
    data = build(evs, TODAY, {})
    titles = [e["title"] for e in data["events"]]
    assert titles[0] == "Стендап"                                  # русский + стендап — наверх
    assert titles[-1] == "Vánoční trhy Staroměstské náměstí"       # туристический центр — вниз
    assert data["weekend"] == {"from": "2026-11-13", "to": "2026-11-15"}
