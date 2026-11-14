// Настройки приложения. Ключ Google Places (New) — публичный по природе браузерных ключей,
// поэтому ОБЯЗАТЕЛЬНО ограничьте его по HTTP-referrer адресом вашего сайта и поставьте дневную квоту
// (см. README, раздел «Google Places»). Пока ключ пустой, вместо рейтингов будет ссылка на Google Maps.
window.APP_CONFIG = {
  GOOGLE_PLACES_KEY: "",
  HOME: "Braník, Praha 4",
  WALK_RADIUS_M: 1200,       // ~15 минут пешком
  MIN_RATING: 4.3,
  MIN_REVIEWS: 100,
  DAILY_REQUEST_CAP: 60,     // страховка в приложении: 2 запроса + до 8 фото на один выбор ≈ 10 единиц
};
