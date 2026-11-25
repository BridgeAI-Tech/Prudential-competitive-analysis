/* ---------- Interactive layer (20 Nov 2026): Stitch screen "Findings explorer" + Penpot board "Prudential CI — interactive UI" ----------
   Front end only: no insight text is changed. Existing insight cards are re-hosted in a master/detail explorer,
   plus a command palette (Ctrl+K or /), a reading-progress bar, animated KPI numbers and a back-to-top button. */
(function () {
  const q = (s, r = document) => r.querySelector(s), qa = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const plain = h => { const d = document.createElement("div"); d.innerHTML = h; return d.textContent.trim(); };
  const INS = typeof INSIGHTS !== "undefined" ? INSIGHTS : [];

  /* 1. Findings explorer: list on the left, the full (unchanged) insight card on the right */
  const host = q("#insights");
  if (host && INS.length) {
    const cards = qa(".card.ins", host);
    const wrap = document.createElement("div");
    wrap.className = "fx";
    wrap.innerHTML = `<div class="fx-bar">
        <div class="fx-seg" role="tablist" aria-label="Layout"><button type="button" data-mode="explore" class="on">Explorer</button><button type="button" data-mode="cards">All cards</button></div>
        <div class="fx-seg fx-conf" aria-label="Confidence"><button type="button" data-c="All" class="on">All</button><button type="button" data-c="High">High</button><button type="button" data-c="Medium">Medium</button></div>
        <label class="fx-search"><span aria-hidden="true">⌕</span><input type="search" placeholder="Filter findings" aria-label="Filter findings"></label>
        <span class="fx-pos mono"></span></div>
      <div class="fx-body"><ol class="fx-list" role="listbox" aria-label="Findings"></ol><div class="fx-pane" aria-live="polite"></div></div>`;
    host.parentNode.insertBefore(wrap, host);
    const list = q(".fx-list", wrap), pane = q(".fx-pane", wrap);
    pane.appendChild(host);
    list.innerHTML = INS.map((x, i) => `<li role="option" tabindex="-1" data-i="${i}">
        <span class="fx-no mono">#${String(i + 1).padStart(2, "0")}</span>
        <span class="fx-t">${esc(plain(x.t))}</span>
        <span class="fx-tags"><span class="fx-chip fx-${String(x.conf).toLowerCase()}">${esc(x.conf)}</span><span class="fx-mods">${esc(plain(x.mods || ""))}</span></span></li>`).join("");
    let mode = "explore", cur = 0, conf = "All", term = "";
    const visible = () => INS.map((x, i) => i).filter(i => (conf === "All" || INS[i].conf === conf) &&
      (!term || plain(INS[i].t + " " + INS[i].finding + " " + INS[i].compare + " " + INS[i].act).toLowerCase().includes(term)));
    const draw = () => {
      const vis = visible();
      if (!vis.includes(cur) && vis.length) cur = vis[0];
      qa("li", list).forEach(li => { const i = +li.dataset.i; li.hidden = !vis.includes(i); li.classList.toggle("on", i === cur); li.setAttribute("aria-selected", i === cur); });
      cards.forEach((c, i) => { c.hidden = mode === "explore" ? i !== cur || !vis.length : !vis.includes(i); if (!c.hidden) c.classList.add("in"); });
      wrap.classList.toggle("fx-cards", mode === "cards");
      q(".fx-pos", wrap).textContent = vis.length ? (mode === "explore" ? `${vis.indexOf(cur) + 1} / ${vis.length}` : `${vis.length} shown`) : "no match";
    };
    const pick = (i, focus) => { cur = i; draw(); if (focus) q(`li[data-i="${i}"]`, list)?.focus(); if (mode === "explore" && innerWidth < 900) pane.scrollIntoView({ behavior: "smooth", block: "start" }); };
    list.addEventListener("click", e => { const li = e.target.closest("li"); if (li) pick(+li.dataset.i); });
    list.addEventListener("keydown", e => {
      const vis = visible(), k = vis.indexOf(cur);
      if (e.key === "ArrowDown" && k < vis.length - 1) { e.preventDefault(); pick(vis[k + 1], true); }
      if (e.key === "ArrowUp" && k > 0) { e.preventDefault(); pick(vis[k - 1], true); }
    });
    wrap.addEventListener("click", e => {
      const m = e.target.closest("[data-mode]"), c = e.target.closest(".fx-conf [data-c]");
      if (m) { mode = m.dataset.mode; qa("[data-mode]", wrap).forEach(b => b.classList.toggle("on", b === m)); draw(); }
      if (c) { conf = c.dataset.c; qa(".fx-conf button", wrap).forEach(b => b.classList.toggle("on", b === c)); draw(); }
    });
    q(".fx-search input", wrap).addEventListener("input", e => { term = e.target.value.trim().toLowerCase(); draw(); });
    // the executive summary's "Open →" buttons jump to #insN: select it in the explorer first
    const sync = () => { const m = /^#ins(\d+)$/.exec(location.hash); if (m) pick(+m[1] - 1); };
    document.addEventListener("click", e => { const b = e.target.closest("#kd button[data-i], .ov-go"); if (b && b.dataset.i != null) pick(+b.dataset.i); }, true);
    addEventListener("hashchange", sync);
    draw(); sync();
  }

  /* 2. Command palette: Ctrl+K or "/" — jump to any page, section heading or finding */
  const nav = qa("nav.toc.dnav a[href^='#']").filter(a => !a.hasAttribute("data-open-chat"));
  const heads = qa("main section.view h2[id], main section.view h3[id], main section.view [id].card > h3").slice(0, 120);
  const entries = [
    ...nav.map(a => ({ kind: "Page", label: a.textContent.replace(/^\s*\S\s*/, "").trim() || a.textContent.trim(), run: () => a.click() })),
    ...INS.map((x, i) => ({ kind: `Finding #${String(i + 1).padStart(2, "0")}`, label: plain(x.t), run: () => { location.hash = `#ins${i + 1}`; if (typeof goTo === "function") goTo(`#ins${i + 1}`); } })),
    ...heads.map(h => ({ kind: "Section", label: h.textContent.trim().slice(0, 90), run: () => (typeof goTo === "function" ? goTo("#" + h.id) : h.scrollIntoView()) })),
  ].filter(e => e.label);
  const pal = document.createElement("div");
  pal.className = "cp"; pal.hidden = true;
  pal.innerHTML = `<div class="cp-box" role="dialog" aria-modal="true" aria-label="Go to"><label class="cp-in"><span aria-hidden="true">⌕</span>
      <input type="text" placeholder="Jump to a page, section or finding…" aria-label="Jump to"><kbd>Esc</kbd></label><ul class="cp-list" role="listbox"></ul>
      <div class="cp-foot mono">↑ ↓ to move · Enter to open · Ctrl K anywhere</div></div>`;
  document.body.appendChild(pal);
  const inp = q("input", pal), ul = q(".cp-list", pal);
  let hits = [], sel = 0;
  const render = () => {
    const t = inp.value.trim().toLowerCase();
    hits = (t ? entries.filter(e => (e.label + " " + e.kind).toLowerCase().includes(t)) : entries.filter(e => e.kind !== "Section")).slice(0, 12);
    sel = Math.min(sel, Math.max(hits.length - 1, 0));
    ul.innerHTML = hits.map((e, i) => `<li role="option" data-k="${i}" class="${i === sel ? "on" : ""}"><span class="cp-kind mono">${esc(e.kind)}</span><span>${esc(e.label)}</span></li>`).join("")
      || `<li class="cp-none">Nothing matches.</li>`;
  };
  const openP = () => { pal.hidden = false; inp.value = ""; sel = 0; render(); inp.focus(); };
  const closeP = () => { pal.hidden = true; };
  const go = i => { const e = hits[i]; if (!e) return; closeP(); e.run(); };
  inp.addEventListener("input", () => { sel = 0; render(); });
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, hits.length - 1); render(); }
    if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); render(); }
    if (e.key === "Enter") { e.preventDefault(); go(sel); }
  });
  pal.addEventListener("click", e => { const li = e.target.closest("li[data-k]"); if (li) go(+li.dataset.k); else if (e.target === pal) closeP(); });
  document.addEventListener("keydown", e => {
    const typing = /input|textarea|select/i.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
    if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); pal.hidden ? openP() : closeP(); }
    else if (e.key === "/" && !typing && pal.hidden) { e.preventDefault(); openP(); }
    else if (e.key === "Escape" && !pal.hidden) closeP();
  });
  const navEl = q("nav.toc.dnav");
  if (navEl) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "cp-trigger no-print";
    b.innerHTML = `<span aria-hidden="true">⌕</span> Jump to… <kbd>Ctrl K</kbd>`;
    b.addEventListener("click", openP);
    navEl.insertBefore(b, navEl.firstChild);
  }

  /* 3. Reading progress bar and back-to-top */
  const bar = document.createElement("div"); bar.className = "rp-bar"; document.body.appendChild(bar);
  const top = document.createElement("button"); top.type = "button"; top.className = "to-top no-print"; top.setAttribute("aria-label", "Back to top"); top.textContent = "↑";
  top.addEventListener("click", () => scrollTo({ top: 0, behavior: "smooth" })); document.body.appendChild(top);
  const onScroll = () => {
    const h = document.documentElement, max = h.scrollHeight - h.clientHeight;
    bar.style.transform = `scaleX(${max > 0 ? Math.min(h.scrollTop / max, 1) : 0})`;
    top.classList.toggle("show", h.scrollTop > 900);
  };
  addEventListener("scroll", onScroll, { passive: true }); onScroll();

  /* 4. KPI numbers count up the first time they come into view, then show their exact original text */
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window) {
    const els = qa(".tiles b, .kpi b, .ov-src b, .lc-count b").filter(el => /^\s*[\d,.]+\s*[%KMB+]*\s*$/.test(el.textContent));
    const io = new IntersectionObserver(es => es.forEach(en => {
      if (!en.isIntersecting) return; io.unobserve(en.target);
      const el = en.target, orig = el.textContent, m = /([\d,.]+)/.exec(orig), n = parseFloat(m[1].replace(/,/g, ""));
      if (!isFinite(n) || n === 0) return;
      const dec = (m[1].split(".")[1] || "").length, t0 = performance.now(), dur = 700;
      const step = t => { const p = Math.min((t - t0) / dur, 1), v = n * (1 - Math.pow(1 - p, 3));
        el.textContent = p < 1 ? orig.replace(m[1], v.toLocaleString("en-GB", { minimumFractionDigits: dec, maximumFractionDigits: dec })) : orig;
        if (p < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    }), { threshold: .6 });
    els.forEach(el => io.observe(el));
  }
})();
