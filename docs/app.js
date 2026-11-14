// «Куда на выходных»: лента-стопка со свайпами → карточка → сайт. Правила: DESIGN.md.
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready(); tg.expand();
  try { tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch {}
  if (tg.colorScheme) document.documentElement.dataset.theme = tg.colorScheme;
  tg.onEvent && tg.onEvent("themeChanged", () => { document.documentElement.dataset.theme = tg.colorScheme; });
}

const CAT = {
  concert: "Концерты", theater: "Театр", show: "Шоу", workshop: "Мастер-классы", market: "Ярмарки", food: "Гастро",
  exhibition: "Выставки", festival: "Фестивали", active: "Активное", sport: "Спорт", kids: "Детям", tour: "Экскурсии", other: "Другое",
};
const CAT1 = { concert: "Концерт", theater: "Театр", show: "Шоу", workshop: "Мастер-класс", market: "Ярмарка", food: "Гастро",
  exhibition: "Выставка", festival: "Фестиваль", active: "Активное", sport: "Спорт", kids: "Детям", tour: "Экскурсия", other: "Событие" };
const KIND = { bowling: "Боулинг", lasergame: "Лазертаг", karting: "Картинг", vr: "VR", escape: "Квесты", workshop: "Мастерские", billiard: "Бильярд", sport: "Скалодром" };
const TOWN = { "Вена": "Wien", "Мюнхен": "München", "Берлин": "Berlin" };
const HOME_AREA = /Praha 4|Braník/i;

