// «Куда на выходных» — пошаговый сценарий:
// даты → рулетка категорий → раунд 1 (нравится / не нравится) → раунд 2 (выбрать одно) → то же для ужина → календарь.
const tg = window.Telegram && window.Telegram.WebApp;
const CFG = window.APP_CONFIG || {};
if (tg) {
  tg.ready(); tg.expand();
  if (tg.colorScheme) document.documentElement.dataset.theme = tg.colorScheme;   // тема Telegram = тема устройства
  tg.onEvent && tg.onEvent("themeChanged", () => { document.documentElement.dataset.theme = tg.colorScheme; });
}

const CAT = {
  concert: "Концерты", theater: "Театр", show: "Шоу и стендап", workshop: "Мастер-классы",
  market: "Ярмарки", food: "Гастро", exhibition: "Выставки", festival: "Фестивали",
  active: "Активный отдых", sport: "Спорт", other: "Другое",
};
const LANG = { ru: "Русский", cs: "Чешский", en: "English" };
const SOURCE = { "prague.eu": "prague.eu", kudyznudy: "Kudy z nudy", tickettailor: "Ticket Tailor", telegram: "Telegram", places: "Подборка мест" };
const SORTS = [["best", "Лучшее"], ["cheap", "Дешевле"], ["pricey", "Дороже"], ["date", "По дате"]];
const RSORTS = [["best", "Лучшее"], ["cheap", "Дешевле"], ["pricey", "Дороже"], ["near", "Ближе"]];

const S = {
  step: "dates",                       // dates | cats | spin | r1 | r2 | rest | done
  events: [], places: [], weekend: null,
  sel: { a: null, b: null },           // выбранные даты в календаре
  cal: { y: 0, m: 0 },
  from: null, to: null,
  cats: new Set(), filters: { free: false, ru: false },
  sort: "best", cat: null, pool: [], vote: {}, round: 1,   // vote: id → true / false
  choice: null,                        // выбранное событие (id)
  plans: loadJson("plans", {}), planId: null,
  rest: { status: "idle", items: [], sort: "best", vote: {}, round: 1, choice: null },
};

// ---------- хранение ----------
function loadJson(k, dflt) { try { return JSON.parse(localStorage.getItem(k)) ?? dflt; } catch { return dflt; } }
function savePlans() {
  const s = JSON.stringify(S.plans);
  try { localStorage.setItem("plans", s); } catch {}
  try { if (tg && tg.CloudStorage && s.length < 3900) tg.CloudStorage.setItem("plans", s); } catch {}
}
function syncCloud() {
  try {
    tg && tg.CloudStorage && tg.CloudStorage.getItem("plans", (e, v) => {
      if (!e && v) { S.plans = { ...JSON.parse(v), ...S.plans }; if (S.step === "dates") render(); }
    });
  } catch {}
}

// ---------- утилиты ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const noEmoji = (s) => String(s || "").replace(/[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}️‍]/gu, "").replace(/\s{2,}/g, " ").trim();
const iso = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
const todayIso = () => iso(new Date());
const dt = (s) => new Date(s + "T12:00:00");
const fmtShort = (s) => dt(s).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }).replace(".", "");
const fmtLong = (s) => dt(s).toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
const fmtRange = (a, b) => (a === b ? fmtShort(a) : `${fmtShort(a)} — ${fmtShort(b)}`);
const overlaps = (e, a, b) => !e.start || (e.start <= b && (e.end || e.start) >= a);
const open = (url) => (tg && tg.openLink ? tg.openLink(url) : window.open(url, "_blank"));
const haptic = (kind) => { try { tg && tg.HapticFeedback && (kind === "select" ? tg.HapticFeedback.selectionChanged() : tg.HapticFeedback.notificationOccurred(kind)); } catch {} };
const q = (s) => encodeURIComponent(s);
const mapUrl = (s) => `https://www.google.com/maps/search/${q(s)}`;
const dollars = (n) => (n == null ? "" : n === 0 ? "бесплатно" : "$".repeat(n));

