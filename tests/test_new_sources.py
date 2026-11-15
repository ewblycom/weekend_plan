from datetime import date

from scraper.sources import goout, luma, vinegret

TODAY = date(2026, 11, 14)


def test_goout_listing_and_detail():
    lst = """<a href="/cs/health+vowws/szykjiy/">x</a><a href="/cs/listky/health+vowws/ywvkb/">b</a>
    <a href="/cs/archa+/vzljb/">venue</a><a href="https://goout.net/cs/jimmy-carr-laughs-funny/szhswky/">y</a>"""
    assert goout.parse_listing(lst) == ["https://goout.net/cs/health+vowws/szykjiy/",
                                        "https://goout.net/cs/jimmy-carr-laughs-funny/szhswky/"]
    page = """<html><head><meta property="og:title" content="Health + VOWWS - zítra 19:00 - ARCHA+ - GoOut">
    <script type="application/ld+json">{"@type":"MusicEvent","name":"Health + VOWWS","startDate":"2026-11-15T19:00:00+01:00",
    "location":{"@type":"Place","name":"ARCHA+","address":{"streetAddress":"Na Poříčí 1047/26","addressLocality":"Praha"}}}</script></head>
    <body><main><a href="/cs/listky/health+vowws/ywvkb/">Koupit</a><a href="/cs/praha/koncerty/leznyvlkkzf/?genres=rock">Rock</a>
    <p>Místo</p><p>ARCHA+</p><p>Vstupné</p><p>960 Kč</p><a href="https://archa-plus.cz/cz/">www.archa-plus.cz</a></main></body></html>"""
    ev = goout.parse_detail(page, "https://goout.net/cs/health+vowws/szykjiy/")
    assert ev.title == "Health + VOWWS" and ev.start == date(2026, 11, 15) and ev.time == "19:00"
    assert ev.category == "concert" and ev.price_from == 960
    assert ev.booking.endswith("/listky/health+vowws/ywvkb/") and ev.link == "https://archa-plus.cz/cz/"
    assert goout.parse_detail("<title>Waiting Room - GoOut</title> virtuální frontu", "u") is None


def test_luma_filters_business_and_parses_price():
    assert luma.parse_listing('<a href="/0n4nt21i">a</a><a href="/discover">d</a><a href="https://luma.com/carlos.sarduy">c</a>') == \
        ["https://luma.com/0n4nt21i", "https://luma.com/carlos.sarduy"]
    page = """<script type="application/ld+json">{"@type":"Event","name":"Unwind & Unwine // Yoga + Social Evening",
    "startDate":"2026-11-19T18:30:00.000+01:00","location":{"name":"Coffee Room Celetna"},
    "offers":{"price":350,"priceCurrency":"CZK"}}</script>"""
    ev = luma.parse_detail(page, "https://luma.com/x")
    assert ev.category == "sport" and ev.price_from == 350 and ev.time == "18:30" and ev.lang == "en"
    biz = page.replace("Unwind & Unwine // Yoga + Social Evening", "AI Makers / 02")
    assert luma.parse_detail(biz, "https://luma.com/y") is None


def test_vinegret_afisha_article():
    page = """<html><head><meta property="og:title" content="В субботу в Праге можно будет бесплатно посетить космическое агентство ЕС">
    <meta property="og:description" content="В субботу, 14 ноября, Агентство EUSPA проведет день открытых дверей в пражском районе Голешовице.">
    <meta property="article:section" content="Афиша"><meta property="article:modified_time" content="2026-11-13"></head>
    <body><main><p>🕘 Время проведения мероприятия: с 09:00 до 18:00;</p><p>📍Адрес агентства: Janovského 438/2, Praha 7 (посмотреть на карте)</p>
    <p>Вход бесплатный.</p></main></body></html>"""
    ev = vinegret.parse_article(page, "https://www.vinegret.cz/694616/x", TODAY)
    assert ev.start == date(2026, 11, 14) and ev.time == "09:00—18:00"
    assert ev.venue == "Janovského 438/2, Praha 7" and ev.lang == "ru"
    news = page.replace('content="Афиша"', 'content="Новости Праги"')
    assert vinegret.parse_article(news, "u", TODAY) is None


def test_place_hours_from_own_site():
    from scraper.sources.places import opening_hours
    html = "<html><body><h2>Otevírací doba</h2><p>Po–Ne 10:00–22:00</p></body></html>"
    assert opening_hours(html) == "10:00–22:00"
    assert opening_hours("<html><body>Provozní doba: 9.30 - 21.00</body></html>") == "09:30–21:00"


def test_place_site_discovery():
    from scraper.sources.places import name_tokens, pick_site, search_results
    assert name_tokens("Absolutní Bowling") == ["absolutni"]
    assert name_tokens("Mercuria Laser Game Braník") == ["mercuria", "branik"]
    html = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.firmy.cz%2Fdetail%2F1">f</a>'
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.absolutnibowling.cz%2Fcenik">o</a>')
    links = search_results(html)
    assert links[1] == "https://www.absolutnibowling.cz/cenik"
    assert pick_site("Absolutní Bowling", links) == "https://www.absolutnibowling.cz/"
    assert pick_site("Absolutní Bowling", ["https://www.facebook.com/absolutnibowling", "https://other.cz/"]) is None


def test_profile_quota_and_loading(tmp_path):
    from scraper import profile
    f = tmp_path / "p.json"
    f.write_text('{"n": 40, "cats": {"theater": 0.8, "exhibition": -0.3}}')
    assert profile.load_file(f) == {"theater": 0.8, "exhibition": -0.3}
    f.write_text('{"n": 5, "cats": {"theater": 0.8}}')
    assert profile.load_file(f) == {}            # мало решений — не доверяем
    assert profile.load_file(tmp_path / "none.json") == {}
    assert profile.quota(40, 0.8) == 72 and profile.quota(40, -0.9) == 20 and profile.quota(10, -0.5) == 10


def test_profile_affinities_from_signals():
    from datetime import datetime, timezone
    from scraper import profile
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    mk = lambda a, c, d="2026-11-14T10:00:00Z": {"action": a, "category": c, "created_at": d}
    rows = [mk("like", "theater") for _ in range(8)] + [mk("skip", "exhibition") for _ in range(6)] + [{"action": "like", "place_kind": "sauna", "created_at": "2026-11-14T10:00:00Z"}]
    aff = profile.affinities(rows, now)
    assert aff["theater"] > 0.5 and aff["exhibition"] < 0 and "kind:sauna" in aff
    old = [mk("like", "theater", "2026-05-01T00:00:00Z") for _ in range(8)]
    assert profile.affinities(old, now)["theater"] < aff["theater"]          # старые сигналы слабее
    assert profile.affinities([mk("like", "show"), mk("unlike", "show")], now)["show"] < 0.05   # отменённый лайк не считается