// иконки — iconmcp.com
const svg = (w, body, s = 22) => `<svg aria-hidden="true" width="${s}" height="${s}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
const IC = {
  close: (s) => svg(1.6, '<line x1="3.75" y1="3.75" x2="12.25" y2="12.25"/><line x1="12.25" y1="3.75" x2="3.75" y2="12.25"/>', s),
  heart: (s) => `<svg aria-hidden="true" width="${s || 22}" height="${s || 22}" viewBox="0 0 16 16"><path fill="currentColor" d="M8 13.25 C5.5 11.75 2 9.25 2 5.75 C2 3.9 3.4 2.5 5.15 2.5 C6.45 2.5 7.45 3.25 8 4.35 C8.55 3.25 9.55 2.5 10.85 2.5 C12.6 2.5 14 3.9 14 5.75 C14 9.25 10.5 11.75 8 13.25 Z"/></svg>`,
  undo: (s) => svg(1.6, '<path d="M2.75 6.5 H9.75 A3.5 3.5 0 0 1 9.75 13.5 H6.25"/><path d="M6 3.25 L2.75 6.5 L6 9.75"/>', s),
  dice: (s) => svg(1.3, '<path d="M8.009 3.721 L12.931 5.039 C13.571 5.211 13.951 5.869 13.779 6.509 L12.461 11.431 C12.289 12.071 11.631 12.451 10.991 12.279 L6.069 10.961 C5.429 10.789 5.049 10.131 5.221 9.491 L6.539 4.569 C6.711 3.929 7.369 3.549 8.009 3.721 Z"/><circle cx="11.34" cy="6.94" r="0.77" fill="currentColor" stroke="none"/><circle cx="7.66" cy="9.06" r="0.77" fill="currentColor" stroke="none"/><line x1="1.75" y1="5.5" x2="3.75" y2="5.5"/><line x1="1.75" y1="10.5" x2="3.75" y2="10.5"/>', s),
  stack: (s) => svg(1.4, '<rect x="2.25" y="6.25" width="11.5" height="7.5" rx="2"/><line x1="3.75" y1="4.25" x2="12.25" y2="4.25"/><line x1="5.25" y1="2.25" x2="10.75" y2="2.25"/>', s),
  cal: (s) => svg(1.4, '<rect x="2.25" y="3.25" width="11.5" height="10.5" rx="2"/><line x1="5.5" y1="1.75" x2="5.5" y2="4.5"/><line x1="10.5" y1="1.75" x2="10.5" y2="4.5"/><line x1="2.25" y1="7" x2="13.75" y2="7"/>', s),
  ticket: (s) => svg(1.4, '<path d="M3.25 3.5 H12.75 A1.25 1.25 0 0 1 14 4.75 V6.25 A1.75 1.75 0 0 0 14 9.75 V11.25 A1.25 1.25 0 0 1 12.75 12.5 H3.25 A1.25 1.25 0 0 1 2 11.25 V9.75 A1.75 1.75 0 0 0 2 6.25 V4.75 A1.25 1.25 0 0 1 3.25 3.5 Z"/><circle cx="9.75" cy="5.75" r="0.77" fill="currentColor" stroke="none"/><circle cx="9.75" cy="8" r="0.77" fill="currentColor" stroke="none"/><circle cx="9.75" cy="10.25" r="0.77" fill="currentColor" stroke="none"/>', s),
  pin: (s) => svg(1.4, '<path d="M8 14 C8 14 3.25 10 3.25 6.75 A4.75 4.75 0 0 1 12.75 6.75 C12.75 10 8 14 8 14 Z"/><circle cx="8" cy="6.75" r="1.75"/>', s),
  globe: (s) => svg(1.4, '<circle cx="8" cy="8" r="6"/><line x1="2" y1="8" x2="14" y2="8"/><ellipse cx="8" cy="8" rx="2.5" ry="6"/>', s),
  down: (s) => svg(1.6, '<path d="M3.75 5.875 L8 10.125 L12.25 5.875"/>', s),
};

// ---------- состояние ----------
const S = {
  events: [], places: [], loaded: false,
  from: null, to: null, mode: "events", tab: "feed",
  cats: new Set(), kinds: new Set(), ru: false,
  decided: {}, history: [], top: null,
  plan: {}, detail: null, sheet: null, draft: null,
};
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const noEmoji = (s) => String(s || "").replace(/[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}️‍]/gu, "").replace(/\s{2,}/g, " ").trim();
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const todayIso = () => iso(new Date());
const dt = (s) => new Date(s + "T12:00:00");
const addDays = (s, n) => { const d = dt(s); d.setDate(d.getDate() + n); return iso(d); };
const WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
const WDL = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const short = (s) => dt(s).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }).replace(".", "");
const rangeLabel = (a, b) => {
  if (a === b) return short(a);
  const A = dt(a), B = dt(b);
  return A.getMonth() === B.getMonth() ? `${A.getDate()}–${B.getDate()} ${short(b).split(" ")[1]}` : `${short(a)} – ${short(b)}`;
};
const cap1 = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const haptic = (k) => { try { tg && tg.HapticFeedback && (k === "select" ? tg.HapticFeedback.selectionChanged() : k === "light" ? tg.HapticFeedback.impactOccurred("light") : tg.HapticFeedback.notificationOccurred(k)); } catch {} };
const openUrl = (u) => (u.startsWith("mailto:") ? (location.href = u) : tg && tg.openLink ? tg.openLink(u) : window.open(u, "_blank"));
const startTime = (t) => { const m = /(\d{1,2})[:.](\d{2})/.exec(t || ""); return m ? `${m[1].padStart(2, "0")}:${m[2]}` : null; };

function weekendRange() {
  const t = todayIso(), wd = dt(t).getDay();
  if (wd === 0) return [t, t];
  if (wd === 6) return [t, addDays(t, 1)];
  return [addDays(t, 6 - wd), addDays(t, 7 - wd)];
}

// ---------- хранение: выбор возвращается при следующем заходе ----------
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
function cloudSet(k, v) { try { tg && tg.CloudStorage && v.length < 4000 && tg.CloudStorage.setItem(k, v); } catch {} }
function save() {
  const sess = JSON.stringify({ from: S.from, to: S.to, mode: S.mode, cats: [...S.cats], kinds: [...S.kinds], ru: S.ru, decided: S.decided, history: S.history.slice(-30), top: S.top });
  try { localStorage.setItem("s2", sess); localStorage.setItem("plan2", JSON.stringify(S.plan)); } catch {}
  cloudSet("s2", sess);
  const compact = {}; Object.values(S.plan).forEach((p) => (compact[p.id] = { ...p, description: undefined, image: undefined }));
  cloudSet("plan2", JSON.stringify(compact));
}
function applySession(o) {
  if (!o || !o.from || o.to < todayIso()) return false;
  S.from = o.from; S.to = o.to; S.mode = o.mode === "places" ? "places" : "events";
  S.cats = new Set(o.cats || []); S.kinds = new Set(o.kinds || []); S.ru = !!o.ru;
  S.decided = o.decided || {}; S.history = o.history || []; S.top = o.top || null;
  return true;
}
function restore() {
  S.plan = load("plan2", {});
  if (!applySession(load("s2", null))) { const [a, b] = weekendRange(); S.from = a; S.to = b; }
  try {
    tg && tg.CloudStorage && tg.CloudStorage.getItems(["s2", "plan2"], (e, v) => {
      if (e || !v) return;
      let changed = false;
      try { if (v.plan2 && !Object.keys(S.plan).length) { S.plan = JSON.parse(v.plan2); changed = true; } } catch {}
      try { if (v.s2 && !localStorage.getItem("s2") && applySession(JSON.parse(v.s2))) changed = true; } catch {}
      if (changed) render();
    });
  } catch {}
}

// ---------- данные ----------
const slotsIn = (e, a, b) => (e.slots || []).filter((x) => x.date >= a && x.date <= b);
function overlaps(e, a, b) {
  if (e.slots && e.slots.length && (slotsIn(e, a, b).length || e.slots.some((x) => x.date >= b))) return slotsIn(e, a, b).length > 0;
  return !e.start || (e.start <= b && (e.end || e.start) >= a);
}
function tier(e) {
  if (e.kind === "place") return 3;
  if (!e.start) return 2;
  const days = (Date.parse(e.end || e.start) - Date.parse(e.start)) / 864e5;
  return days <= 3 ? 0 : days <= 21 ? 1 : 2;
}
function dayOf(e, a = S.from, b = S.to) {
  const s = slotsIn(e, a, b)[0]; if (s) return s.date;
  if (!e.start) return null;
  return e.start < a ? a : e.start;
}
function timeOf(e, a = S.from, b = S.to) { const s = slotsIn(e, a, b)[0]; return (s && s.time) || startTime(e.time); }
function placeItems() {
  return S.places.map((p) => ({
    id: "place-" + p.name, kind: "place", placeKind: p.kind, title: p.name, area: p.area || "", venue: p.map || p.name,
    description: p.note, image: p.image || null, link: p.site || null, booking: p.booking || null, url: p.url, hours: p.hours || null, score: 5,
  }));
}
function inRange(a = S.from, b = S.to, ru = S.ru) { return S.events.filter((e) => overlaps(e, a, b) && (!ru || e.lang === "ru")); }
function deck() {
  const t0 = (e) => dayOf(e) + (timeOf(e) || "99");
  let xs = inRange().filter((e) => (!S.cats.size || S.cats.has(e.category)) && S.decided[e.id] === undefined);
  xs.sort((x, y) => tier(x) - tier(y) || (tier(x) === 0 ? t0(x).localeCompare(t0(y)) : 0) || y.score - x.score);
  if (S.top) { const i = xs.findIndex((e) => e.id === S.top); if (i > 0) xs.unshift(xs.splice(i, 1)[0]); }
  return xs;
}
const itemById = (id) => S.events.find((e) => e.id === id) || placeItems().find((e) => e.id === id) || (S.plan[id] && S.plan[id].item);

// ---------- куски разметки ----------
function thumb(url, w = 800) {
  if (!url) return "";
  if (url.includes("imgproxy.cdn.praguecitytourism.city")) return url.replace(/\/w:\d+\//, `/w:${w}/`).replace(/\/q:\d+\//, "/q:72/");
  if (url.includes("tickettailorassets.com")) return url.replace(/w_\d+/, `w_${w}`);
  return `https://images.weserv.nl/?url=${encodeURIComponent(url.replace(/^https?:\/\//, ""))}&w=${w}&output=webp&q=72`;
}
function ph(e, cls = "", w = 800) {
  const d = e.kind !== "place" && dayOf(e);
  const num = d ? `<span class="num">${dt(d).getDate()}</span>` : "";
  const img = e.image ? `<img loading="lazy" decoding="async" draggable="false" src="${esc(thumb(e.image, w))}" data-orig="${esc(e.image)}" alt="" onerror="if(this.dataset.orig&&this.src!==this.dataset.orig){this.src=this.dataset.orig;this.dataset.orig=''}else{this.remove()}">` : "";
  return `<div class="ph ${cls}">${num}${img}</div>`;
}
function stickers(e) {
  const out = [];
  if (e.kind === "place") { if (HOME_AREA.test(e.area || "")) out.push('<span class="stk">РЯДОМ С ДОМОМ</span>'); return out; }
  if (tier(e) === 0) out.push('<span class="stk">ТОЛЬКО ЭТИ ВЫХОДНЫЕ</span>');
  else if (e.end && e.end <= addDays(S.to, 3)) out.push('<span class="stk">ПОСЛЕДНИЕ ДНИ</span>');
  if (e.free) out.push('<span class="stk w">БЕСПЛАТНО</span>');
  if (e.lang === "ru") out.push('<span class="stk f">ПО-РУССКИ</span>');
  if (e.city && e.city !== "Прага") out.push(`<span class="stk w">${esc(e.city.toUpperCase())}</span>`);
  return out.slice(0, 3);
}
function metaLine(e) {
  if (e.kind === "place") return [e.area, e.hours].filter(Boolean).join(" · ");
  const d = dayOf(e), t = timeOf(e);
  const day = d ? cap1(WD[dt(d).getDay()]) + " " + dt(d).getDate() : "";
  const venue = (e.venue || "").split(/[,—]/)[0].trim();
  return [day, t, venue].filter(Boolean).join(" · ");
}
function cardHtml(e, cls) {
  return `<article class="card ${cls}" data-id="${esc(e.id)}">
    ${ph(e)}
    <div class="stks">${stickers(e).join("")}</div>
    <span class="cat glass">${esc(CAT1[e.category] || "Событие")}</span>
    <span class="stamp yes">ХОЧУ</span><span class="stamp no">МИМО</span>
    <div class="body"><h2>${esc(e.title)}</h2><p class="meta">${esc(metaLine(e))}</p></div>
  </article>`;
}