function when(e) {
  if (!e.start) return e.kind === "place" ? "Без привязки к дате" : "Дата в посте";
  let s = e.end && e.end !== e.start ? `${fmtShort(e.start)} — ${fmtShort(e.end)}` : fmtShort(e.start);
  if (e.time) s += `, ${e.time}`;
  return (e.date_uncertain ? "≈ " : "") + s;
}
function priceTag(e) { return e.free ? "Бесплатно" : e.price_from ? `от ${e.price_from.toLocaleString("ru-RU")} Kč` : ""; }

// ---------- данные для рулетки ----------
function placesAsEvents() {
  return S.places.map((p) => ({
    id: "place-" + p.name, kind: "place", source: "places", url: p.url, title: p.name, category: "active",
    venue: p.map || p.name, description: p.note, lang: "cs", score: 5, tags: [p.area].filter(Boolean),
    start: null, end: null, time: null, free: null, price_from: null,
  }));
}
function inRange() {
  const all = [...S.events, ...placesAsEvents()].filter((e) => overlaps(e, S.from, S.to));
  return all.filter((e) => (!S.filters.free || e.free) && (!S.filters.ru || e.lang === "ru"));
}
const priceKey = (e) => (e.free ? 0 : e.price_from ?? null);
function sortList(list, mode) {
  const cmpPrice = (x, y, dir) => {
    const a = priceKey(x), b = priceKey(y);
    if (a == null && b == null) return y.score - x.score;
    if (a == null) return 1; if (b == null) return -1;
    return dir * (a - b) || y.score - x.score;
  };
  const a = [...list];
  if (mode === "date") a.sort((x, y) => (x.start || "9").localeCompare(y.start || "9") || y.score - x.score);
  else if (mode === "cheap") a.sort((x, y) => cmpPrice(x, y, 1));
  else if (mode === "pricey") a.sort((x, y) => cmpPrice(x, y, -1));
  else a.sort((x, y) => y.score - x.score);
  return a;
}

// ---------- шапка-«поиск» ----------
function renderSearch() {
  const rows = [];
  if (S.from) rows.push(["dates", "Даты", fmtRange(S.from, S.to)]);
  if (S.cat && !["dates", "cats", "spin"].includes(S.step)) rows.push(["cats", "Категория", CAT[S.cat]]);
  const ch = S.choice && eventOf(S.choice);
  if (ch && ["rest", "done"].includes(S.step)) rows.push(["r2", "Событие", ch.title]);
  const dn = S.rest.choice && S.rest.items.find((i) => i.id === S.rest.choice);
  if (dn && S.step === "done") rows.push(["rest", "Ужин", dn.name]);
  $("search").innerHTML = rows.map(([k, l, v]) => `<button class="srow" data-back="${k}"><span class="k">${l}</span><span class="v">${esc(v)}</span></button>`).join("");
  $("search").style.display = rows.length ? "" : "none";
}
const eventOf = (id) => [...S.events, ...placesAsEvents()].find((e) => e.id === id) || (S.plans[id] && S.plans[id].event);

