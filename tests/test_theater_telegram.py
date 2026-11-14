from datetime import date

from scraper.sources import prague_eu, telegram

TODAY = date(2026, 11, 14)

THEATER_HTML = """<main>
<div><a href="/cs/akce/romeo-a-julie/">x</a>
<span>činohra</span><h2>Romeo a Julie</h2><p>23. 10. 2026—13. 11. 2026, 19:00</p>Švandovo divadlo na Smíchově</div>
<div><a href="/cs/akce/figarova-svatba/">x</a>
<span>opera</span><h2>Figarova svatba</h2><p>15. 11. 2026, 19:00</p>Stavovské divadlo</div>
<div><a href="/cs/akce/kaspar/">x</a>
<span>loutkové divadlo</span><h2>Kašpárek v pekle</h2><p>14. 11. 2026, 14:00</p>Divadlo říše loutek</div>
</main>"""

DIGEST = """Чем заняться на выходных в Праге и Брно
🐊БРНО
▪️Вечеринка нулевых
Возвращаем тебя в 2000-е!
📅14.11
🏰ПРАГА
▪️ČokoFest
Шоколадный фестиваль.
📅13-15.11
▪️Karlínská husa
Гусь в Карлине.
📅15.11
▪️Старое
📅1.11"""


def test_theater_categories():
    evs = prague_eu.parse_listing(THEATER_HTML, "show")
    cats = {e.title: e.category for e in evs}
    assert cats == {"Romeo a Julie": "theater", "Figarova svatba": "theater", "Kašpárek v pekle": "kids"}


def test_pozor_digest_prague_only():
    evs = telegram.parse_pozor_digest(DIGEST, "pozor_brno", "u", TODAY)
    assert [e.title for e in evs] == ["ČokoFest", "Karlínská husa"]
    assert (evs[0].start, evs[0].end) == (date(2026, 11, 13), date(2026, 11, 15))


def test_cesko_afisha_prague_only():
    text = "Афиша:\n🍫 В Праге пройдет фестиваль шоколада ČokoFest;\n🎉 В Остраве будет рынок;\nАкции:\n"
    evs = telegram.parse_cesko_afisha(text, "the_cesko", "u", TODAY)
    assert len(evs) == 1 and evs[0].date_uncertain


def test_brno_post_skipped():
    html = """<div class="tgme_widget_message"><div class="tgme_widget_message_text">Концерт в Брно 20 ноября, билеты</div>
    <a class="tgme_widget_message_date" href="https://t.me/x/1"><time datetime="2026-11-13T10:00:00+00:00"></time></a></div>"""
    assert telegram.parse_channel(html, "pozor_brno", TODAY) == []