// ---------- шапка ----------
function headerHtml() {
  const counts = {};
  let chips = "";
  if (S.mode === "events") {
    inRange().forEach((e) => (counts[e.category] = (counts[e.category] || 0) + 1));
    const cats = Object.keys(CAT).filter((c) => counts[c]);
    chips = `<button class="chip ${S.cats.size ? "" : "on"}" data-act="cat" data-v="">Всё</button>` +
      cats.map((c) => `<button class="chip ${S.cats.has(c) ? "on" : ""}" data-act="cat" data-v="${c}">${CAT[c]}</button>`).join("");
  } else {
    placeItems().forEach((p) => (counts[p.placeKind] = (counts[p.placeKind] || 0) + 1));
    const kinds = Object.keys(KIND).filter((k) => counts[k]);
    chips = `<button class="chip ${S.kinds.size ? "" : "on"}" data-act="kind" data-v="">Всё</button>` +
      kinds.map((k) => `<button class="chip ${S.kinds.has(k) ? "on" : ""}" data-act="kind" data-v="${k}">${KIND[k]}</button>`).join("");
  }
  return `<header class="hdr">
    <div class="row">
      <button class="cap glass" data-act="dates" aria-label="Даты и категории">${IC.cal(18)}<span>${esc(rangeLabel(S.from, S.to))}</span><span class="chev">${IC.down(16)}</span></button>
      <div class="seg glass ${S.mode}"><span class="pill"></span>
        <button class="${S.mode === "events" ? "on" : ""}" data-act="mode" data-v="events">События</button>
        <button class="${S.mode === "places" ? "on" : ""}" data-act="mode" data-v="places">Места</button></div>
    </div>
    <div class="chips">${chips}</div>
  </header>`;
}

