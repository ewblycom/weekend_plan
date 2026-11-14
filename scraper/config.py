"""Настройки под вас: Прага 4 (Браник), пара, русскоязычные, не туристы, есть машина."""

# Сколько дней вперёд держать в общей ленте (вкладка «Все ближайшие»)
HORIZON_DAYS = 21

# Ticket Tailor: организаторы русскоязычных концертов/стендапа.
# Адрес вида tickettailor.com/events/<организатор>
TICKETTAILOR_ORGANIZERS = ["spotlightproduction"]

# Публичные Telegram-каналы (без @): czech_info, Pozor! (pozor_brno), The Česko (the_cesko).
# Это новостные каналы — парсер берёт из них только афишные посты с датой (czech_info убран: там только новости и реклама).
# Добавьте сюда каналы, которые читаете сами, —
# например афишу Праги или Vinegret, — когда узнаете их точные @username.
TELEGRAM_CHANNELS = ["pozor_brno", "the_cesko"]

# Туристический центр — сильно опускаем в выдаче
TOURIST_MARKERS = [
    "staroměstské náměstí", "václavské náměstí", "karlův most", "pražský hrad",
    "malostranské náměstí", "orloj", "old town", "charles bridge", "prague castle",
    "starom", "petřín",
]

# Скорее для детей — опускаем (если заголовок/категория про детей)
KIDS_MARKERS = ["pro děti", "pohádk", "dětsk", "pro nejmenší", "rodiny s dětmi", "kids", "для детей"]

# Хорошо для пары
COUPLE_MARKERS = [
    "degustac", "ochutnáv", "víno", "vína", "vinn", "wine", "pro dva", "pro 2", "pro páry",
    "rande", "workshop", "dílna", "kurz", "koncert", "jazz", "swing", "tanec", "tanč",
    "večer", "dyzajn", "design", "market", "keramik", "stand-up", "стендап", "концерт",
    "мастер-класс", "дегустац",
]

# Рядом с домом (Прага 4) — небольшой бонус, машина всё равно есть
NEAR_HOME = ["braník", "podolí", "krč", "modřany", "nusle", "michle", "lhotka",
             "kunratice", "chodov", "pankrác", "praha 4", "smíchov", "anděl", "vyšehrad"]

CATEGORY_WEIGHT = {
    "concert": 3.0, "show": 3.0, "theater": 2.8, "workshop": 3.0, "market": 2.5, "food": 2.5,
    "festival": 2.5, "exhibition": 2.0, "other": 1.5, "sport": 1.0, "history": 0.5,
    "tour": -1.0, "kids": -3.0, None: 1.0,
}

# Telegram: посты про события других городов (не Прага) отбрасываем
OTHER_CITIES = ["брно", "брне", "оломоуц", "острав", "пльзен", "либерец", "пардубиц", "карлов вар",
                "градец", "зноймо", "крумлов", "подебрад", "йиглав", "злин", "ческе-будейовиц",
                "lysá", "loket", "vildštejn"]
PRAGUE_WORDS = ["прага", "праге", "праги", "пражск", "praha", "praha 4"]


# Города, куда мы готовы поехать на вечер (билеты и афиша из Tickettailor).
# Форма слова в заголовке («в Праге», «в Вене») → название города для показа.
CITY_FORMS = {
    "прага": "Прага", "праге": "Прага", "praha": "Прага", "prague": "Прага",
    "вена": "Вена", "вене": "Вена", "wien": "Вена", "vienna": "Вена", "vídeň": "Вена",
    "мюнхен": "Мюнхен", "мюнхене": "Мюнхен", "münchen": "Мюнхен", "munchen": "Мюнхен", "munich": "Мюнхен",
    "берлин": "Берлин", "берлине": "Берлин", "berlin": "Берлин",
}
HOME_CITY = "Прага"

# Telegram: посты, которые явно не про события (поиск жилья, реклама услуг, курсы валют)
NOT_EVENT = ["аренд", "квартир", "комнат", "вакан", "страхован", "курс валют", "ищете работу"]