// ---------- экран 1: календарь ----------
function monthGrid(y, m) {
  const first = new Date(y, m, 1), startWd = (first.getDay() + 6) % 7, days = new Date(y, m + 1, 0).getDate();
  const eventDays = new Set();
  S.events.forEach((e) => {
    if (!e.start) return;
    const end = e.end && e.end !== e.start ? e.end : e.start;
    if (e.start === end) eventDays.add(e.start);
  });
  let h = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((w) => `<div class="cal-wd">${w}</div>`).join("");
  h += '<div></div>'.repeat(startWd);
  const t = todayIso(), a = S.sel.a, b = S.sel.b || S.sel.a;
  for (let d = 1; d <= days; d++) {
    const s = iso(new Date(y, m, d));
    const cls = ["day"];
    if (s < t) cls.push("past");
    if (s === t) cls.push("today");
    if (a && s === a) cls.push("start");
    if (b && s === b) cls.push("end");
    if (a && b && s > a && s < b) cls.push("mid");
    if (eventDays.has(s)) cls.push("has");
    h += `<button class="${cls.join(" ")}" data-day="${s}"><span>${d}</span></button>`;
  }
  return h;
}
function viewDates() {
  const { y, m } = S.cal, now = new Date();
  const base = now.getFullYear() * 12 + now.getMonth(), cur = y * 12 + m;
  const name = new Date(y, m, 1).toLocaleDateString("ru-RU", { month: "long" }) + " " + y;
  const plans = Object.values(S.plans).sort((p, q) => (p.date + (p.time || "")).localeCompare(q.date + (q.time || "")));
  return `<h1 class="title">Когда пойдём?</h1>
    <p class="lead">Отметьте первый и последний день. Один день — нажмите на него дважды.</p>
    <div class="cal glass">
      <div class="cal-head">
        <button class="nav prev" data-month="-1" ${cur <= base ? "disabled" : ""} aria-label="Назад"></button>
        <b>${esc(name)}</b>
        <button class="nav next" data-month="1" ${cur >= base + 3 ? "disabled" : ""} aria-label="Вперёд"></button>
      </div>
      <div class="cal-grid">${monthGrid(y, m)}</div>
    </div>
    <p class="hint muted"><button class="btn-quiet" data-weekend="1">Ближайшие выходные</button></p>
    ${plans.length ? `<div class="plans"><div class="row-label"><b>Запланировано</b></div>${plans.map((p) =>
      `<button class="plan-row" data-plan="${esc(p.id)}"><span><b>${esc(p.event.title)}</b></span><span>${esc(fmtShort(p.date))}${p.time ? ", " + esc(p.time) : ""}</span></button>`).join("")}</div>` : ""}`;
}
function pickDay(s) {
  const t = S.sel;
  if (!t.a || t.b || s < t.a) { S.sel = { a: s, b: null }; return render(); }   // начало нового выбора
  S.sel = { a: t.a, b: s }; render();                                           // второй тап — конец (тот же день = один день)
  setTimeout(() => applyDates(S.sel.a, S.sel.b), 380);
}
function applyDates(a, b) {
  S.from = a; S.to = b; S.sel = { a, b };
  S.cat = null; S.vote = {}; S.choice = null; S.rest = freshRest();
  S.step = "cats"; haptic("select"); render(); window.scrollTo({ top: 0, behavior: "smooth" });
}
function weekendRange() {
  const n = new Date(), wd = n.getDay(), off = (k) => iso(new Date(n.getFullYear(), n.getMonth(), n.getDate() + k));
  if (wd === 0) return [todayIso(), todayIso()];
  if (wd === 6) return [todayIso(), off(1)];
  const toFri = (5 - wd + 7) % 7;
  return [off(toFri), off(toFri + 2)];
}

// ---------- экран 2: категории ----------
function viewCats() {
  const list = inRange();
  const counts = {};
  list.forEach((e) => { if (CAT[e.category]) counts[e.category] = (counts[e.category] || 0) + 1; });
  const cats = Object.keys(CAT).filter((c) => counts[c]);
  return `<h1 class="title">Что хочется?</h1>
    <p class="lead">Отметьте несколько категорий — рулетка выберет одну. Если не выбрать ни одной, крутится всё.</p>
    <div class="chips">${cats.map((c) => `<button class="chip ${S.cats.has(c) ? "on" : ""}" data-cat="${c}">${CAT[c]}<i>${counts[c]}</i></button>`).join("") || '<p class="muted">В эти даты ничего не найдено. Выберите другие даты.</p>'}</div>
    <div class="row-label"><b>Цена</b></div>
    <div class="seg glass">${[[false, "Любая"], [true, "Бесплатно"]].map(([v, l]) => `<button class="${S.filters.free === v ? "on" : ""}" data-filter="free:${v}">${l}</button>`).join("")}</div>
    <div class="row-label"><b>Язык</b></div>
    <div class="seg glass">${[[false, "Любой"], [true, "Русский"]].map(([v, l]) => `<button class="${S.filters.ru === v ? "on" : ""}" data-filter="ru:${v}">${l}</button>`).join("")}</div>`;
}
function dockCats() {
  const has = inRange().some((e) => CAT[e.category]);
  return `<div class="glass"><button class="btn-primary block" data-spin="1" ${has ? "" : "disabled"}>Запустить</button></div>`;
}