// ---------- экраны ----------
function feedHtml() {
  if (S.mode === "places") {
    const xs = placeItems().filter((p) => !S.kinds.size || S.kinds.has(p.placeKind))
      .sort((a, b) => (HOME_AREA.test(b.area) ? 1 : 0) - (HOME_AREA.test(a.area) ? 1 : 0));
    return `<div class="feed"><div class="grid">${xs.map((p, i) => `<button class="tile" style="animation-delay:${Math.min(i, 8) * 30}ms" data-act="open" data-v="${esc(p.id)}">
      ${ph(p, "", 420)}${stickers(p)[0] || ""}${S.plan[p.id] ? `<span class="heart">${IC.heart(14)}</span>` : ""}
      <span class="t"><b>${esc(p.title)}</b><span>${esc(p.area)}</span>${p.hours ? `<span class="h">${esc(p.hours)}</span>` : ""}</span></button>`).join("")}</div></div>`;
  }
  const xs = deck();
  if (!xs.length) {
    const any = inRange().length;
    return `<div class="feed"><div class="empty"><div class="big">${any ? "ВСЁ" : "ПУСТО"}</div>${any ? "Карточки на эти даты закончились" : "Попробуй другие даты"}
      <div class="btns">${any ? '<button class="btn" data-act="reset">Ещё раз</button>' : ""}<button class="btn ink" data-act="dates">Даты</button></div></div></div>`;
  }
  const cards = xs.slice(0, 3).map((e, i) => cardHtml(e, ["top", "b1", "b2"][i])).reverse().join("");
  return `<div class="feed"><div class="stack" id="stack">${cards}</div></div>
    <div class="acts">
      <button class="rb s" data-act="undo" aria-label="Вернуть" ${S.history.length ? "" : "disabled"}>${IC.undo(20)}</button>
      <button class="rb l" data-act="pass" aria-label="Мимо">${IC.close(26)}</button>
      <button class="rb l like" data-act="like" aria-label="Хочу">${IC.heart(28)}</button>
      <button class="rb s" data-act="dice" aria-label="Не знаю, куда хочу">${IC.dice(22)}</button>
    </div>`;
}
function planItems() {
  const t = todayIso();
  return Object.values(S.plan).filter((p) => !p.date || p.date >= t).sort((a, b) => (a.date || "9").localeCompare(b.date || "9") || (a.time || "99").localeCompare(b.time || "99"));
}
function planHtml() {
  const xs = planItems();
  const groups = {};
  xs.forEach((p) => (groups[p.date || "any"] = groups[p.date || "any"] || []).push(p));
  const row = (p) => `<div class="rowwrap" data-row="${esc(p.id)}"><div class="del">${IC.close(20)}</div>
    <button class="prow" data-act="open" data-v="${esc(p.id)}">${ph(p.item, "", 160)}
      <span class="tx"><b>${esc(p.item.title)}</b><span>${esc(p.place || "")}</span></span>
      ${p.time ? `<span class="tm">${esc(p.time)}</span>` : ""}<span class="dot"></span></button></div>`;
  const body = Object.entries(groups).map(([d, ps]) => `<section class="day"><div class="dh">${d === "any"
    ? '<span class="any">КОГДА УГОДНО</span>' : `<b>${dt(d).getDate()}</b><span>${WDL[dt(d).getDay()]}</span>`}</div>${ps.map(row).join("")}</section>`).join("");
  return `<div class="plan"><div class="hd"><h1>План</h1>${xs.some((p) => p.date) ? `<button class="btn ink" data-act="ics">${IC.cal(18)}<span>В календарь</span></button>` : ""}</div>
    ${body || `<div class="empty"><div class="big">ПУСТО</div>Свайпни вправо то, что нравится<div class="btns"><button class="btn ink" data-act="tab" data-v="feed">В ленту</button></div></div>`}</div>`;
}
function tabsHtml() {
  const n = planItems().length;
  return `<nav class="tabs glass ${S.tab}" aria-label="Разделы"><span class="drop"></span>
    <button class="${S.tab === "feed" ? "on" : ""}" data-act="tab" data-v="feed">${IC.stack(20)}<span>Лента</span></button>
    <button class="${S.tab === "plan" ? "on" : ""}" data-act="tab" data-v="plan">${IC.cal(20)}<span>План</span>${n ? `<span class="badge" id="badge">${n}</span>` : ""}</button></nav>`;
}
function detailHtml() {
  const e = itemById(S.detail); if (!e) return "";
  const inPlan = !!S.plan[e.id];
  const slots = e.kind === "place" ? [] : slotsIn(e, S.from, S.to);
  const first = slots[0];
  const slotsHtml = slots.length ? `<div class="slots">${slots.slice(0, 12).map((s, i) => `<span class="slot ${i === 0 ? "on" : ""}">${cap1(WD[dt(s.date).getDay()])} ${dt(s.date).getDate()}<span>${esc(s.time || "")}</span></span>`).join("")}</div>`
    : e.hours ? `<div class="slots"><span class="slot">Открыто<span>${esc(e.hours)}</span></span></div>` : "";
  const town = TOWN[e.city] || "Praha";
  const booking = e.booking || (!e.link ? e.url : null);
  const desc = noEmoji(e.description || "");
  const sub = e.kind === "place" ? [KIND[e.placeKind], e.area].filter(Boolean).join(" · ") : [CAT1[e.category], first ? null : metaLine(e)].filter(Boolean).join(" · ");
  return `<div class="detail" id="detail" role="dialog" aria-label="${esc(e.title)}">
    <button class="x glass" data-act="close" aria-label="Закрыть">${IC.down(20)}</button>
    ${ph(e, "hero", 900)}
    <div class="stks">${stickers(e).join("")}</div>
    <div class="sh"><span class="handle"></span>
      <h1>${esc(e.title)}</h1>
      <p class="meta">${esc(sub || (e.venue || ""))}${first && e.venue ? " · " + esc(e.venue.split(/[,—]/)[0]) : ""}</p>
      ${slotsHtml}
      ${desc.length > 20 ? `<div class="desc" data-act="more">${esc(desc)}</div>` : ""}
    </div>
    <div class="dact">
      ${booking ? `<button class="btn ink big" data-act="url" data-v="${esc(booking)}">${IC.ticket(22)}<span>${e.kind === "place" ? "Бронь" : "Билеты"}</span></button>` : ""}
      ${e.link ? `<button class="btn ${booking ? "sq" : "ink big"}" data-act="url" data-v="${esc(e.link)}" aria-label="Сайт">${IC.globe(22)}${booking ? "" : "<span>Сайт</span>"}</button>` : ""}
      <button class="btn sq" data-act="url" data-v="${esc("https://www.google.com/maps/search/" + encodeURIComponent((e.venue || e.title) + ", " + town))}" aria-label="Маршрут">${IC.pin(22)}</button>
      <button class="rb l ${inPlan ? "like" : ""}" data-act="toggle" data-v="${esc(e.id)}" aria-label="${inPlan ? "Убрать из плана" : "Хочу"}">${IC.heart(24)}</button>
    </div></div>`;
}
function datesHtml() {
  const d = S.draft, t = todayIso();
  const days = [];
  for (let i = 0; i < 28; i++) days.push(addDays(t, i));
  const pills = days.map((s, i) => {
    const wd = dt(s).getDay();
    const on = s === d.a || s === d.b, mid = d.a && d.b && s > d.a && s < d.b;
    return `<button class="dp ${on ? "on" : mid ? "mid" : ""} ${wd === 5 || wd === 6 || wd === 0 ? "wk" : ""} ${wd === 1 && i ? "gap" : ""}" data-act="day" data-v="${s}"><span>${WD[wd]}</span><b>${dt(s).getDate()}</b></button>`;
  }).join("");
  const b = d.b || d.a;
  const list = inRange(d.a, b, d.ru);
  const counts = {}; list.forEach((e) => (counts[e.category] = (counts[e.category] || 0) + 1));
  const cats = Object.keys(CAT).filter((c) => counts[c]);
  const n = list.filter((e) => !d.cats.size || d.cats.has(e.category)).length;
  return `<div class="scrim" data-act="sheetclose"></div>
    <section class="sheet" id="sheet" aria-label="Даты и категории"><span class="handle"></span>
      <div class="days" id="days">${pills}</div>
      <div class="chips">
        ${cats.map((c) => `<button class="chip ${d.cats.has(c) ? "on" : ""}" data-act="dcat" data-v="${c}">${CAT[c]}<i>${counts[c]}</i></button>`).join("")}
        <button class="chip ${d.ru ? "on" : ""}" data-act="dru">По-русски</button>
      </div>
      <div class="foot">
        <button class="btn ink big" data-act="apply" ${n ? "" : "disabled"}>Показать · ${n}</button>
        <button class="rb l lime" data-act="applydice" aria-label="Не знаю, куда хочу" ${n ? "" : "disabled"}>${IC.dice(24)}</button>
      </div></section>`;
}

