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


def test_brno_post_skipped():
    html = """<div class="tgme_widget_message"><div class="tgme_widget_message_text">Концерт в Брно 20 ноября, билеты</div>
    <a class="tgme_widget_message_date" href="https://t.me/x/1"><time datetime="2026-11-13T10:00:00+00:00"></time></a></div>"""
    assert telegram.parse_channel(html, "pozor_brno", TODAY) == []


# ---------- фильтры: города, дубли, анонсы Telegram ----------
from scraper.sources import tickettailor


def test_ticket_city_filter_and_title():
    assert tickettailor.clean_title("Купить билеты – Дмитрий Романов в Праге. Стендап – Rock Cafe") == "Дмитрий Романов в Праге. Стендап"
    assert tickettailor.detect_city("Дмитрий Романов в Праге. Стендап", None) == ("Прага", True)
    assert tickettailor.detect_city("Stand Up Astana в Вене", None) == ("Вена", True)
    assert tickettailor.detect_city("Анна Виленская в Мюнхене. Лекция", None) == ("Мюнхен", True)
    assert tickettailor.detect_city("Концерт в Берлине", None) == ("Берлин", True)
    assert tickettailor.detect_city("Стендап в Амстердаме", None) [1] is False
    assert tickettailor.detect_city("Стендап Астана в Лиссабоне", None)[1] is False
    # без города в заголовке — по адресу/индексу
    assert tickettailor.detect_city("Концерт", "Futurum Music Bar, 150 00") == ("Прага", True)
    assert tickettailor.detect_city("Концерт", "Isarphilharmonie, 81667") == ("Мюнхен", True)
    assert tickettailor.detect_city("Симфонический день", "Какой-то зал") == (None, False)


def test_telegram_structured_ad_post():
    html = """<div class="tgme_widget_message"><div class="tgme_widget_message_text">Пора доставать Thrasher: 2к17 возвращается<br/><br/>📅 Дата: 21 ноября в 21:00<br/>📍 Локация: клуб в центре Праги - The Pitch<br/>💸 Стоимость: бесплатно<br/>🎶 Хиты СНГ, вечеринка</div>
    <a class="tgme_widget_message_date" href="https://t.me/pozor_brno/1"><time datetime="2026-11-12T10:00:00+00:00"></time></a></div>"""
    [ev] = telegram.parse_channel(html, "pozor_brno", TODAY)
    assert ev.start == date(2026, 11, 21) and ev.time == "21:00"
    assert ev.venue == "The Pitch" and ev.free is True and ev.category == "concert"


def test_telegram_news_and_housing_skipped():
    def post(text):
        return f"""<div class="tgme_widget_message"><div class="tgme_widget_message_text">{text}</div>
        <a class="tgme_widget_message_date" href="https://t.me/x/2"><time datetime="2026-11-12T10:00:00+00:00"></time></a></div>"""
    assert telegram.parse_channel(post("Премьер встретился с президентом 13.11 в Дублине"), "czech_info", TODAY) == []
    assert telegram.parse_channel(post("Ищете комнату в Праге? Концерт не нужен, билеты на просмотр 20 ноября"), "pozor_brno", TODAY) == []


def test_cesko_links_and_event_page():
    html = """<div class="tgme_widget_message"><div class="tgme_widget_message_text">Афиша:<br/>
    В Праге пройдет <a href="https://the-cesko.cz/events/abc123">фестиваль шоколада</a>;<br/>
    <a href="https://the-cesko.cz/life/zzz">Не афиша</a></div>
    <a class="tgme_widget_message_date" href="https://t.me/the_cesko/3"><time datetime="2026-11-13T10:00:00+00:00"></time></a></div>"""
    assert telegram.cesko_links(html, TODAY) == {"https://the-cesko.cz/events/abc123": "фестиваль шоколада"}
    page = """<html><head><meta property="og:title" content="В пражском ТЦ Westfield Chodov появится зона Голодных игр"></head><body>
    <h1>В пражском ТЦ Westfield Chodov появится зона Голодных игр</h1><p>Текст.</p>
    <p><strong>Дата:</strong> 18-22 ноября<br/><strong>Время:</strong> 9:00-21:00<br/>
    <strong>Место:</strong> Westfield Chodov, первый этаж возле магазина CROPP<br/><strong>Вход:</strong> бесплатно</p>
    <p>Скопировать ссылку</p></body></html>"""
    ev = telegram.parse_cesko_event(page, "https://the-cesko.cz/events/abc123", TODAY)
    assert (ev.start, ev.end) == (date(2026, 11, 18), date(2026, 11, 22))
    assert ev.time == "9:00—21:00" and ev.venue == "Westfield Chodov" and ev.free is True
    # событие в Остраве отбрасывается
    assert telegram.parse_cesko_event(page.replace("Westfield Chodov", "Ostrava Arena").replace("пражском ТЦ", "ТЦ в Остраве"), "u", TODAY) is None
