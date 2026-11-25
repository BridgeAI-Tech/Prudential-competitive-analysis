/* ---------- News in pictures (20 Nov 2026) ----------
   Every news / newsroom record that has a lead image: picture, insurer, date, the record's own (English) title and
   source, "Read the article" (original URL) and "Evidence record" (the dashboard's evidence routing). Text unchanged. */
(function () {
  if (typeof NEWSIMG === "undefined" || typeof EVID === "undefined") return;
  const rows = EVID.filter(r => NEWSIMG[r[0]]).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return;
  const BR = ["Prudential", "AIA", "Manulife", "AXA"];
  const KIND = { Media: "News media", "Official site": "Newsrooms" };
  const e = s => (typeof escH === "function" ? escH(s) : String(s ?? ""));

  function mount(host, where, id, limit0) {
    if (!host) return;
    const sec = document.createElement("section");
    sec.className = "nw reveal in"; sec.id = id;
    let fb = "All", fk = "All", limit = limit0;
    sec.innerHTML = `<div class="lc-head"><div><h3><span class="nw-ico">▣</span> News in pictures</h3>
        <p>Each picture is the article's own lead image. Click to read the article; "Evidence record" opens it in the evidence log.</p></div>
        <span class="lc-count"><b>${rows.length}</b> articles</span></div>
      <div class="lc-filters"><div class="lc-pills nw-k">${["All", "News media", "Newsrooms"].map(k => `<button type="button" data-k="${k}" class="${k === "All" ? "on" : ""}">${k}</button>`).join("")}</div>
        <div class="lc-pills nw-b"><button type="button" data-b="All" class="on">All</button>${BR.map(b => `<button type="button" data-b="${b}" class="bp-pill bp-${b.toLowerCase()}">${b}</button>`).join("")}</div></div>
      <div class="nw-grid"></div><button type="button" class="pd-more lc-more">Show more ▾</button>`;
    host.insertAdjacentElement(where, sec);
    const draw = () => {
      const xs = rows.filter(r => (fb === "All" || r[2] === fb) && (fk === "All" || KIND[r[8]] === fk));
      sec.querySelector(".nw-grid").innerHTML = xs.slice(0, limit).map(r => {
        const x = TT(r);
        return `<article class="nw-card">
          <a class="nw-img" href="${e(r[10])}" target="_blank" rel="noopener"><img loading="lazy" src="${MEDIA_BASE}${NEWSIMG[r[0]]}" alt=""></a>
          <div class="nw-body"><div class="nw-meta"><span class="bp-pill bp-${r[2].toLowerCase()}">${r[2]}</span><span class="mono">${fmtD(r[1])}</span></div>
            <a class="nw-t" href="${e(r[10])}" target="_blank" rel="noopener">${x.t}</a>
            <div class="nw-src">${e(r[11] || r[8])}${x.zh ? " · translated from Chinese" : ""}</div>
            <div class="nw-acts"><a href="${e(r[10])}" target="_blank" rel="noopener">Read the article ↗</a><button type="button" data-id="${r[0]}">Evidence record →</button></div></div></article>`;
      }).join("") || '<p class="muted small">No articles for this filter.</p>';
      sec.querySelector(".lc-more").hidden = xs.length <= limit;
    };
    sec.addEventListener("click", ev => {
      const b = ev.target.closest(".nw-b button"), k = ev.target.closest(".nw-k button"), rec = ev.target.closest("button[data-id]");
      if (b) { fb = b.dataset.b; limit = limit0; sec.querySelectorAll(".nw-b button").forEach(x => x.classList.toggle("on", x === b)); draw(); }
      if (k) { fk = k.dataset.k; limit = limit0; sec.querySelectorAll(".nw-k button").forEach(x => x.classList.toggle("on", x === k)); draw(); }
      if (ev.target.closest(".lc-more")) { limit += limit0; draw(); }
      if (rec) { const r = rows.find(x => x[0] === rec.dataset.id); if (r && typeof openDrawer === "function") openDrawer("News article", TT(r).o.slice(0, 120), [r]); }
    });
    draw();
  }
  // Executive Summary: after the live captures wall; Competitor Activity: at the top of the page
  const es = document.getElementById("captures") || document.querySelector("#es .ov");
  mount(es, "afterend", "news-pics", 6);
  const p2 = document.querySelector("#p2 .sec-head");
  mount(p2, "afterend", "news-pics-p2", 6);
})();