// ---------- экран 2б: рулетка ----------
function startSpin() {
  const avail = Object.keys(CAT).filter((c) => inRange().some((e) => e.category === c));
  const chosen = avail.filter((c) => S.cats.has(c));
  const from = chosen.length ? chosen : avail;
  if (!from.length) return;
  const final = from[Math.floor(Math.random() * from.length)];
  const labels = [];
  for (let i = 0; i < 26; i++) labels.push(from[Math.floor(Math.random() * from.length)]);
  labels.push(final);
  S.step = "spin"; S.cat = null; render();
  const reel = $("reel"); if (!reel) return;
  reel.innerHTML = labels.map((c) => `<div>${esc(CAT[c])}</div>`).join("");
  void reel.offsetHeight;
  reel.style.transform = `translateY(${-(labels.length - 2) * 72}px)`;
  haptic("select");
  let done = false;
  const finish = () => {
    if (done) return; done = true;
    haptic("success");
    setTimeout(() => {
      S.cat = final; S.vote = {}; S.round = 1;
      S.pool = sortList(inRange().filter((e) => e.category === final), S.sort);
      S.step = "r1"; render(); window.scrollTo({ top: 0, behavior: "smooth" });
    }, 650);
  };
  reel.addEventListener("transitionend", finish, { once: true });
  setTimeout(finish, 3200);
}
function viewSpin() {
  return `<h1 class="title">Крутим…</h1><div class="reel-wrap glass"><div class="reel" id="reel"></div></div>`;
}

// ---------- карточки событий ----------
function eventCard(e, mode) {
  const v = S.vote[e.id];
  const tags = [];
  if (e.lang) tags.push(`<span class="tag lang">${LANG[e.lang] || e.lang}</span>`);
  const p = priceTag(e); if (p) tags.push(`<span class="tag price">${esc(p)}</span>`);
  (e.tags || []).map(noEmoji).filter((t) => t && t !== "бесплатно" && t !== "на русском").slice(0, 3).forEach((t) => tags.push(`<span class="tag">${esc(t)}</span>`));
  const long = e.description && e.description.length > 20 ? e.description : "";
  const yes = mode === "r2" ? "Иду" : "Нравится", no = mode === "r2" ? "Не иду" : "Не нравится";
  return `<article class="card glass ${v === true ? "liked" : ""} ${v === false ? "passed" : ""}">
    <div class="eyebrow">${esc(CAT[e.category] || "")}</div>
    <h3>${esc(e.title)}</h3>
    <div class="meta">${esc(when(e))}${e.venue ? " · " + esc(e.venue) : ""}</div>
    <div class="tags">${tags.join("")}</div>
    ${long ? `<div class="more" id="more-${esc(e.id)}" hidden>${esc(long)}</div>` : ""}
    <div class="links">
      ${long ? `<button class="btn-quiet" data-more="${esc(e.id)}">Подробнее</button>` : ""}
      <button class="btn-quiet" data-open="${esc(e.url)}">Источник</button>
    </div>
    <div class="pair">
      <button class="btn ${v === false ? "on" : ""}" data-vote="${esc(e.id)}:0">${no}</button>
      <button class="btn ${v === true ? "on" : ""}" data-vote="${esc(e.id)}:1">${yes}</button>
    </div></article>`;
}
function sortBar(current, opts, attr) {
  return `<div class="seg glass" style="margin-bottom:12px">${opts.map(([k, l]) => `<button class="${current === k ? "on" : ""}" data-${attr}="${k}">${l}</button>`).join("")}</div>`;
}
function viewRound1() {
  const list = sortList(S.pool, S.sort);
  return `<h1 class="title">${esc(CAT[S.cat])}</h1>
    <p class="lead">Отметьте то, что нравится. Потом выберем одно.</p>
    ${sortBar(S.sort, SORTS, "sort")}
    <div class="list">${list.map((e) => eventCard(e, "r1")).join("") || '<p class="muted empty">Ничего не нашлось</p>'}</div>`;
}
function dockRound1() {
  const n = Object.values(S.vote).filter(Boolean).length;
  return n ? `<div class="glass"><button class="btn-primary block" data-next="r2">Дальше · ${n}</button></div>` : "";
}
function viewRound2() {
  const list = S.pool.filter((e) => S.vote[e.id]);
  return `<h1 class="title">Выберите одно</h1><p class="lead">Нажмите «Иду» на том, что выбираете точно.</p>
    <div class="list">${list.map((e) => eventCard({ ...e }, "r2")).join("")}</div>`;
}

