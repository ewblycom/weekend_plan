// Рестораны рядом с местом события — Google Places API (New), запросы идут из браузера
// в момент, когда вы нажимаете «Иду». Результаты НЕ сохраняются на сервере (условия Google
// ограничивают хранение данных); в браузере держим только на время сессии.
(function () {
  const C = window.APP_CONFIG || {};
  const API = "https://places.googleapis.com/v1";
  const PRICE = { PRICE_LEVEL_FREE: 0, PRICE_LEVEL_INEXPENSIVE: 1, PRICE_LEVEL_MODERATE: 2, PRICE_LEVEL_EXPENSIVE: 3, PRICE_LEVEL_VERY_EXPENSIVE: 4 };

  const SHOWN = 8;
  const enabled = () => !!C.GOOGLE_PLACES_KEY;

  // ---- дневной счётчик запросов (страховка поверх квоты в Google Cloud) ----
  function usedToday() {
    try {
      const o = JSON.parse(localStorage.getItem("gp_usage") || "{}");
      return o.day === new Date().toISOString().slice(0, 10) ? o.n : 0;
    } catch { return 0; }
  }
  function bump(n) {
    try { localStorage.setItem("gp_usage", JSON.stringify({ day: new Date().toISOString().slice(0, 10), n: usedToday() + n })); } catch {}
  }

  async function call(path, body, fieldMask) {
    if (usedToday() + 10 > (C.DAILY_REQUEST_CAP || 60)) throw new Error("cap");
    bump(1);
    const r = await fetch(`${API}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Goog-Api-Key": C.GOOGLE_PLACES_KEY, "X-Goog-FieldMask": fieldMask },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error("http " + r.status);
    return r.json();
  }

  const km = (a, b) => {
    const R = 6371000, rad = (x) => (x * Math.PI) / 180;
    const dLat = rad(b.latitude - a.latitude), dLon = rad(b.longitude - a.longitude);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  };

  async function near(venue, town = "Praha") {
    const ck = "gp:" + venue + "|" + town;
    try { const c = sessionStorage.getItem(ck); if (c) return JSON.parse(c); } catch {}

    // 1) координаты площадки
    const g = await call("places:searchText", {
      textQuery: `${venue}, ${town}`, languageCode: "cs", maxResultCount: 1,
      ...(town === "Praha" ? { regionCode: "CZ", locationBias: { circle: { center: { latitude: 50.0755, longitude: 14.4378 }, radius: 30000 } } } : {}),
    }, "places.location,places.displayName");
    const spot = g.places && g.places[0];
    if (!spot) throw new Error("nogeo");
    const center = spot.location;

    // 2) рестораны в радиусе ~15 минут пешком, без фастфуда и «еды на вынос»
    const n = await call("places:searchNearby", {
      includedTypes: ["restaurant"],
      excludedTypes: ["fast_food_restaurant", "meal_takeaway", "meal_delivery"],
      maxResultCount: 20, rankPreference: "POPULARITY", languageCode: "cs",
      locationRestriction: { circle: { center, radius: C.WALK_RADIUS_M || 1200 } },
    }, "places.id,places.displayName,places.rating,places.userRatingCount,places.priceLevel,places.googleMapsUri,places.shortFormattedAddress,places.primaryTypeDisplayName,places.editorialSummary,places.photos,places.location");

    const items = (n.places || []).map((p) => {
      const dist = km(center, p.location);
      return {
        id: p.id,
        name: p.displayName && p.displayName.text,
        rating: p.rating || 0,
        reviews: p.userRatingCount || 0,
        price: p.priceLevel in PRICE ? PRICE[p.priceLevel] : null,
        kind: p.primaryTypeDisplayName && p.primaryTypeDisplayName.text,
        address: p.shortFormattedAddress,
        url: p.googleMapsUri,
        summary: p.editorialSummary && p.editorialSummary.text,
        photo: p.photos && p.photos[0] ? `${API}/${p.photos[0].name}/media?maxWidthPx=800&key=${C.GOOGLE_PLACES_KEY}` : null,
        walkMin: Math.max(1, Math.round((dist * 1.3) / 80)),   // 80 м/мин, поправка на извилистость улиц
      };
    }).filter((p) => p.name);
    // фото тарифицируются за каждую загрузку: учитываем в дневном счётчике те, что реально покажем
    bump(Math.min(SHOWN, items.filter((i) => i.photo).length));
    const res = { center, items };
    try { sessionStorage.setItem(ck, JSON.stringify(res)); } catch {}
    return res;
  }

  // Рейтинг с поправкой на число отзывов: 4.8 по 12 отзывам хуже, чем 4.6 по 900.
  const bayes = (p) => (p.rating * p.reviews + 4.0 * 50) / (p.reviews + 50);

  function rank(items, { sort = "best", strict = true, maxPrice = 4 } = {}) {
    let list = items.filter((p) => p.price == null || p.price <= maxPrice);
    if (strict) list = list.filter((p) => p.rating >= (C.MIN_RATING || 4.3) && p.reviews >= (C.MIN_REVIEWS || 100));
    const price = (p, dflt) => (p.price == null ? dflt : p.price);
    const by = {
      best: (a, b) => bayes(b) - bayes(a),
      cheap: (a, b) => price(a, 9) - price(b, 9) || bayes(b) - bayes(a),
      pricey: (a, b) => price(b, -1) - price(a, -1) || bayes(b) - bayes(a),
      near: (a, b) => a.walkMin - b.walkMin || bayes(b) - bayes(a),
    };
    return [...list].sort(by[sort] || by.best).slice(0, SHOWN);
  }

  window.Places = { enabled, near, rank, usedToday };
})();