// ---------- рендер ----------
function render(opts = {}) {
  const app = $("#app");
  if (!S.loaded) { app.innerHTML = '<div class="loading">…</div>'; return; }
  app.innerHTML = (S.tab === "feed" ? headerHtml() + feedHtml() : planHtml()) + tabsHtml() +
    (S.sheet === "dates" ? datesHtml() : "") + (S.detail ? detailHtml() : "");
  if (opts.enter) { const c = $(".card.top"); c && c.classList.add(opts.enter); }
  if (opts.bump) { const b = $("#badge"); b && b.classList.add("bump"); }
  if (S.sheet === "dates" && opts.scrollDays !== false) { const on = $(".dp.on"); on && on.scrollIntoView({ inline: "center", block: "nearest" }); }
  bindStack(); bindPlanRows(); bindDetail();
  if (tg && tg.BackButton) (S.detail || S.sheet) ? tg.BackButton.show() : tg.BackButton.hide();
  save();
}

// ---------- действия ----------
function snapshot(e) {
  const date = e.kind === "place" ? null : dayOf(e);
  const item = { ...e, description: (e.description || "").slice(0, 400) };
  return { id: e.id, date, time: e.kind === "place" ? null : timeOf(e), place: e.kind === "place" ? e.area : (e.venue || "").split(/[,—]/)[0], item };
}
function decide(id, like) {
  S.decided[id] = like ? 1 : 0; S.history.push(id); if (S.top === id) S.top = null;
  if (like) { const e = itemById(id); if (e) S.plan[id] = snapshot(e); haptic("light"); } else haptic("select");
  render({ enter: "enter", bump: like });
}
function fly(card, like) {
  card.classList.remove("drag", "back"); card.classList.add("fly");
  const st = card.querySelector(like ? ".stamp.yes" : ".stamp.no"); if (st) st.style.opacity = 1;
  card.style.transform = `translate(${like ? 560 : -560}px, -40px) rotate(${like ? 22 : -22}deg)`;
  card.style.opacity = "0";
  setTimeout(() => decide(card.dataset.id, like), 260);
}
function swipeTop(like) { const c = $(".card.top"); if (c) fly(c, like); }
function undo() {
  const id = S.history.pop(); if (!id) return;
  if (S.decided[id] === 1) delete S.plan[id];
  delete S.decided[id]; S.top = id; haptic("select");
  render({ enter: "land" });
}
function dice() {
  const xs = deck(); if (!xs.length) return;
  const pick = xs[Math.floor(Math.random() * xs.length)];
  const st = $("#stack"); if (st) st.classList.add("fan");
  haptic("select");
  setTimeout(() => { S.top = pick.id; render({ enter: "land" }); haptic("success"); }, 650);
}
function togglePlan(id) {
  if (S.plan[id]) { delete S.plan[id]; if (S.decided[id] === 1) delete S.decided[id]; haptic("select"); }
  else { const e = itemById(id); if (e) { S.plan[id] = snapshot(e); S.decided[id] = 1; haptic("light"); } }
  render({ bump: !!S.plan[id] });
}
function closeDetail() {
  const d = $("#detail"); if (!d) return;
  d.classList.add("closing"); setTimeout(() => { S.detail = null; render(); }, 260);
}
function closeSheet() {
  const s = $("#sheet"); if (!s) return;
  s.classList.add("closing"); setTimeout(() => { S.sheet = null; S.draft = null; render(); }, 260);
}
function openSheet() { S.sheet = "dates"; S.draft = { a: S.from, b: S.to, cats: new Set(S.cats), ru: S.ru }; render(); }
function applyDraft(withDice) {
  const d = S.draft; S.from = d.a; S.to = d.b || d.a; S.cats = new Set(d.cats); S.ru = d.ru;
  S.mode = "events"; S.tab = "feed"; S.top = null; S.sheet = null; S.draft = null;
  render(); if (withDice) setTimeout(dice, 120);
}
function exportIcs() {
  const items = planItems().filter((p) => p.date).map((p) => ({
    uid: p.id, title: p.item.title, date: p.date, time: p.time, minutes: 120,
    location: p.item.venue || p.place || "", url: p.item.booking || p.item.link || p.item.url || "",
  }));
  if (items.length) ICS.download(`weekend-${S.from}.ics`, ICS.build(items));
}

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("[data-act]"); if (!t) return;
  const a = t.dataset.act, v = t.dataset.v;
  if (a === "mode") { if (S.mode !== v) { S.mode = v; haptic("select"); render(); } return; }
  if (a === "cat") { v ? (S.cats.has(v) ? S.cats.delete(v) : S.cats.add(v)) : S.cats.clear(); S.top = null; haptic("select"); return render(); }
  if (a === "kind") { v ? (S.kinds.has(v) ? S.kinds.delete(v) : S.kinds.add(v)) : S.kinds.clear(); haptic("select"); return render(); }
  if (a === "tab") { S.tab = v; S.detail = null; haptic("select"); window.scrollTo(0, 0); return render(); }
  if (a === "like") return swipeTop(true);
  if (a === "pass") return swipeTop(false);
  if (a === "undo") return undo();
  if (a === "dice") return dice();
  if (a === "reset") { inRange().forEach((e) => { if (S.decided[e.id] === 0) delete S.decided[e.id]; }); S.history = []; return render({ enter: "land" }); }
  if (a === "open") { S.detail = v; haptic("select"); return render(); }
  if (a === "close") return closeDetail();
  if (a === "toggle") return togglePlan(v);
  if (a === "url") return openUrl(v);
  if (a === "more") return t.classList.toggle("open");
  if (a === "ics") return exportIcs();
  if (a === "dates") return openSheet();
  if (a === "sheetclose") return closeSheet();
  if (a === "day") {
    const d = S.draft;
    if (!d.a || d.b) S.draft.a = v, S.draft.b = null;
    else if (v < d.a) S.draft.b = d.a, S.draft.a = v;
    else S.draft.b = v;
    haptic("select"); return render({ scrollDays: false });
  }
  if (a === "dcat") { S.draft.cats.has(v) ? S.draft.cats.delete(v) : S.draft.cats.add(v); haptic("select"); return render({ scrollDays: false }); }
  if (a === "dru") { S.draft.ru = !S.draft.ru; haptic("select"); return render({ scrollDays: false }); }
  if (a === "apply") return applyDraft(false);
  if (a === "applydice") return applyDraft(true);
});
tg && tg.BackButton && tg.BackButton.onClick(() => (S.detail ? closeDetail() : S.sheet ? closeSheet() : null));

