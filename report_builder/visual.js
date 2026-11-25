/* ---------- Visual layer (Sahaj's walkthrough, 17 Nov 2026) ----------
   1. Source visuals: campaign / ad / social gallery, website screenshots, Xiaohongshu and WeChat pilot, with a lightbox.
   2. Progressive disclosure: explainers behind "How this is measured", long insights clamped with "Read more",
      long tables show 8 rows with "Show all".
   Images come from MEDIA (report_app/prudential/media/media.json), served behind the login at /media/<file>. */
(function () {
  if (typeof MEDIA === "undefined" || !Array.isArray(MEDIA)) window.MEDIA = [];
  const BASE = location.protocol === "file:" ? "../report_app/prudential/media/" : "/media/";
  const BR = ["Prudential", "AIA", "Manulife", "AXA"];
  const BCLS = { Prudential: "pru", AIA: "aia", Manulife: "mfc", AXA: "axa" };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtD = d => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d || ""); return m ? `${+m[3]} ${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+m[2] - 1]} ${m[1]}` : ""; };
  const num = n => n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n || 0);
  const brandsOn = () => (typeof F !== "undefined" && F.brands && F.brands.size) ? BR.filter(b => F.brands.has(b)) : BR;

  function card(x) {
    const eng = x.platform === "YouTube" ? (x.views ? `${num(x.views)} views` : "") : x.likes ? `♥ ${num(x.likes)}${x.comments ? ` · 💬 ${num(x.comments)}` : ""}` : "";
    return `<figure class="vg-card" data-i="${MEDIA.indexOf(x)}" tabindex="0">
      <div class="vg-img"><img loading="lazy" src="${BASE}${esc(x.file)}" alt="${esc(x.brand)} ${esc(x.platform)} ${esc(x.kind)}">
        <span class="vg-badge">${esc(x.platform)}${x.kind === "video" ? " ▶" : ""}</span></div>
      <figcaption><div class="vg-meta"><b class="bp-${x.brand.toLowerCase()}">${esc(x.brand)}</b><span>${esc(fmtD(x.date))}</span></div>
        <p>${esc(x.title || x.text)}</p>${eng || x.cta ? `<div class="vg-eng">${esc(eng)}${x.cta ? `<span class="vg-cta">${esc(x.cta)}</span>` : ""}</div>` : ""}</figcaption></figure>`;
  }

  function gallery(host, platforms, opts = {}) {
    const el = document.createElement("div");
    el.className = "vg reveal in";
    el.innerHTML = `<div class="vg-head"><h3 id="${opts.id}">${opts.title}</h3><p class="muted small">${opts.sub}</p>
      <div class="seg vg-tabs">${platforms.map((p, i) => `<button type="button" class="${i ? "" : "on"}" data-p="${p}">${p}</button>`).join("")}</div></div>
      <div class="vg-grid"></div>`;
    host.insertAdjacentElement(opts.where || "afterend", el);
    let plat = platforms[0];
    const draw = () => {
      const on = brandsOn();
      el.querySelector(".vg-grid").innerHTML = on.map(b => {
        const xs = MEDIA.filter(x => x.brand === b && x.platform === plat).slice(0, opts.per || 6);
        return `<div class="vg-col"><div class="vg-colh b-${BCLS[b]}">${b}<small>${xs.length ? `${xs.length} shown` : "none in this period"}</small></div>${xs.map(card).join("")}</div>`;
      }).join("");
    };
    el.querySelector(".vg-tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
      plat = b.dataset.p; el.querySelectorAll(".vg-tabs button").forEach(x => x.classList.toggle("on", x === b)); draw(); });
    draw();
    document.addEventListener("brandfocus", draw);
    return draw;
  }

  function strip(host, filter, opts) {
    const xs = MEDIA.filter(filter);
    if (!xs.length) return;
    const el = document.createElement("div");
    el.className = "vg reveal in";
    el.innerHTML = `<div class="vg-head"><h3 id="${opts.id}">${opts.title}${opts.pilot ? ' <span class="vg-pilot">Pilot</span>' : ""}</h3><p class="muted small">${opts.sub}</p></div>
      <div class="vg-strip ${opts.wide ? "wide" : ""}"></div>`;
    host.insertAdjacentElement(opts.where || "afterend", el);
    const draw = () => { const on = brandsOn(); el.querySelector(".vg-strip").innerHTML = xs.filter(x => on.includes(x.brand)).map(card).join(""); };
    draw();
    document.addEventListener("brandfocus", draw);
  }

  // lightbox: the full image, the full caption and the link to the original
  const lb = document.createElement("div");
  lb.className = "vg-lb"; lb.hidden = true;
  lb.innerHTML = `<div class="vg-lb-box" role="dialog" aria-modal="true" aria-label="Source image"><button type="button" class="vg-lb-x" aria-label="Close">×</button>
    <img alt=""><div class="vg-lb-txt"></div></div>`;
  document.body.appendChild(lb);
  const openLb = i => { const x = MEDIA[i]; if (!x) return;
    lb.querySelector("img").src = BASE + x.file; lb.querySelector("img").alt = `${x.brand} ${x.platform}`;
    lb.querySelector(".vg-lb-txt").innerHTML = `<div class="vg-meta"><b class="bp-${x.brand.toLowerCase()}">${esc(x.brand)}</b> · ${esc(x.platform)} · ${esc(fmtD(x.date))}${x.captured ? ` · screenshot taken ${esc(x.captured)}` : ""}</div>
      <p>${esc(x.text)}</p>${x.url ? `<div class="lb-acts"><button type="button" class="btn primary lb-ev" data-href="${esc(x.url)}" data-label="${esc(x.brand + " " + x.platform)}">Open evidence record →</button><a class="small" href="${esc(x.url)}" target="_blank" rel="noopener">Open the original ↗</a></div>` : ""}
      ${x.pilot ? '<p class="muted small">Pilot collection (19 Nov 2026): found by searching the insurer\'s name; not yet part of the counts.</p>' : ""}`;
    lb.dataset.href = x.url || ""; lb.dataset.label = `${x.brand} ${x.platform}`;
    lb.hidden = false; lb.querySelector(".vg-lb-x").focus(); };
  // the evidence record (bigger picture, full detail and the source link) rather than straight to the source (20 Nov 2026)
  lb.addEventListener("click", e => { const b = e.target.closest(".lb-ev") || (e.target.matches(".vg-lb-box > img") && lb.dataset.href ? e.target : null);
    if (!b || typeof window.routeEv !== "function") return; lb.hidden = true; window.routeEv(lb.dataset.href, lb.dataset.label); });
  document.addEventListener("click", e => { const c = e.target.closest(".vg-card"); if (c) openLb(+c.dataset.i);
    if (e.target === lb || e.target.closest(".vg-lb-x")) lb.hidden = true; });
  document.addEventListener("keydown", e => { if (e.key === "Escape") lb.hidden = true;
    if (e.key === "Enter" && e.target.classList?.contains("vg-card")) openLb(+e.target.dataset.i); });

  // ---------- 1. place the visuals ----------
  const p3ins = document.querySelector("#p3 .insight");
  if (p3ins && MEDIA.some(x => ["Meta ad", "Instagram", "Facebook", "YouTube"].includes(x.platform)))
    gallery(p3ins, ["Meta ad", "Instagram", "Facebook", "YouTube"].filter(p => MEDIA.some(x => x.platform === p)), { id: "gallery",
      title: "What each brand is posting and advertising",
      sub: "Snapshots of the insurers' own ads (Meta Ad Library) and their most engaging recent posts, Jun – Oct 2026. Click a card to see it large and open the original." });
  const prof = document.querySelector("#profiles-v #coCmp")?.closest(".tbl-wrap");
  if (prof) strip(prof, x => x.platform === "Website" && /home/.test(x.file), { id: "sites", wide: true,
    title: "Their websites today", sub: "Home page of each insurer's Hong Kong site, as a visitor sees it (screenshots taken by this monitor)." });
  const p4ins = document.querySelector("#p4 .insight");
  if (p4ins) strip(p4ins, x => x.platform === "Website" && /health/.test(x.file), { id: "hciShots", wide: true,
    title: "Health and critical illness pages today", sub: "Each insurer's own health or critical illness product page (screenshots taken by this monitor)." });
  // (20 Nov 2026) the Xiaohongshu / WeChat pilot strip is replaced by the full section (cnsoc.js)

  // ---------- 2. progressive disclosure ----------
  // explainers: one line "How this is measured", text on click (short ones stay visible)
  document.querySelectorAll("section.view p.muted.small").forEach((p, n) => {
    if (p.closest(".vg, .cogrid, .insight, table, .modal") || p.textContent.trim().length < 160) return;
    const id = "xp" + n, b = document.createElement("button");
    b.type = "button"; b.className = "pd-more"; b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", id);
    b.textContent = "ⓘ How to read this";
    p.id = p.id || id; p.classList.add("pd-hide");
    p.insertAdjacentElement("beforebegin", b);
    b.addEventListener("click", () => { const open = p.classList.toggle("pd-hide") === false; b.setAttribute("aria-expanded", open); b.textContent = open ? "ⓘ Hide" : "ⓘ How to read this"; });
  });
  // long insights: headline first (3 lines), the rest on click
  const clampIns = () => document.querySelectorAll(".insight > p").forEach(p => {
    if (p.dataset.pd || p.textContent.length < 260) return;
    p.dataset.pd = "1"; p.classList.add("pd-clamp");
    const b = document.createElement("button"); b.type = "button"; b.className = "pd-more pd-ins"; b.textContent = "Read more";
    p.insertAdjacentElement("afterend", b);
    b.addEventListener("click", () => { const open = p.classList.toggle("pd-clamp") === false; b.textContent = open ? "Show less" : "Read more"; });
  });
  // long tables: first 8 rows, then "Show all"
  const LIMIT = 8;
  const fold = tb => {
    const rows = [...tb.rows].filter(r => !r.classList.contains("pd-ctl"));
    const ctl = tb.querySelector("tr.pd-ctl");
    if (rows.length <= LIMIT + 2 || tb.dataset.pdAll === "1") { ctl?.remove(); rows.forEach(r => r.classList.remove("pd-row-hide")); return; }
    rows.forEach((r, i) => r.classList.toggle("pd-row-hide", i >= LIMIT));
    // keep the existing control when nothing changed: re-creating it fired the watcher again, every frame, and a real
    // click (press and release on the same button) could never land (fixed 20 Nov 2026)
    if (ctl && ctl === tb.lastElementChild && ctl.dataset.n === String(rows.length)) return;
    ctl?.remove();
    const tr = document.createElement("tr"); tr.className = "pd-ctl"; tr.dataset.n = String(rows.length);
    tr.innerHTML = `<td colspan="${rows[0].cells.length || 1}"><button type="button" class="pd-more">Show all ${rows.length} rows ▾</button></td>`;
    tr.querySelector("button").addEventListener("click", () => { tb.dataset.pdAll = "1"; fold(tb); });
    tb.appendChild(tr);
  };
  const watch = () => document.querySelectorAll("section.view table tbody").forEach(tb => {
    if (tb.dataset.pdw || tb.closest("#evTbl, .ev-list")) return;
    tb.dataset.pdw = "1";
    let busy = false;
    new MutationObserver(() => { if (busy) return; busy = true; requestAnimationFrame(() => { fold(tb); busy = false; }); }).observe(tb, { childList: true });
    fold(tb);
  });
  setTimeout(() => { clampIns(); watch(); }, 400);
  document.addEventListener("click", e => { if (e.target.closest("nav a, [data-view]")) setTimeout(() => { clampIns(); watch(); }, 300); });

  // the brand filter changes (brand chips, Reset, "all brands" links): redraw the galleries for the chosen brands
  document.addEventListener("click", e => { if (e.target.closest("#fbar, [data-allbrands]")) setTimeout(() => document.dispatchEvent(new Event("brandfocus")), 60); });
})();
