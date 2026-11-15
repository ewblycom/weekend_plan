// Профиль вкуса: что человек лайкает и пропускает → чем похожее поднимаем в ленте.
// Всё считается на устройстве; хранится как счётчики по признакам, а не как список событий (события живут неделями).
(function (root) {
  const HALF_LIFE_DAYS = 60;      // старые сигналы ослабевают вдвое за 60 дней
  const SKIP_WEIGHT = 0.4;        // «мимо» — слабый сигнал: часто это «не в эту дату», а не «не моё»
  const PRIOR = 3;                // сглаживание: 1–2 лайка не делают из категории «любимую»
  const FULL_AT = 25;             // после стольких решений профиль работает на полную силу
  const MAX_FEATURES = 70;
  const STOP = new Set(["praha", "prague", "praze", "live", "show", "tour", "2026", "2027", "ticket", "tickets", "wine", "party", "день", "вечер"]);
  const DAY = 864e5;

  const decay = (t, now) => Math.pow(0.5, Math.max(0, now - t) / (HALF_LIFE_DAYS * DAY));

  function featuresOf(e) {
    const f = [];
    if (e.kind === "place") f.push(["kind:" + e.placeKind, 1]);
    else if (e.category) f.push(["cat:" + e.category, 1]);
    const venue = (e.venue || "").split(/[,—]/)[0].trim().toLowerCase();
    if (venue && e.kind !== "place") f.push(["venue:" + venue.slice(0, 40), 0.5]);
    if (e.lang === "ru") f.push(["ru", 0.5]);
    if (e.free) f.push(["free", 0.3]);
    else if (e.price_from) f.push(["price:" + (e.price_from < 300 ? "low" : e.price_from < 800 ? "mid" : "high"), 0.3]);
    const words = (e.title || "").toLowerCase().match(/[\p{L}\d]{5,}/gu) || [];
    [...new Set(words)].filter((w) => !STOP.has(w)).slice(0, 4).forEach((w) => f.push(["kw:" + w, 0.25]));
    return f;
  }

  // taste = { n: число решений, f: { признак: [лайки, пропуски, время последнего сигнала] } }
  const empty = () => ({ n: 0, f: {} });

  function record(taste, e, like, now = Date.now()) {
    taste.n += 1;
    featuresOf(e).forEach(([k]) => {
      const cur = taste.f[k] || [0, 0, now];
      const d = decay(cur[2], now);
      const l = cur[0] * d + (like ? 1 : 0), s = cur[1] * d + (like ? 0 : 1);
      taste.f[k] = [+l.toFixed(3), +s.toFixed(3), now];
    });
    prune(taste);
    return taste;
  }

  // откат сигнала: «назад» в ленте или убрали из плана. wasLike=true — лайк превращается в слабый «мимо», иначе сигнал просто стирается
  function retract(taste, e, wasLike, now = Date.now()) {
    taste.n = Math.max(0, taste.n - (wasLike ? 0 : 1));
    featuresOf(e).forEach(([k]) => {
      const cur = taste.f[k]; if (!cur) return;
      if (wasLike) { cur[0] = Math.max(0, cur[0] - 1); cur[1] += 1; } else cur[1] = Math.max(0, cur[1] - 1);
      cur[2] = now;
    });
  }

  function prune(taste) {
    const ks = Object.keys(taste.f);
    if (ks.length <= MAX_FEATURES) return;
    ks.filter((k) => k.startsWith("kw:") || k.startsWith("venue:"))
      .sort((a, b) => taste.f[a][2] - taste.f[b][2])
      .slice(0, ks.length - MAX_FEATURES).forEach((k) => delete taste.f[k]);
  }

  function affinity(taste, k, now = Date.now()) {
    const c = taste.f[k]; if (!c) return 0;
    const d = decay(c[2], now), l = c[0] * d, s = c[1] * d;
    return (l - SKIP_WEIGHT * s) / (l + s + PRIOR);      // от -0.4 до ~+1
  }

  const confidence = (taste) => Math.min(1, taste.n / FULL_AT);

  // насколько событие похоже на то, что человек выбирал: -0.4 … +1
  function score(taste, e, now = Date.now()) {
    const fs = featuresOf(e); let num = 0, den = 0;
    fs.forEach(([k, w]) => { num += w * affinity(taste, k, now); den += w; });
    return den ? num / den : 0;
  }

  // Итоговый балл ленты: базовый (язык, пара, район…) + вклад вкуса. Вкус растёт вместе с числом решений.
  const blend = (taste, e, base) => base + 6 * confidence(taste) * score(taste, e);

  // категории, про которые мы почти ничего не знаем — их периодически подмешиваем, чтобы лента не замыкалась в пузырь
  function unexplored(taste, e) {
    const k = e.kind === "place" ? "kind:" + e.placeKind : "cat:" + e.category;
    const c = taste.f[k]; return !c || c[0] + c[1] < 3;
  }

  // топ интересов для экрана «Твой вкус» и для настройки парсера
  function top(taste, now = Date.now(), n = 6) {
    return Object.keys(taste.f).filter((k) => k.startsWith("cat:") || k.startsWith("kind:"))
      .map((k) => ({ key: k, aff: affinity(taste, k, now), seen: taste.f[k][0] + taste.f[k][1] }))
      .filter((x) => x.seen >= 1).sort((a, b) => b.aff - a.aff).slice(0, n);
  }

  const api = { featuresOf, empty, record, retract, affinity, score, confidence, blend, unexplored, top };
  if (typeof module !== "undefined") module.exports = api; else root.Taste = api;
})(typeof self !== "undefined" ? self : this);