// ---------- жесты ----------
function drag(el, { onMove, onEnd, axis }) {
  let x0 = 0, y0 = 0, dx = 0, dy = 0, on = false, locked = null;
  el.addEventListener("pointerdown", (e) => { on = true; x0 = e.clientX; y0 = e.clientY; dx = dy = 0; locked = null; el.setPointerCapture(e.pointerId); });
  el.addEventListener("pointermove", (e) => {
    if (!on) return; dx = e.clientX - x0; dy = e.clientY - y0;
    if (!locked && Math.hypot(dx, dy) > 8) locked = axis === "x" && Math.abs(dy) > Math.abs(dx) ? "none" : "yes";
    if (locked === "yes") onMove(dx, dy);
  });
  const end = () => { if (!on) return; on = false; onEnd(dx, dy, locked === "yes" || Math.hypot(dx, dy) > 8); };
  el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
}
function bindStack() {
  const c = $(".card.top"); if (!c) return;
  const yes = c.querySelector(".stamp.yes"), no = c.querySelector(".stamp.no");
  drag(c, {
    onMove(dx, dy) {
      c.classList.add("drag"); c.classList.remove("back", "enter", "land");
      c.style.transform = `translate(${dx}px, ${dy * 0.35}px) rotate(${Math.max(-12, Math.min(12, dx / 18))}deg)`;
      yes.style.opacity = Math.max(0, Math.min(1, dx / 90)); no.style.opacity = Math.max(0, Math.min(1, -dx / 90));
    },
    onEnd(dx, dy, moved) {
      c.classList.remove("drag");
      if (!moved) { S.detail = c.dataset.id; haptic("select"); return render(); }
      if (dx > 100) return fly(c, true);
      if (dx < -100) return fly(c, false);
      c.classList.add("back"); c.style.transform = ""; yes.style.opacity = no.style.opacity = 0;
      if (dy < -110 && Math.abs(dx) < 70) { S.detail = c.dataset.id; haptic("select"); render(); }
    },
  });
}
function bindPlanRows() {
  document.querySelectorAll(".rowwrap").forEach((w) => {
    const r = w.querySelector(".prow");
    let suppress = false;
    r.addEventListener("click", (e) => { if (suppress) { e.stopPropagation(); e.preventDefault(); suppress = false; } }, true);
    drag(r, {
      axis: "x",
      onMove(dx) { r.classList.remove("back"); r.style.transform = `translateX(${Math.min(0, dx)}px)`; },
      onEnd(dx, dy, moved) {
        if (moved) suppress = true;
        if (dx < -90) {
          w.classList.add("gone"); haptic("select");
          setTimeout(() => { const id = w.dataset.row; delete S.plan[id]; if (S.decided[id] === 1) delete S.decided[id]; render(); }, 320);
        } else { r.classList.add("back"); r.style.transform = ""; }
      },
    });
  });
}
function bindDetail() {
  const d = $("#detail"); if (!d) return;
  const hero = d.querySelector(".ph.hero");
  if (hero) drag(hero, { onMove(dx, dy) { if (dy > 0) d.style.transform = `translateX(-50%) translateY(${dy}px)`; }, onEnd(dx, dy) { if (dy > 90) closeDetail(); else d.style.transform = ""; } });
}

// ---------- загрузка ----------
async function boot() {
  restore(); render();
  const bust = `?v=${Date.now()}`;
  const [ev, pl] = await Promise.all([
    fetch("data/events.json" + bust).then((r) => r.json()),
    fetch("data/places.json" + bust).then((r) => r.json()).catch(() => ({ places: [] })),
  ]);
  S.events = (ev.events || []).map((e) => ({ ...e, category: CAT[e.category] ? e.category : "other", tags: (e.tags || []).map(noEmoji) }));
  S.places = pl.places || [];
  S.loaded = true;
  render({ enter: "enter" });
}
boot().catch((e) => { $("#app").innerHTML = `<div class="loading">Не удалось загрузить: ${esc(e.message)}</div>`; });
