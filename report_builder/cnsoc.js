/* ---------- Mainland social conversation: Xiaohongshu and WeChat (20 Nov 2026) ----------
   412 posts about the four insurers (1 Nov 2025 - 31 Oct 2026, about Hong Kong, classified post by post), found by
   searching each insurer's name. Search-based: what others say about each insurer, so it has its own section and is
   not added to the activity counts. Row: [id, platform, brand, yyyymmdd, likes, title (Chinese), English summary,
   topic, speaker, tone, plan, url, picture]. */
(function () {
  if (typeof CNSOC === "undefined" || !CNSOC.length) return;
  const B = ["Prudential", "AIA", "Manulife", "AXA"], ST = CNSOC_ST, N = ST.n;
  const COL = { Prudential: "#D6343C", AIA: "#C27A00", Manulife: "#1A9A6C", AXA: "#2A78D6" };
  const TOPIC = { company_news: "Company news", products: "Products and plans", events_brand: "Events and brand", claims_service: "Claims and service",
    dividends_returns: "Dividends and returns", comparison: "Comparisons", recruitment_agents: "Agent recruitment", other: "Other" };
  const SPEAK = { agent_or_broker: "Agents and brokers", media_or_kol: "Media and finance bloggers", insurer_official: "The insurer itself", customer: "Customers", unknown: "Unclear" };
  const base = typeof MEDIA_BASE !== "undefined" ? MEDIA_BASE : "/media/";
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (a, b) => b ? Math.round(100 * a / b) : 0;
  const fd = d => { const s = String(d); return `${+s.slice(6, 8)} ${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+s.slice(4, 6) - 1]} ${s.slice(0, 4)}`; };

  // pictures of these posts also show in the Evidence library's record card
  const imgOf = {}; CNSOC.forEach(r => { if (r[12]) imgOf[r[11]] = base + r[12]; });
  const prevEV = window.EVIMG; window.EVIMG = (u, id) => (prevEV && prevEV(u, id)) || imgOf[u] || "";

  // sources strip on the Executive Summary: the pilot chips become real counts
  document.querySelectorAll(".ov-src.ov-pilot").forEach(c => {
    const p = /Xiaohongshu/.test(c.textContent) ? "Xiaohongshu" : /WeChat/.test(c.textContent) ? "WeChat" : null; if (!p) return;
    const n = B.reduce((a, b) => a + (ST.platform[p][b] || 0), 0);
    c.innerHTML = `${p}<b>${n}</b>`; c.title = `${n} posts about the four insurers (search-based; not in the activity counts). See Social, Ads & Search: Detail.`;
  });

  const heat = (v, mx) => `background:rgba(42,120,214,${mx ? (0.08 + 0.42 * v / mx).toFixed(2) : 0})`;
  const tbl = (obj, labels, title) => {
    const keys = Object.keys(obj), mx = Math.max(1, ...keys.flatMap(k => B.map(b => obj[k][b] || 0)));
    return `<div class="tbl-wrap"><table class="cn-tbl"><thead><tr><th>${title}</th>${B.map(b => `<th class="num"><span class="bp-pill bp-${b.toLowerCase()}">${b}</span></th>`).join("")}</tr></thead>
      <tbody>${keys.map(k => `<tr><td>${labels[k] || k}</td>${B.map(b => { const v = obj[k][b] || 0;
        return `<td class="num" style="${heat(v, mx)}"><b>${v ? pct(v, ST.brand[b]) + "%" : "–"}</b> <span class="muted small">${v || ""}</span></td>`; }).join("")}</tr>`).join("")}</tbody></table></div>`;
  };
  const PN = p => p === "Xiaohongshu" ? "Little Red Book (Xiaohongshu)" : p;   // display name (client, 24 Nov 2026); data keys unchanged
  const bars = B.map(b => { const x = ST.platform.Xiaohongshu[b] || 0, w = ST.platform.WeChat[b] || 0, t = x + w;
    return `<div class="cn-bar"><span class="cn-b" style="color:${COL[b]}">${b}</span><span class="cn-track"><i style="width:${pct(x, N) * 2.4}%;background:${COL[b]}"></i><i style="width:${pct(w, N) * 2.4}%;background:${COL[b]};opacity:.45"></i></span>
      <span class="cn-n mono"><b>${pct(t, N)}%</b> ${t}</span></div>`; }).join("");

  const sec = document.createElement("section");
  sec.className = "cn reveal in"; sec.id = "cnsoc";
  sec.innerHTML = `<h3>Mainland social conversation: Little Red Book (Xiaohongshu) and WeChat <span class="cn-tag">SEARCH-BASED</span></h3>
    <p class="muted small">${N} posts about the four insurers, 1 Nov 2025 – 31 Oct 2026, found by searching each insurer's name on Little Red Book (Xiaohongshu) and WeChat (collected 19 Nov 2026).
      Of ${ST.fetched.toLocaleString()} posts fetched, ${ST.window_hk} were in the period and about Hong Kong, ${ST.named} named their insurer, and ${N} are substantially about it (checked post by post).
      This shows what agents, brokers, media, bloggers, customers and the insurers say <i>about</i> each insurer, so it is kept apart from the activity counts elsewhere in the dashboard. No personal names are stored.</p>
    <div class="insight"><span class="tag">KEY INSIGHT</span><p>${CNSOC_INS}</p></div>
    <div class="cn-grid">
      <div class="ov-panel"><h4>Share of conversation</h4><p class="muted small">Posts about each insurer; darker = Little Red Book, lighter = WeChat.</p>${bars}</div>
      <div class="ov-panel"><h4>Who is talking</h4><p class="muted small">Share of each insurer's posts by who wrote them.</p>${tbl(ST.speaker, SPEAK, "Speaker")}</div>
    </div>
    <div class="cn-grid">
      <div class="ov-panel"><h4>What they talk about</h4><p class="muted small">Share of each insurer's posts by topic (count after the share).</p>${tbl(ST.topic, TOPIC, "Topic")}</div>
      <div class="ov-panel"><h4>Tone towards the insurer</h4><p class="muted small">As read from each post's text.</p>${tbl(ST.tone, { positive: "Positive", neutral: "Neutral", negative: "Negative" }, "Tone")}</div>
    </div>
    <div class="cn-wall">
      <div class="lc-filters"><div class="lc-pills cn-b-f"><button type="button" data-b="All" class="on">All</button>${B.map(b => `<button type="button" data-b="${b}" class="bp-pill bp-${b.toLowerCase()}">${b}</button>`).join("")}</div>
        <div class="lc-pills cn-p-f">${["All", "Xiaohongshu", "WeChat"].map(p => `<button type="button" data-p="${p}" class="${p === "All" ? "on" : ""}">${PN(p)}</button>`).join("")}</div>
        <div class="lc-pills cn-t-f"><button type="button" data-t="All" class="on">All topics</button>${Object.keys(ST.topic).map(t => `<button type="button" data-t="${t}">${TOPIC[t]}</button>`).join("")}</div>
        <div class="lc-pills cn-s-f"><button type="button" data-s="date" class="on">Newest</button><button type="button" data-s="likes">Most liked</button></div></div>
      <div class="nw-grid cn-grid-posts"></div><button type="button" class="pd-more lc-more">Show more ▾</button></div>`;
  const host = document.querySelector("#deep .sec-head");
  const after = host?.parentElement.querySelector(":scope > .insight") || host;
  if (!after) return;
  after.insertAdjacentElement("afterend", sec);

  let fb = "All", fp = "All", ft = "All", sort = "date", limit = 12;
  const draw = () => {
    const xs = CNSOC.filter(r => (fb === "All" || r[2] === fb) && (fp === "All" || r[1] === fp) && (ft === "All" || r[7] === ft))
      .slice().sort((a, b) => sort === "likes" ? b[4] - a[4] : b[3] - a[3]);
    sec.querySelector(".cn-grid-posts").innerHTML = xs.slice(0, limit).map(r => `<article class="nw-card cn-card" data-u="${e(r[11])}" data-l="${e(r[6])}" tabindex="0" role="button">
        ${r[12] ? `<div class="nw-img"><img loading="lazy" src="${base}${e(r[12])}" alt=""></div>` : ""}
        <div class="nw-body"><div class="nw-meta"><span class="bp-pill bp-${r[2].toLowerCase()}">${r[2]}</span><span class="mono">${fd(r[3])}</span></div>
          <div class="cn-chips"><span class="ds-tag">${PN(r[1])}</span><span class="ds-tag">${TOPIC[r[7]]}</span><span class="ds-tag cn-t-${r[9]}">${r[9]}</span></div>
          <div class="nw-t">${e(r[6])}</div>
          <div class="nw-src">${e(SPEAK[r[8]])}${r[10] ? " · " + e(r[10]) : ""} · ♥ ${Number(r[4]).toLocaleString()}</div>
          <div class="nw-acts"><span class="cn-open">Evidence record →</span><button type="button" class="cn-ext small" data-x="${e(r[11])}">Open post ↗</button></div></div></article>`).join("")
      || '<p class="muted small">No posts for this filter.</p>';
    sec.querySelector(".lc-more").hidden = xs.length <= limit;
  };
  draw();
  sec.addEventListener("click", ev => {
    const pick = (sel, set) => { const b = ev.target.closest(sel); if (!b) return false; set(b); b.parentElement.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); limit = 12; draw(); return true; };
    if (pick(".cn-b-f button", b => fb = b.dataset.b) || pick(".cn-p-f button", b => fp = b.dataset.p) || pick(".cn-t-f button", b => ft = b.dataset.t) || pick(".cn-s-f button", b => sort = b.dataset.s)) return;
    if (ev.target.closest(".lc-more")) { limit += 12; draw(); return; }
    const x = ev.target.closest(".cn-ext"); if (x) { window.open(x.dataset.x, "_blank", "noopener"); return; }   // straight to the post
    const c = ev.target.closest(".cn-card"); if (c) window.routeEv?.(c.dataset.u, c.dataset.l);
  });
  sec.addEventListener("keydown", ev => { const c = ev.target.closest(".cn-card"); if (c && ev.key === "Enter") window.routeEv?.(c.dataset.u, c.dataset.l); });
})();
