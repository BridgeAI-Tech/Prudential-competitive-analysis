/* ---------- Image-first cards and the detail panel (20 Nov 2026) ----------
   1. EVIMG(url, id): the best picture we hold for a source (news lead image, page screenshot, cited report page,
      live capture or gallery image); used by the Evidence library's record cards.
   2. routeEv(url, label): opens that source's record in the Evidence library (bigger picture, full detail, original link).
   3. Compact cards: takeaways, strengths / weaknesses and the timeline board show the picture, the company and the key
      line only; a tap opens the detail panel with the full (unchanged) explanation. Pictures lead to the evidence record. */
(function () {
  const base = typeof MEDIA_BASE !== "undefined" ? MEDIA_BASE : "/media/";
  const shots = typeof MOVESHOT !== "undefined" ? MOVESHOT : {};
  const news = typeof NEWSIMG !== "undefined" ? NEWSIMG : {};
  const byUrl = new Map();
  (typeof CAPTURES !== "undefined" ? CAPTURES : []).forEach(c => c.url && !byUrl.has(c.url) && byUrl.set(c.url, c.file));
  (typeof MEDIA !== "undefined" ? MEDIA : []).forEach(m => m.url && !byUrl.has(m.url) && byUrl.set(m.url, m.file));
  const rec = {}; if (typeof EVID !== "undefined") EVID.forEach(r => { if (r[10] && !rec[r[10]]) rec[r[10]] = r[0]; });
  const strip = u => String(u || "").split("#")[0].replace(/\/$/, "");
  window.EVIMG = (u, id) => {
    const f = (id && news[id]) || (id && typeof EVIMGMAP !== "undefined" && EVIMGMAP[id]) || shots[u] || shots[strip(u)] || (rec[u] && news[rec[u]]) || byUrl.get(u) || byUrl.get(strip(u));
    return f ? base + f : "";
  };
  window.routeEv = (href, label) => {
    if (!href) return;
    try {
      const k = normU(href), ids = EVURL.get(k);
      goEvidence(ids ? { title: label || href, ids: new Set(ids), single: true } : { title: label || href, doc: k, url: href, single: true });
    } catch (e) { open(href, "_blank", "noopener"); }
  };
  if (typeof drawEvFocus === "function") try { drawEvFocus(); } catch (e) { /* not open yet */ }
  if (typeof drawExplorer === "function") try { drawExplorer(); } catch (e) { /* not drawn yet */ }   // evidence rows now get their pictures

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- the detail panel
  const sh = document.createElement("div");
  sh.className = "dsheet"; sh.hidden = true;
  sh.innerHTML = `<div class="ds-panel" role="dialog" aria-modal="true" aria-label="Detail"><div class="ds-head"><button type="button" class="btn ds-back" aria-label="Back">← Back</button><button type="button" class="ds-x" aria-label="Close">×</button></div><div class="ds-body"></div></div>`;
  document.body.appendChild(sh);
  const body = sh.querySelector(".ds-body");
  let lastFocus = null;
  const close = () => { sh.hidden = true; document.documentElement.classList.remove("ds-open"); lastFocus?.focus?.(); };
  window.closeSheet = close;
  function openSheet({ img, href, label, meta, title, html, actions }) {
    lastFocus = document.activeElement;
    body.innerHTML = `${img ? `<figure class="ds-img" data-href="${esc(href || "")}" data-label="${esc(label || "")}" title="${href ? "Open the evidence record" : ""}"><img src="${img}" alt="">${href ? '<figcaption>Open the evidence record →</figcaption>' : ""}</figure>` : ""}
      <div class="ds-meta">${meta || ""}</div><h3 class="ds-title">${title || ""}</h3><div class="ds-content">${html || ""}</div>
      <div class="ds-acts">${actions || ""}</div>`;
    sh.hidden = false; document.documentElement.classList.add("ds-open");
    sh.querySelector(".ds-x").focus();
  }
  sh.addEventListener("click", e => {
    if (e.target === sh || e.target.closest(".ds-x, .ds-back")) return close();
    const fig = e.target.closest(".ds-img[data-href]");
    if (fig && fig.dataset.href) { close(); return window.routeEv(fig.dataset.href, fig.dataset.label); }
    const act = e.target.closest("[data-act]");
    if (act) { close(); return ACTS[act.dataset.act]?.(act.dataset.arg); }
    const a = e.target.closest("a[href]"); if (!a) return;
    const h = a.getAttribute("href");
    if (/^https?:/i.test(h)) { if (e.ctrlKey || e.metaKey || e.shiftKey) return; e.preventDefault(); close(); window.routeEv(h, a.textContent.trim()); }
    else if (h.startsWith("#")) { e.preventDefault(); close(); try { goTo(h); } catch (x) { location.hash = h; } }
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !sh.hidden) close(); });
  const ACTS = {
    ins: i => { try { goTo(`#ins${+i + 1}`); } catch (e) { location.hash = `#ins${+i + 1}`; } },
    recs: i => { const x = INSIGHTS[+i]; if (x && typeof openDrawer === "function" && typeof evidFor === "function") openDrawer(`Insight ${+i + 1}: supporting records`, x.t, evidFor(x)); },
    src: u => window.routeEv(u),
  };

  window.openSheet = openSheet; window.SHEET_ACTS = ACTS;   // used by modcards.js (module cards)

  // ---- picture element of a card -> not a link (the card opens the panel; the panel's picture opens the evidence)
  const pic = card => {
    const a = card.querySelector(":scope > a.ov-img, :scope > a.cp-img, :scope > a.mshot");
    if (!a) return { img: "", href: "", label: "" };
    const img = a.querySelector("img")?.getAttribute("src") || "", href = a.getAttribute("href"), label = a.querySelector(".ov-img-src")?.textContent || "";
    const d = document.createElement("div"); d.className = a.className; d.innerHTML = a.innerHTML; a.replaceWith(d);
    return { img, href, label };
  };
  const compact = (card, open) => {
    if (card.dataset.cmp) return; card.dataset.cmp = "1";
    const p = pic(card);
    card.classList.add("cmp"); card.tabIndex = 0; card.setAttribute("role", "button");
    card.insertAdjacentHTML("beforeend", '<span class="cmp-more">Tap for detail →</span>');
    const go = () => open(card, p);
    card.addEventListener("click", e => { if (e.target.closest("a[href^='#']")) return; go(); });
    card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  };
  const clean = el => { const c = el.cloneNode(true); c.querySelectorAll(".cp-img, .ov-img, .mshot, .cmp-more, .ins-path, details.more").forEach(x => x.remove()); return c.innerHTML; };

  // 1. executive takeaways -> the full insight (four boxes) in the panel
  // InkTank structure (operator, 20 Nov 2026): picture, tags + source count, title, short summary, recommendation box,
  // then "Inspect evidence →" (the supporting records) and "View lineage →" (the full insight in the panel)
  const openIns = (c, p) => {
    const i = +c.querySelector(".ov-go")?.dataset.kd, x = INSIGHTS[i], full = document.getElementById(`ins${i + 1}`);
    openSheet({ img: p.img, href: p.href, label: (x?.t || "").replace(/<[^>]+>/g, ""), meta: c.querySelector(".ov-meta")?.outerHTML || "",
      title: esc(x?.t ? x.t.replace(/<[^>]+>/g, "") : c.querySelector("h4")?.textContent),
      html: full ? `<div class="ins-grid">${clean(full.querySelector(".ins-grid") || full)}</div>` : "",
      actions: `${x?.ins ? `<button type="button" class="btn primary" data-act="recs" data-arg="${i}">Open the supporting records</button>` : ""}
        <button type="button" class="btn" data-act="ins" data-arg="${i}">Open in Insights</button>` });
  };
  document.querySelectorAll(".ov-cards .ov-card").forEach(card => {
    if (card.dataset.ink) return; card.dataset.ink = "1";
    const i = +card.querySelector(".ov-go")?.dataset.kd, x = INSIGHTS[i];
    const a = card.querySelector(":scope > a.ov-img");
    const p = { img: a?.querySelector("img")?.getAttribute("src") || "", href: a?.getAttribute("href") || "", label: "" };
    // how many distinct sources the finding cites (InkTank's "3+ cuts")
    const n = x ? new Set([...[x.finding, x.compare, x.means, x.act].join(" ").matchAll(/href="(https?:[^"]+)"/g)].map(m => m[1].split("#")[0])).size : 0;
    if (n) card.querySelector(".ov-meta")?.insertAdjacentHTML("beforeend", `<span class="ov-cuts">${n} source${n === 1 ? "" : "s"}</span>`);
    card.insertAdjacentHTML("beforeend", `<div class="ov-foot"><button type="button" class="ov-insp">Inspect evidence →</button><button type="button" class="ov-lin">View lineage →</button></div>`);
    card.querySelector(".ov-insp").addEventListener("click", () => {
      if (x?.ins && typeof openDrawer === "function" && typeof evidFor === "function") openDrawer(`Insight ${i + 1}: supporting records`, x.t, evidFor(x));
      else if (p.href) window.routeEv(p.href, (x?.t || "").replace(/<[^>]+>/g, ""));
    });
    card.querySelector(".ov-lin").addEventListener("click", () => openIns(card, p));
    card.querySelector("h4")?.addEventListener("click", () => openIns(card, p));
    if (card.querySelector("h4")) card.querySelector("h4").style.cursor = "pointer";
  });
  // 2. strengths and weaknesses
  document.querySelectorAll("#swS .swi, #swW .swi").forEach(card => compact(card, (c, p) => {
    const strong = !!c.closest("#swS");
    openSheet({ img: p.img, href: p.href, label: c.querySelector(".h")?.textContent || p.label,
      meta: `<span class="ds-tag ${strong ? "good" : "bad"}">${strong ? "Strongest point" : "Weakest point"}</span><span class="ds-tag">${esc(c.querySelector(".a")?.textContent)}</span>`,
      title: esc(c.querySelector(".h")?.textContent), html: (() => { const k = c.cloneNode(true); k.querySelectorAll(".a, .h, .cp-img, .cmp-more").forEach(x => x.remove()); return k.innerHTML; })(),
      actions: p.href ? `<button type="button" class="btn primary" data-act="src" data-arg="${esc(p.href)}">Open the evidence record</button>` : "" });
  }));
  // 3. timeline board (re-drawn by the filters, so watch it)
  const board = document.getElementById("tlBoard");
  const doBoard = () => board && board.querySelectorAll(".mcard").forEach(card => compact(card, (c, p) => {
    const brand = c.closest(".mcol")?.querySelector("h4 span")?.textContent || "", src = c.querySelector(".ms a");
    const href = p.href || src?.getAttribute("href") || "";
    openSheet({ img: p.img, href, label: src?.textContent || "",
      meta: `${brand ? `<span class="bp-pill bp-${brand.toLowerCase()}">${esc(brand)}</span>` : ""}${c.querySelector(".md")?.innerHTML || ""}`,
      title: esc(c.querySelector(".mh")?.textContent), html: c.querySelector(".ms") ? `<p class="small">Source: ${c.querySelector(".ms").innerHTML}</p>` : "",
      actions: href ? `<button type="button" class="btn primary" data-act="src" data-arg="${esc(href)}">Open the evidence record</button>` : "" });
  }));
  doBoard();

  // 4. Insights tab, "Key insight from each module": a picture from the records behind each module's key insight
  //    (the same records its Evidence button opens; newest first), else the module's newest news / newsroom record
  (() => {
    const MODS = [["M1", "p2"], ["M2", "p3"], ["M3", "p4"], ["M4", "p5"]], used = new Set(), usedT = [];
    const ttl = {}; EVID.forEach(r => { if (r[10] && !ttl[r[10]]) ttl[r[10]] = (TT(r).o + " " + (typeof ENS !== "undefined" && ENS[r[0]] ? ENS[r[0]] : "")).toLowerCase(); });
    const kw = t => new Set(String(t || "").toLowerCase().match(/[a-z]{5,}/g) || []);
    // the same story from two outlets: most of its title words already used by another row
    const recOf = {}; EVID.forEach(r => { if (r[10] && !recOf[r[10]]) recOf[r[10]] = r; });
    const usedR = [], day = d => { const s = String(d); return Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8)) / 864e5; };
    // the same story: most title words shared, or the same insurer within three days (two outlets, one press event)
    const sameStory = (t, u) => { const a = kw(t), r = recOf[u];
      if (r && usedR.some(([b, d]) => b === r[2] && Math.abs(day(d) - day(r[1])) <= 3)) return true;
      return a.size && usedT.some(b => { let n = 0; a.forEach(w => b.has(w) && n++); return n / a.size > .5; }); };
    const plan = [...document.querySelectorAll("#modIns tbody tr")].map((tr, j) => {
      const [m, sec] = MODS[j] || []; if (!m || tr.querySelector(".mi-pic")) return null;
      const cands = [];
      try {
        const box = document.querySelector(`#${sec} .insight`), ev = box ? evForBox(box) : null;
        if (ev) {
          EVID.filter(r => ev.ids.has(r[0])).sort((a, b) => b[1] - a[1]).forEach(r => cands.push([window.EVIMG(r[10], r[0]), r[10], TT(r).o]));
          const cd = citedDocs(); ev.docs.forEach(k => { const d = cd.get(k); if (d) cands.push([window.EVIMG(d.url), d.url, ""]); });
        }
      } catch (e) { /* fall back below */ }
      EVID.filter(r => r[5].includes(m) && r[1] >= 20251101 && r[1] <= 20261031 && (r[8] === "Media" || r[8] === "Official site"))
        .sort((a, b) => b[1] - a[1]).forEach(r => cands.push([window.EVIMG(r[10], r[0]), r[10], ""]));
      // relevance: how many of the insight's own key words appear in the source's title / summary
      const STOP = new Set("about after their there which while these those other first since every would could being still more most than with from into over only also have this that were where what when".split(" "));
      const words = new Set(((tr.cells[1].querySelector("b, strong, mark")?.textContent || "") + " " + tr.cells[1].textContent).toLowerCase().match(/[a-z]{5,}/g)?.filter(w => !STOP.has(w)) || []);
      const score = x => { const t = ttl[x[1]] || String(x[2] || "").toLowerCase(); let n = 0; words.forEach(w => { if (t.includes(w)) n++; }); return n; };
      cands.forEach((x, k) => { x.s = score(x); x.k = k; });
      cands.sort((a, b) => b.s - a.s || a.k - b.k);
      return { tr, cands: cands.filter(x => x[0] && !/news\.google\./.test(x[1])) };
    }).filter(Boolean);
    // the row with the strongest match picks first, so a closely matching story goes to the row it is about
    plan.sort((a, b) => (b.cands[0]?.s || 0) - (a.cands[0]?.s || 0)).forEach(({ tr, cands }) => {
      const c = cands.find(x => !used.has(x[0]) && !sameStory(ttl[x[1]] || x[2], x[1])); if (!c) return;
      used.add(c[0]); usedT.push(kw(ttl[c[1]] || c[2])); if (recOf[c[1]]) usedR.push([recOf[c[1]][2], recOf[c[1]][1]]);
      const host = (String(c[1]).split("/")[2] || "").replace(/^www\./, "");
      tr.cells[1].insertAdjacentHTML("afterbegin", `<span class="mi-pic" role="button" tabindex="0" title="Open the evidence record" data-href="${esc(c[1])}" data-label="${esc(c[2] || host)}"><img loading="lazy" src="${c[0]}" alt=""><span class="ov-img-src">${esc(host)}</span></span>`);
    });
    const tb = document.querySelector("#modIns");
    const go = e => { const p = e.target.closest(".mi-pic"); if (!p) return; e.preventDefault(); e.stopPropagation(); window.routeEv(p.dataset.href, p.dataset.label); };
    tb?.addEventListener("click", go, true);
    tb?.addEventListener("keydown", e => { if (e.key === "Enter") go(e); }, true);
  })();
  if (board) new MutationObserver(doBoard).observe(board, { childList: true, subtree: true });
})();

/* ---------- Strengths and Gaps: equal card heights so both columns line up row by row (24 Nov 2026) ---------- */
(function () {
  const sel = "#swS .swi.cmp, #swW .swi.cmp";
  let busy = false;
  const even = () => {
    if (busy) return; busy = true;
    requestAnimationFrame(() => {
      const cards = [...document.querySelectorAll(sel)].filter(c => c.offsetParent);
      if (cards.length) {
        cards.forEach(c => { c.style.minHeight = ""; });
        const tall = Math.max(...cards.map(c => c.getBoundingClientRect().height));
        cards.forEach(c => { c.style.minHeight = tall + "px"; });
      }
      busy = false;
    });
  };
  const start = () => {
    const cols = ["#swS", "#swW"].map(s => document.querySelector(s)).filter(Boolean);
    if (!cols.length) return setTimeout(start, 500);
    if (window.ResizeObserver) cols.forEach(c => new ResizeObserver(() => { if (!busy) even(); }).observe(c));
    window.addEventListener("resize", even);
    document.addEventListener("load", e => { if (e.target.tagName === "IMG" && e.target.closest(sel)) even(); }, true);
    even();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
