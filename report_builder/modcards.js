/* ---------- Module cards (20 Nov 2026) ----------
   Like the Executive Summary takeaways: every module's key-insight box (and each finding on the social detail page)
   shows only a picture, the companies it is about and a one-line headline. Clicking it opens the right-hand panel
   with the big picture, the full text (unchanged), and buttons for the supporting records and the evidence record.
   The full text stays in the page (hidden on screen, shown in print), so filters, search and the AI still read it. */
(function () {
  if (typeof window.openSheet !== "function" || typeof window.EVIMG !== "function") return;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const host = u => (String(u).split("/")[2] || "").replace(/^www\d?\./, "");
  const BR = ["Prudential", "AIA", "Manulife", "AXA"];
  const used = new Set();
  document.querySelectorAll(".ov-card img, .cp-img img, .ob-pic img").forEach(i => used.add(i.getAttribute("src")));   // pictures already on the overview, cards and brief

  // headline: the first sentence without its citations and labels, kept short
  const headOf = el => {
    const c = el.cloneNode(true); c.querySelectorAll(".conf, .tag, button, .ev-btn, details, .ob-pic").forEach(x => x.remove());
    let t = c.textContent.replace(/\s+/g, " ").trim();
    for (let k = 0; k < 3; k++) t = t.replace(/\s*\([^()]*\)/g, "");
    t = t.replace(/\s+([,.;:])/g, "$1").trim();
    const m = /^(.+?(?<!\.[A-Z])[.!?])\s+(?=[A-Z"“])/.exec(t); let h = m ? m[1] : t;
    if (h.length > 165) { const cut = Math.max(h.lastIndexOf(": ", 165), h.lastIndexOf("; ", 165), h.lastIndexOf(", while ", 165));
      h = cut > 60 ? h.slice(0, cut) : h.slice(0, h.lastIndexOf(" ", 150)) + "…"; }
    return h.replace(/[:;,]$/, "").replace(/^\w/, x => x.toUpperCase());
  };
  const brandsOf = t => BR.map(b => [b, t.search(new RegExp(`\\b${b}\\b`))]).filter(x => x[1] >= 0).sort((a, b) => a[1] - b[1]).map(x => x[0]);
  const pills = bs => bs.map(b => `<span class="bp bp-${b.toLowerCase()}">${b}</span>`).join("");
  const words = t => new Set((t.toLowerCase().match(/[a-z]{5,}/g) || []).filter(w => !/^(about|after|their|there|which|while|these|those|other|first|since|every|would|could|being|still|where|prudential|manulife)$/.test(w)));

  // picture: a page the text cites, else the best-matching record behind it (title words, then the companies named)
  const pickPic = (el, recIds, bs) => {
    for (const a of el.querySelectorAll("a[href^='http']")) { const u = a.getAttribute("href"), src = window.EVIMG(u);
      if (src && !used.has(src)) { used.add(src); return { src, u, label: `${a.textContent.trim().slice(0, 40)} · ${host(u)}` }; } }
    if (typeof EVID === "undefined") return null;
    const w = words(el.textContent), ids = recIds && recIds.size ? recIds : null;
    const pool = EVID.filter(r => (ids ? ids.has(r[0]) : bs.includes(r[2])) && r[10] && r[1] >= 20251101 && r[1] <= 20261031);
    let best = null, bestS = -1;
    pool.forEach(r => { const src = window.EVIMG(r[10], r[0]); if (!src || used.has(src) || /news\.google\./.test(r[10])) return;
      const t = String(typeof TT === "function" ? TT(r).o : r[9]).toLowerCase(); let s = 0; w.forEach(x => { if (t.includes(x)) s++; });
      if (bs[0] && r[2] === bs[0]) s += .5;
      if (s > bestS || (s === bestS && r[1] > best[1])) { bestS = s; best = r; } });
    if (!best) return null;
    const src = window.EVIMG(best[10], best[0]); used.add(src);
    return { src, u: best[10], label: `${String(typeof TT === "function" ? TT(best).o : best[9]).slice(0, 40)} · ${host(best[10])}` };
  };

  const boxes = [];
  const build = (el, opt) => {
    if (el.classList.contains("mc")) return;
    const i = boxes.length; boxes.push({ el, opt });
    const txt = opt.text(el);
    if (!txt.textContent.trim()) { boxes.pop(); return; }
    let rec = null; try { rec = opt.recs ? opt.recs(el) : null; } catch (e) { /* no records */ }
    let bs = opt.bs ? opt.bs(el) : brandsOf(txt.textContent); if (!bs.length && opt.brands) bs = opt.brands;
    const p = (opt.pic && opt.pic(el)) || pickPic(txt, rec && rec.ids, bs.length ? bs : BR);
    boxes[i].pic = p; boxes[i].rec = rec;
    el.classList.add("mc"); el.tabIndex = 0; el.setAttribute("role", "button"); el.dataset.mc = i;
    if (!p) el.classList.add("mc-nopic");
    el.insertAdjacentHTML("afterbegin", `${p ? `<div class="mc-pic"><img loading="lazy" src="${esc(p.src)}" alt=""><span class="ov-img-src">${esc(host(p.u))}</span></div>` : ""}
      <div class="mc-b"><div class="mc-meta"><span class="mc-tag">${esc(opt.tag(el))}</span>${pills(bs)}</div><h4 class="mc-h">${esc(opt.head ? opt.head(el) : headOf(txt))}</h4><span class="cmp-more">Tap for detail →</span></div>`);
    // filled or redrawn later by the filters: keep the headline and companies in step
    if (txt === el) return;   // a static card: nothing redraws it
    let q = 0;
    new MutationObserver(() => { cancelAnimationFrame(q); q = requestAnimationFrame(() => {
      const t = opt.text(el); let b = opt.bs ? opt.bs(el) : brandsOf(t.textContent); if (!b.length && opt.brands) b = opt.brands;
      el.querySelector(".mc-h").textContent = opt.head ? opt.head(el) : headOf(t);
      const meta = el.querySelector(".mc-meta"); meta.innerHTML = `<span class="mc-tag">${esc(opt.tag(el))}</span>${pills(b)}`; }); })
      .observe(txt, { childList: true, subtree: true, characterData: true });
  };
  const openBox = i => {
    const { el, opt, pic, rec } = boxes[i], t = opt.text(el); let bs = opt.bs ? opt.bs(el) : brandsOf(t.textContent); if (!bs.length && opt.brands) bs = opt.brands;
    const nR = rec ? rec.ids.size : 0, nD = rec ? rec.docs.size : 0;
    const sec = el.closest("section.view")?.querySelector("h2")?.textContent.replace(/^\s*\d+\.\s*/, "").trim() || "";
    window.openSheet({ img: pic ? pic.src : "", href: pic ? pic.u : "", label: pic ? pic.label : "",
      meta: `<span class="ds-tag">${esc(opt.tag(el))}</span>${sec ? `<span class="ds-tag">${esc(sec)}</span>` : ""}${bs.map(b => `<span class="bp-pill bp-${b.toLowerCase()}">${b}</span>`).join("")}`,
      title: esc(el.querySelector(".mc-h").textContent),
      html: opt.detail(el) + (opt.note ? `<p class="small muted" style="margin-top:12px">${opt.note}</p>` : ""),
      actions: `${nR || nD ? `<button type="button" class="btn primary" data-act="mcrecs" data-arg="${i}">Open the supporting records (${nR ? `${nR} record${nR === 1 ? "" : "s"}` : ""}${nR && nD ? ", " : ""}${nD ? `${nD} document${nD === 1 ? "" : "s"}` : ""})</button>` : ""}
        ${pic ? `<button type="button" class="btn${nR || nD ? "" : " primary"}" data-act="src" data-arg="${esc(pic.u)}">Open the evidence record</button>` : ""}` });
  };
  window.SHEET_ACTS.mcrecs = i => { const b = boxes[+i]; if (!b || !b.rec) return;
    try { goEvidence({ title: b.rec.title || b.el.querySelector(".mc-h").textContent, ids: b.rec.ids, docs: b.rec.docs }); } catch (e) { /* evidence view not ready */ } };

  // 1. every module's key-insight / watch / reading box
  document.querySelectorAll("main section.view:not(#es):not(#ev) .insight").forEach(box => {
    if (box.closest("#insights, .fx, .ds-content")) return;
    build(box, {
      text: b => b.querySelector(":scope > p") || b,
      tag: b => (b.querySelector(":scope > .tag")?.textContent || "Key insight").trim(),
      recs: b => typeof evForBox === "function" ? evForBox(b) : null,
      detail: b => `<p>${(b.querySelector(":scope > p") || b).innerHTML}</p>`,
      note: "The charts and tables behind this finding are on the page, under this card.",
    });
  });
  // 2. the eight findings on the social, ad and search detail page
  document.querySelectorAll("#dpCards > .card").forEach(card => build(card, {
    text: c => c,
    tag: c => `Finding ${(c.id || "").replace(/\D/g, "")}`,
    head: c => (c.querySelector(".chart-title")?.textContent || "").replace(/^\s*\d+\.\s*/, ""),
    recs: c => { if (typeof evOfLinks !== "function") return null; const e = evOfLinks([c]); return { ...e, title: c.querySelector(".chart-title")?.textContent }; },
    detail: c => { const k = c.cloneNode(true); k.querySelectorAll(".mc-pic, .mc-b, .chart-title").forEach(x => x.remove()); return k.innerHTML; },
  }));

  // 3. the Leadership Brief: the bottom line, each strength and weakness, the five actions and the watch list
  //    (pictures come from brief.js; "Read more" opens out in the panel)
  const one = document.getElementById("one");
  if (one) {
    const takePic = el => { const b = el.querySelector(".ob-pic"); if (!b) return null;
      const p = { src: b.querySelector("img").getAttribute("src"), u: b.dataset.href, label: b.dataset.label }; b.remove(); return p; };
    const opened = el => { const k = el.cloneNode(true); k.querySelectorAll(".ob-pic").forEach(x => x.remove());
      k.querySelectorAll("details").forEach(d => { d.querySelector("summary")?.remove(); const w = document.createElement("div"); w.className = "mc-more"; w.innerHTML = d.innerHTML; d.replaceWith(w); });
      return k.innerHTML; };
    const mainTxt = el => { const k = el.cloneNode(true); k.querySelectorAll("details, .ob-pic, .mc-b, .mc-pic").forEach(x => x.remove()); return k.textContent; };
    const pruFirst = el => ["Prudential", ...brandsOf(mainTxt(el)).filter(b => b !== "Prudential")];
    const linkRecs = el => { if (typeof evOfLinks !== "function") return null; const e = evOfLinks([el]); return e.ids.size || e.docs.size ? { ...e, title: headOf(el) } : null; };
    const bl = one.querySelector(".onepage > .op-box");
    if (bl) build(bl, { text: b => b.querySelector(".ob-txt p") || b.querySelector("p") || b, tag: () => "The bottom line", pic: takePic, bs: pruFirst,
      recs: b => linkRecs(b.querySelector(".ob-txt") || b), detail: b => `<p>${(b.querySelector(".ob-txt p") || b.querySelector("p")).innerHTML}</p>` });
    const listCards = (box, tag) => box && [...box.querySelectorAll(":scope > ul > li, :scope > ol > li")].forEach((li, n) => build(li, {
      text: x => x.querySelector(":scope > .ob-body") || x, tag: () => tag(n), pic: takePic, bs: pruFirst,
      recs: x => linkRecs(x.querySelector(":scope > .ob-body") || x), detail: x => opened(x.querySelector(":scope > .ob-body") || x) }));
    const boxBy = rx => [...one.querySelectorAll(".op-box")].find(b => rx.test(b.querySelector("h4")?.textContent || ""));
    listCards(boxBy(/strongest/i), () => "Strongest point");
    listCards(boxBy(/weakest/i), () => "Weakest point");
    listCards(boxBy(/Top five actions/i), n => `Action ${n + 1}`);
    listCards(boxBy(/Watch next/i), () => "Watch next");
  }

  const go = e => { const el = e.target.closest(".mc[data-mc]"); if (!el) return;
    if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
    if (e.target.closest("a[href^='#'], .ev-btn")) return;
    e.preventDefault(); openBox(+el.dataset.mc); };
  document.addEventListener("click", go);
  document.addEventListener("keydown", go);
})();
