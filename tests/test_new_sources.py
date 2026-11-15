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


def test_food_venues_and_items(tmp_path, monkeypatch):
    from datetime import date
    from scraper.sources import food
    assert food.venue_key("Jatka78, Praha 7") == "jatka78" and food.venue_key("Praha") is None
    evs = [{"venue": "Jatka78, Praha 7", "start": "2026-11-18"}, {"venue": "Jatka78", "start": "2026-11-19"},
           {"venue": "Rock Cafe — Národní", "start": "2026-11-16"}, {"venue": "Wiener Konzerthaus", "city": "Вена"},
           {"venue": "Daleko", "start": "2027-03-01"}]
    assert food.pick_venues(evs, date(2026, 11, 15)) == [("jatka78", "Jatka78"), ("rock cafe", "Rock Cafe")]
    it = {"title": "Lokál", "totalScore": 4.5, "reviewsCount": 900, "categoryName": "Restaurace", "address": "x", "location": {"lat": 50.1, "lng": 14.4}}
    assert food.parse_item(it)["rating"] == 4.5 and food.parse_item({**it, "permanentlyClosed": True}) is None
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert food.collect(evs, date(2026, 11, 15)) == 0       # без токена тихо пропускаем


def test_food_walking_radius_and_ranking(monkeypatch):
    from scraper.sources import food
    o = (50.0755, 14.4378)                       # Вацлавак
    mk = lambda t, lat, lng, r=4.5, n=300: {"title": t, "totalScore": r, "reviewsCount": n, "categoryName": "Restaurace", "location": {"lat": lat, "lng": lng}}
    near = food.parse_item(mk("Близко", 50.0775, 14.4378), o)         # ~220 м
    assert near["min"] <= 4 and near["m"] < 300
    assert food.parse_item(mk("Далеко", 50.0900, 14.4378), o) is None   # ~1,6 км — больше 10 минут
    assert food.parse_item({"title": "Без координат"}, o) is None
    assert food.walk_min(600) == 10 and food.walk_min(700) == 12
    items = [mk("A", 50.0760, 14.4378, 4.9, 25), mk("B", 50.0765, 14.4378, 4.6, 900), mk("C", 50.0770, 14.4378, 3.5, 900),
             mk("D", 50.0770, 14.4378, 4.8, 5), mk("E", 50.0900, 14.4378, 5.0, 900)]
    monkeypatch.setattr(food, "_run", lambda token, payload: items)
    got = [p["name"] for p in food.fetch_nearby("t", o)]
    assert got == ["B", "A"]                                           # C — низкая оценка, D — мало отзывов, E — далеко; B выше A за счёт числа отзывов
    assert food.in_prague(50.07, 14.43) and not food.in_prague(48.2, 16.3)


def test_food_only_restaurants_and_czk():
    from scraper.sources import food
    r = lambda **k: {"name": "X", "type": "Česká restaurace", "rating": 4.6, "reviews": 300, "address": "Národní 1, Praha", **k}
    assert food.good(r())
    for bad in (r(type="Kavárna"), r(type="Rychlé občerstvení"), r(type="Hotel"), r(type="Outletové centrum"),
                r(name="McDonald's"), r(name="KFC Anděl", type="Restaurace"), r(address="Westfield Chodov, Roztylská 2321"),
                r(**{"in": "Palladium"}), r(name="Coffee Fellows", type="Restaurace")):
        assert not food.good(bad), bad
    assert food.czk_price("200–400\xa0Kč") == "200–400 Kč" and food.czk_price("2\xa0826\xa0HNL") is None and food.czk_price("€10–20") is None



def test_food_details_fields():
    from scraper.sources import food
    it = {"title": "U X", "totalScore": 4.6, "reviewsCount": 300, "categoryName": "Česká restaurace", "imageUrl": "https://lh3/x.jpg",
          "description": " Domácí kuchyně ", "menu": "https://ux.cz/menu", "location": {"lat": 50.08, "lng": 14.42},
          "reviewsTags": [{"title": "svíčková", "count": 40}, {"title": "obsluha", "count": 30}, {"title": "guláš", "count": 20}]}
    p = food.parse_item(it)
    assert p["img"] == "https://lh3/x.jpg" and p["desc"] == "Domácí kuchyně" and p["menu"].endswith("/menu") and p["tags"] == ["svíčková", "guláš"]
