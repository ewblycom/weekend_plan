from scraper.pricing import detect_price


def test_free():
    assert detect_price("Vstup zdarma, od 10:00") == (True, None)
    assert detect_price("Фестиваль настольных игр, вход бесплатный.") == (True, None)


def test_price():
    assert detect_price("Vstupné od 250 Kč, děti 120 Kč") == (None, 120)
    assert detect_price("Билеты 1 200 Kč") == (None, 1200)
    assert detect_price("Dospělí 300 CZK, zdarma pro děti do 6 let") == (None, 300)


def test_unknown():
    assert detect_price("Koncert v 19:00") == (None, None)
    assert detect_price(None) == (None, None)
