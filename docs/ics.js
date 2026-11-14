// Календарь: файл .ics (Apple/Google/Outlook) и ссылка «Добавить в Google Calendar».
// Время «плавающее» (без часового пояса): календарь трактует его как локальное, то есть пражское.
(function () {
  const pad = (n) => String(n).padStart(2, "0");
  const dstr = (iso) => iso.replace(/-/g, "");
  const esc = (s) => String(s || "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

  function fold(line) {            // строки .ics не длиннее 75 октетов (режем по символам — для кириллицы с запасом)
    const out = []; let cur = "";
    for (const ch of line) {
      if ((cur + ch).length > 60) { out.push(cur); cur = " " + ch; } else cur += ch;
    }
    out.push(cur);
    return out.join("\r\n");
  }

  function addMinutes(iso, hhmm, minutes) {
    const [h, m] = hhmm.split(":").map(Number);
    const t = new Date(`${iso}T${pad(h)}:${pad(m)}:00`);
    t.setMinutes(t.getMinutes() + minutes);
    return `${t.getFullYear()}${pad(t.getMonth() + 1)}${pad(t.getDate())}T${pad(t.getHours())}${pad(t.getMinutes())}00`;
  }

  // item: {uid, title, date:'YYYY-MM-DD', time:'HH:MM'|null, minutes, location, description, url}
  function vevent(it) {
    const L = ["BEGIN:VEVENT", `UID:${it.uid}@weekend-prague`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`];
    if (it.time) {
      L.push(`DTSTART:${dstr(it.date)}T${it.time.replace(":", "")}00`);
      L.push(`DTEND:${addMinutes(it.date, it.time, it.minutes || 120)}`);
    } else {
      const next = new Date(it.date + "T12:00:00"); next.setDate(next.getDate() + 1);
      L.push(`DTSTART;VALUE=DATE:${dstr(it.date)}`);
      L.push(`DTEND;VALUE=DATE:${next.getFullYear()}${pad(next.getMonth() + 1)}${pad(next.getDate())}`);
    }
    L.push(`SUMMARY:${esc(it.title)}`);
    if (it.location) L.push(`LOCATION:${esc(it.location)}`);
    const desc = [it.description, it.url].filter(Boolean).join("\n");
    if (desc) L.push(`DESCRIPTION:${esc(desc)}`);
    L.push("BEGIN:VALARM", "TRIGGER:-PT2H", "ACTION:DISPLAY", `DESCRIPTION:${esc(it.title)}`, "END:VALARM", "END:VEVENT");
    return L.map(fold).join("\r\n");
  }

  function build(items) {
    return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//weekend-prague//RU", "CALSCALE:GREGORIAN", ...items.map(vevent), "END:VCALENDAR"].join("\r\n") + "\r\n";
  }

  function googleUrl(it) {
    const start = it.time ? `${dstr(it.date)}T${it.time.replace(":", "")}00` : dstr(it.date);
    let end;
    if (it.time) end = addMinutes(it.date, it.time, it.minutes || 120);
    else { const n = new Date(it.date + "T12:00:00"); n.setDate(n.getDate() + 1); end = `${n.getFullYear()}${pad(n.getMonth() + 1)}${pad(n.getDate())}`; }
    const p = new URLSearchParams({
      action: "TEMPLATE", text: it.title, dates: `${start}/${end}`,
      details: [it.description, it.url].filter(Boolean).join("\n"), location: it.location || "", ctz: "Europe/Prague",
    });
    return "https://calendar.google.com/calendar/render?" + p.toString();
  }

  function download(filename, text) {
    const blob = new Blob([text], { type: "text/calendar;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  window.ICS = { build, googleUrl, download };
})();