// ---------- выбор события → план + ужин ----------
const startTime = (e) => { const m = /(\d{1,2}):(\d{2})/.exec(e.time || ""); return m ? `${m[1].padStart(2, "0")}:${m[2]}` : null; };
function endTime(e) { const a = [...(e.time || "").matchAll(/(\d{1,2}):(\d{2})/g)]; return a.length > 1 ? `${a[1][1].padStart(2, "0")}:${a[1][2]}` : null; }
function shiftTime(hhmm, min) {
  const [h, m] = hhmm.split(":").map(Number), t = (((h * 60 + m + min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
function planDate(e) {
  const lo = e.start || S.from, hi = e.end || e.start || S.to;
  let day = S.from > lo ? S.from : lo;
  if (day > hi) day = hi;
  if (day < S.from) day = S.from;
  return day;
}
function chooseEvent(id) {
  const e = eventOf(id); if (!e) return;
  S.choice = id;
  S.plans[id] = { id, event: e, date: planDate(e), time: startTime(e), minutes: 120, dinner: null };
  savePlans();
  S.rest = freshRest(); S.step = "rest"; render(); haptic("success");
  window.scrollTo({ top: 0 });
  loadRestaurants();
}
const freshRest = () => ({ status: "idle", items: [], sort: "best", vote: {}, round: 1, choice: null });

// ---------- рестораны ----------
async function loadRestaurants() {
  const p = S.plans[S.choice], e = p.event, r = S.rest;
  if (!e.venue) { r.status = "novenue"; return render(); }
  if (!Places.enabled()) { r.status = "nokey"; return render(); }
  r.status = "loading"; render();
  try {
    const res = await Places.near(e.venue);
    if (S.rest !== r) return;
    r.all = res.items; r.status = "ok";
  } catch (err) { if (S.rest !== r) return; r.status = "error"; r.msg = err.message; }
  render();
}
function restList() { return Places.rank(S.rest.all || [], { sort: S.rest.sort, strict: true, maxPrice: 4 }); }
function restCard(x, mode) {
  const v = S.rest.vote[x.id];
  const bits = [`${x.rating.toFixed(1)}, ${x.reviews} отзывов`, dollars(x.price), `${x.walkMin} мин пешком`].filter(Boolean);
  const yes = mode === "r2" ? "Ужин здесь" : "Нравится", no = mode === "r2" ? "Не сюда" : "Не нравится";
  return `<article class="card glass ${v === true ? "liked" : ""} ${v === false ? "passed" : ""}">
    ${x.photo ? `<img class="photo" loading="lazy" src="${esc(x.photo)}" alt="" onerror="this.remove()">` : ""}
    <div class="eyebrow">${esc(x.kind || "Ресторан")}</div>
    <h3>${esc(x.name)}</h3>
    <div class="meta">${esc(bits.join(" · "))}</div>
    ${x.summary ? `<div class="more" style="display:block">${esc(x.summary)}</div>` : ""}
    <div class="links"><button class="btn-quiet" data-open="${esc(x.url)}">Открыть в Google</button></div>
    <div class="pair">
      <button class="btn ${v === false ? "on" : ""}" data-rvote="${esc(x.id)}:0">${no}</button>
      <button class="btn ${v === true ? "on" : ""}" data-rvote="${esc(x.id)}:1">${yes}</button>
    </div></article>`;
}
function savedBanner() {
  const p = S.plans[S.choice];
  return `<div class="sum glass"><div class="eyebrow">Событие сохранено</div><h3>${esc(p.event.title)}</h3>
    <div class="muted">${esc(fmtLong(p.date))}${p.time ? ", " + esc(p.time) : ""}</div>
    <div class="links" style="margin-top:10px"><button class="btn-quiet" data-ics="${esc(p.id)}">Скачать .ics</button><button class="btn-quiet" data-gcal="0">Google Calendar</button></div></div>`;
}
function viewRest() {
  const r = S.rest, p = S.plans[S.choice], e = p.event;
  const head = savedBanner() + `<h1 class="title">Где поесть</h1><p class="lead">Рестораны в 15 минутах пешком от «${esc(e.venue || e.title)}».</p>`;
  if (r.status === "loading" || r.status === "idle") return head + `<div class="list"><div class="skeleton"></div><div class="skeleton"></div></div>`;
  if (r.status === "novenue") return head + `<p class="muted">У события нет точного адреса, поэтому рестораны рядом найти не получится.</p>`;
  if (r.status === "nokey") return head + `<p class="muted">Ключ Google Places не подключён (см. README), поэтому рестораны с рейтингами недоступны.</p><div class="stack"><button class="btn block" data-open="${esc(mapUrl("restaurace u " + (e.venue || e.title) + ", Praha"))}">Открыть рестораны в Google Maps</button></div>`;
  if (r.status === "error") {
    const why = { cap: "Достигнут дневной лимит запросов.", nogeo: "Не удалось найти это место на карте." }[r.msg] || "Не получилось загрузить рестораны. Проверьте ключ и его ограничения в Google Cloud.";
    return head + `<p class="muted">${esc(why)}</p><div class="stack"><button class="btn block" data-open="${esc(mapUrl("restaurace u " + (e.venue || e.title) + ", Praha"))}">Открыть в Google Maps</button></div>`;
  }
  const list = restList();
  if (r.round === 2) {
    const liked = list.filter((x) => r.vote[x.id]);
    return head + `<h3 style="margin:18px 4px 10px;font:var(--t-h)">Выберите одно место</h3><div class="list">${liked.map((x) => restCard(x, "r2")).join("")}</div>`;
  }
  return head + sortBar(r.sort, RSORTS, "rsort") +
    `<div class="list">${list.map((x) => restCard(x, "r1")).join("") || '<p class="muted empty">Под фильтры (от 4,3 и 100+ отзывов) ничего не подошло.</p>'}</div>`;
}
function dockRest() {
  const r = S.rest;
  if (r.status === "ok" && r.round === 1) {
    const n = Object.values(r.vote).filter(Boolean).length;
    return n ? `<div class="glass"><button class="btn-primary block" data-rnext="1">Дальше · ${n}</button></div>`
             : `<div class="glass"><button class="btn block" data-skip="1">Без ужина</button></div>`;
  }
  if (r.status !== "ok" && r.status !== "loading" && r.status !== "idle") return `<div class="glass"><button class="btn-primary block" data-skip="1">Готово</button></div>`;
  if (r.status === "ok" && r.round === 2) return `<div class="glass"><button class="btn block" data-skip="1">Без ужина</button></div>`;
  return "";
}
function defaultDinnerTime(p) {
  const st = p.time, en = endTime(p.event);
  if (st && en && st < "15:00") return shiftTime(en, 30);
  if (st) return shiftTime(st, -120);
  return "19:00";
}
function chooseDinner(id) {
  const x = S.rest.all.find((i) => i.id === id), p = S.plans[S.choice]; if (!x) return;
  p.dinner = { id: x.id, name: x.name, address: x.address, url: x.url, rating: x.rating.toFixed(1), date: p.date, time: defaultDinnerTime(p) };
  S.rest.choice = id; savePlans();
  S.step = "done"; render(); haptic("success"); window.scrollTo({ top: 0 });
}

// ---------- итог ----------
function icsItems(p) {
  const e = p.event;
  const items = [{ uid: p.id, title: e.title, date: p.date, time: p.time, minutes: p.minutes || 120,
    location: [e.venue, "Praha"].filter(Boolean).join(", "), description: CAT[e.category] || "", url: e.url }];
  if (p.dinner) items.push({ uid: p.id + "-dinner", title: "Ужин: " + p.dinner.name, date: p.dinner.date || p.date,
    time: p.dinner.time || "19:00", minutes: 90, location: p.dinner.address || p.dinner.name, description: "К событию: " + e.title, url: p.dinner.url });
  return items;
}
const downloadIcs = (id) => { const p = S.plans[id]; p && ICS.download(`plan-${p.date}.ics`, ICS.build(icsItems(p))); };
const gcal = (id, i) => { const p = S.plans[id]; p && open(ICS.googleUrl(icsItems(p)[i] || icsItems(p)[0])); };
function viewDone() {
  const p = S.plans[S.planId || S.choice]; if (!p) return "";
  const e = p.event, d = p.dinner;
  return `<h1 class="title">Готово</h1><p class="lead">План сохранён в приложении. Добавьте его в календарь.</p>
    <div class="sum glass"><div class="eyebrow">Событие</div><h3>${esc(e.title)}</h3>
      <div class="muted">${esc(e.venue || "")}</div>
      <div class="fields">
        <label class="field">Дата<input type="date" id="plan-date" value="${esc(p.date)}"></label>
        <label class="field">Время<input type="time" id="plan-time" value="${esc(p.time || "")}"></label>
      </div></div>
    ${d ? `<div class="sum glass"><div class="eyebrow">Ужин</div><h3>${esc(d.name)}</h3>
      <div class="muted">${esc(d.address || "")}${d.rating ? " · " + esc(d.rating) : ""}</div>
      <div class="fields"><label class="field">Время<input type="time" id="dinner-time" value="${esc(d.time || "")}"></label></div>
      <div class="links" style="margin-top:8px"><button class="btn-quiet" data-open="${esc(d.url)}">Открыть в Google</button></div></div>` : ""}
    <div class="stack">
      <button class="btn-primary block" data-ics="${esc(p.id)}">Скачать .ics для календаря</button>
      <button class="btn block" data-gcal="0">Добавить в Google Calendar</button>
      <button class="btn-quiet block" data-restart="1">Начать заново</button>
    </div>
    ${tg ? `<p class="muted" style="margin:14px 4px">Если файл не скачался внутри Telegram, откройте сайт в браузере или используйте Google Calendar.</p>` : ""}`;
}

// ---------- рендер ----------
function render() {
  renderSearch();
  const view = $("view"), dock = $("dock");
  let html = "", dk = "";
  switch (S.step) {
    case "dates": html = viewDates(); break;
    case "cats": html = viewCats(); dk = dockCats(); break;
    case "spin": html = viewSpin(); break;
    case "r1": html = viewRound1(); dk = dockRound1(); break;
    case "r2": html = viewRound2(); break;
    case "rest": html = viewRest(); dk = dockRest(); break;
    case "done": html = viewDone(); break;
  }
  const keep = S.step === view.dataset.step && S.step !== "spin" && S.step !== "dates";
  view.dataset.step = S.step;
  const y = window.scrollY;
  view.innerHTML = html;
  if (!keep) { view.classList.remove("view"); void view.offsetWidth; view.classList.add("view"); }
  if (keep) window.scrollTo(0, y);
  dock.innerHTML = dk;
  if (tg && tg.BackButton) { S.step === "dates" ? tg.BackButton.hide() : tg.BackButton.show(); }
}
function goBack(to) {
  if (to === "dates") { S.step = "dates"; S.sel = { a: S.from, b: S.to }; }
  else if (to === "cats") { S.step = "cats"; S.vote = {}; S.choice = null; }
  else if (to === "r2") { S.step = "r2"; S.choice = null; }
  else if (to === "rest") { S.step = "rest"; S.rest.round = 2; }
  render(); window.scrollTo(0, 0);
}
function backOne() {
  const order = { cats: "dates", r1: "cats", r2: "r1", rest: "r2", done: "rest" };
  const t = order[S.step]; if (!t) return;
  if (t === "r1") { S.step = "r1"; render(); }
  else if (t === "r2") { S.step = "r2"; S.choice = null; render(); }
  else if (t === "rest") { S.step = "rest"; S.rest.round = 2; render(); }
  else goBack(t);
}
tg && tg.BackButton && tg.BackButton.onClick(backOne);

// ---------- события ----------
document.addEventListener("click", (ev) => {
  const t = ev.target.closest("button,[data-open]"); if (!t) return;
  const ds = t.dataset;
  if (ds.day) return pickDay(ds.day);
  if (ds.month) { let { y, m } = S.cal; m += Number(ds.month); if (m < 0) { m = 11; y--; } if (m > 11) { m = 0; y++; } S.cal = { y, m }; return render(); }
  if (ds.weekend) { const [a, b] = weekendRange(); return applyDates(a, b); }
  if (ds.back) return goBack(ds.back);
  if (ds.plan) { S.planId = ds.plan; S.choice = ds.plan; const p = S.plans[ds.plan]; S.from = S.from || p.date; S.to = S.to || p.date; S.rest = freshRest(); if (p.dinner) S.rest.choice = p.dinner.id, S.rest.items = [{ id: p.dinner.id, name: p.dinner.name }]; S.step = "done"; return render(); }
  if (ds.cat) { S.cats.has(ds.cat) ? S.cats.delete(ds.cat) : S.cats.add(ds.cat); haptic("select"); return render(); }
  if (ds.filter) { const [k, v] = ds.filter.split(":"); S.filters[k] = v === "true"; S.cats.clear(); return render(); }
  if (ds.spin) return startSpin();
  if (ds.sort) { S.sort = ds.sort; return render(); }
  if (ds.vote) { const k = ds.vote.lastIndexOf(":"), id = ds.vote.slice(0, k), want = ds.vote.slice(k + 1) === "1"; if (S.step === "r2") { return want ? chooseEvent(id) : (S.vote[id] = false, render()); } S.vote[id] = S.vote[id] === want ? undefined : want; haptic("select"); return render(); }
  if (ds.next === "r2") { S.step = "r2"; render(); return window.scrollTo(0, 0); }
  if (ds.more) { const el = $("more-" + ds.more); if (el) { el.hidden = !el.hidden; t.textContent = el.hidden ? "Подробнее" : "Свернуть"; } return; }
  if (ds.open) return open(ds.open);
  if (ds.rsort) { S.rest.sort = ds.rsort; return render(); }
  if (ds.rvote) { const k = ds.rvote.lastIndexOf(":"), id = ds.rvote.slice(0, k), want = ds.rvote.slice(k + 1) === "1"; if (S.rest.round === 2) { return want ? chooseDinner(id) : (S.rest.vote[id] = false, render()); } S.rest.vote[id] = S.rest.vote[id] === want ? undefined : want; haptic("select"); return render(); }
  if (ds.rnext) { S.rest.round = 2; render(); return window.scrollTo(0, 0); }
  if (ds.skip) { S.step = "done"; render(); return window.scrollTo(0, 0); }
  if (ds.ics) return downloadIcs(ds.ics);
  if (ds.gcal !== undefined) return gcal(S.planId || S.choice, Number(ds.gcal));
  if (ds.restart) { S.step = "dates"; S.sel = { a: null, b: null }; S.from = S.to = S.cat = null; S.planId = null; S.choice = null; S.vote = {}; S.rest = freshRest(); render(); return window.scrollTo(0, 0); }
});
document.addEventListener("change", (ev) => {
  const t = ev.target, p = S.plans[S.planId || S.choice]; if (!p) return;
  if (t.id === "plan-date") { p.date = t.value || p.date; if (p.dinner) p.dinner.date = p.date; }
  else if (t.id === "plan-time") p.time = t.value || null;
  else if (t.id === "dinner-time" && p.dinner) p.dinner.time = t.value || null;
  else return;
  savePlans();
});

// ---------- загрузка ----------
async function load() {
  const bust = `?v=${Date.now()}`;
  const [ev, pl] = await Promise.all([
    fetch("data/events.json" + bust).then((r) => r.json()),
    fetch("data/places.json" + bust).then((r) => r.json()).catch(() => ({ places: [] })),
  ]);
  S.events = (ev.events || []).map((e) => ({ ...e, tags: (e.tags || []).map(noEmoji) }));
  S.places = pl.places || [];
  S.weekend = ev.weekend;
  const n = new Date(); S.cal = { y: n.getFullYear(), m: n.getMonth() };
  render(); syncCloud();
}
load().catch((e) => { $("view").innerHTML = `<p class="muted empty">Не удалось загрузить данные: ${esc(e.message)}</p>`; });
