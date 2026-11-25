/* ---------- Executive overview, InkTank-style (19–20 Nov 2026) ----------
   Built from the dashboard's own data, nothing invented:
   - source strip: record counts per platform from EVID (+ the Xiaohongshu / WeChat pilot)
   - takeaway cards: the INSIGHTS findings (headline, two evidence lines, the Prudential recommendation, confidence);
     "Inspect evidence" opens the existing finding panel with its sources
   - competitor war room: radar of Prudential vs one rival on six activity measures counted from EVID in the window
   - campaign snapshots (MEDIA images) and data coverage per channel                                   */
(function () {
  const es = document.getElementById("es");
  if (!es || typeof EVID === "undefined") return;
  const BR4 = ["Prudential", "AIA", "Manulife", "AXA"];
  const COL = { Prudential: "var(--b-pru)", AIA: "var(--b-aia)", Manulife: "var(--b-mfc)", AXA: "var(--b-axa)" };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const txt = h => { const d = document.createElement("div"); d.innerHTML = h || ""; return d.textContent.replace(/\s+/g, " ").trim(); };
  // the evidence text carries citations in brackets ("(HY report, p.25)"): drop them, then cut at a sentence end or a word
  const firstSentences = (t, n = 1, max = 220) => {
    const c = t.replace(/\s*\([^()]*\)/g, "").replace(/\s+/g, " ").trim();
    const parts = c.split(/(?<=[a-z0-9%)][.!?])\s+(?=[A-Z"“])/);
    const s = parts.slice(0, n).join(" ");
    return s.length > max ? s.slice(0, max).replace(/\s+\S*$/, "") + "…" : s; };
  const inWin = r => r[1] >= 20251101 && r[1] <= 20261031;
  const W = EVID.filter(inWin);

  // ---- source strip
  const plat = {}; W.forEach(r => { plat[r[8]] = (plat[r[8]] || 0) + 1; });
  const order = ["Meta ads", "Google ads", "Facebook", "Instagram", "Threads", "LinkedIn", "YouTube", "App store", "Media", "Official site", "HKEX", "Industry"];
  const label = { "Meta ads": "Meta Ad Library", "Google ads": "Google Ads", "App store": "App Store & Google Play", "Media": "Hong Kong media", "Official site": "Insurer newsrooms", "HKEX": "HKEX filings", "Industry": "Industry awards" };
  const chips = order.filter(p => plat[p]).map(p => `<span class="ov-src">${esc(label[p] || p)}<b>${plat[p].toLocaleString()}</b></span>`).join("")
    + `<span class="ov-src ov-pilot" title="Collection tested 19 Nov 2026; not yet in the counts">Little Red Book<b>pilot</b></span><span class="ov-src ov-pilot" title="Collection tested 19 Nov 2026; not yet in the counts">WeChat<b>pilot</b></span>`;

  // ---- takeaway cards from INSIGHTS
  // picture for each card, taken from the sources the finding itself cites (page screenshot or the article's lead image), no repeats
  const usedImg = new Set();
  const byUrl = {}; if (typeof EVID !== "undefined") EVID.forEach(r => { if (r[10] && !byUrl[r[10]]) byUrl[r[10]] = r; });
  const pickImg = x => {
    const base = typeof MEDIA_BASE !== "undefined" ? MEDIA_BASE : "/media/";
    const urls = [...[x.finding, x.compare, x.means, x.act].join(" ").matchAll(/href="([^"]+)"/g)].map(m => m[1]).filter(u => /^https?:/.test(u));
    const cands = [];
    urls.forEach(u => {
      if (typeof MOVESHOT !== "undefined" && MOVESHOT[u]) cands.push({ f: MOVESHOT[u], u });
      const r = byUrl[u]; if (r && typeof NEWSIMG !== "undefined" && NEWSIMG[r[0]]) cands.push({ f: NEWSIMG[r[0]], u });
    });
    if (x.ins && typeof evidFor === "function" && typeof NEWSIMG !== "undefined")
      evidFor(x).slice().sort((a, c) => c[1] - a[1]).forEach(r => { if (NEWSIMG[r[0]]) cands.push({ f: NEWSIMG[r[0]], u: r[10] }); });
    const c = cands.find(c => !usedImg.has(c.f)); if (!c) return "";
    usedImg.add(c.f);
    const host = (c.u.split("/")[2] || "").replace(/^www\./, "");
    return `<a class="ov-img" href="${esc(c.u)}" target="_blank" rel="noopener"><img loading="lazy" src="${base}${esc(c.f)}" alt=""><span class="ov-img-src">Source: ${esc(host)}</span></a>`;
  };
  const cards = (typeof INSIGHTS !== "undefined" ? INSIGHTS : []).slice(0, 6).map((x, i) => {
    const ev = firstSentences(txt(x.finding), 2, 240), rec = firstSentences(txt(x.act), 1, 200);
    const strength = String(x.conf || "").toLowerCase();
    return `<article class="ov-card">${pickImg(x)}
      <div class="ov-meta"><span class="ov-tag">${esc(x.mods || "Finding")}</span><span class="ov-str ov-${esc(strength)}">${esc(x.conf || "")}</span></div>
      <h4>${esc(x.t)}</h4>
      <p class="ov-ev">${esc(ev)}</p>
      <div class="ov-rec"><span>Prudential recommendation</span>${esc(rec)}</div>
      <button type="button" class="ov-go" data-kd="${i}">Inspect evidence →</button></article>`;
  }).join("");

  // ---- war room: six activity measures per brand (counts in the window; scaled to the highest brand = 100)
  const AX = [["Paid ads", r => r[3] === "ad"], ["Social posts", r => r[3] === "social_post"], ["Media coverage", r => r[3] === "news_article"],
              ["Announcements & awards", r => ["announcement", "award", "content_article"].includes(r[3])], ["Video", r => r[3] === "video"],
              ["Campaigns & sponsorship", r => /sponsor|campaign|community/.test(String(r[4] || ""))]];
  const cnt = {}; BR4.forEach(b => { cnt[b] = AX.map(([, f]) => W.filter(r => r[2] === b && f(r)).length); });
  const mx = AX.map((_, k) => Math.max(1, ...BR4.map(b => cnt[b][k])));
  const radar = rival => {
    const cx = 170, cy = 150, R = 110, n = AX.length, pt = (k, v) => [cx + R * v * Math.sin(2 * Math.PI * k / n), cy - R * v * Math.cos(2 * Math.PI * k / n)];
    const ring = f => AX.map((_, k) => pt(k, f).join(",")).join(" ");
    const poly = b => AX.map((_, k) => pt(k, cnt[b][k] / mx[k]).join(",")).join(" ");
    const grid = [0.25, 0.5, 0.75, 1].map(f => `<polygon points="${ring(f)}" class="ov-grid"/>`).join("")
      + AX.map((a, k) => { const [x, y] = pt(k, 1.18); return `<line x1="${cx}" y1="${cy}" x2="${pt(k, 1)[0]}" y2="${pt(k, 1)[1]}" class="ov-grid"/><text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" class="ov-ax">${esc(a[0])}</text>`; }).join("");
    return `<svg viewBox="-50 -10 440 320" role="img" aria-label="Activity radar: Prudential vs ${esc(rival)}">${grid}
      <polygon points="${poly(rival)}" style="fill:${COL[rival]};fill-opacity:.16;stroke:${COL[rival]}" class="ov-poly"/>
      <polygon points="${poly("Prudential")}" style="fill:var(--b-pru);fill-opacity:.18;stroke:var(--b-pru)" class="ov-poly"/></svg>`;
  };
  const warTable = rival => `<table class="ov-tbl"><thead><tr><th>Measure (records, Nov 2025 – Oct 2026)</th><th class="num">Prudential</th><th class="num">${esc(rival)}</th></tr></thead><tbody>`
    + AX.map((a, k) => `<tr><td>${esc(a[0])}</td><td class="num"><b>${cnt.Prudential[k].toLocaleString()}</b></td><td class="num">${cnt[rival][k].toLocaleString()}</td></tr>`).join("") + "</tbody></table>";

  // ---- campaign snapshots + coverage
  const base = location.protocol === "file:" ? "../report_app/prudential/media/" : "/media/";
  const M = (typeof MEDIA !== "undefined" ? MEDIA : []);
  const snaps = BR4.map(b => M.find(m => m.brand === b && m.platform === "Meta ad") || M.find(m => m.brand === b && m.platform === "Instagram")).filter(Boolean);
  const totalW = W.length;
  const cov = order.filter(p => plat[p]).map(p => `<div class="ov-cov"><span>${esc(label[p] || p)}</span><i style="width:${Math.max(2, 100 * plat[p] / Math.max(...Object.values(plat)))}%"></i><b>${plat[p].toLocaleString()}</b></div>`).join("");

  const el = document.createElement("div");
  el.className = "ov";
  el.innerHTML = `
    <div class="ov-strip" aria-label="Verified sources"><span class="ov-strip-h">Verified sources</span>${chips}
      <span class="ov-total"><b>${totalW.toLocaleString()}</b> records · Nov 2025 – Oct 2026</span></div>
    <div class="ov-h"><h3>Executive takeaways</h3><a href="#p6" data-view="p6" class="ov-link">All insights & recommendations →</a></div>
    <div class="ov-cards">${cards}</div>
    <div class="ov-h"><h3>Competitor war room</h3><span class="muted small">How active each brand was, by channel. Scaled so the busiest brand on each measure = the outer ring.</span></div>
    <div class="ov-war">
      <div class="ov-panel"><div class="seg ov-rival">${BR4.slice(1).map((b, i) => `<button type="button" class="${i ? "" : "on"}" data-r="${b}">Prudential vs ${b}</button>`).join("")}</div>
        <div class="ov-radar"></div><div class="ov-legend"><span><i style="background:var(--b-pru)"></i>Prudential</span><span class="ov-rv"></span></div></div>
      <div class="ov-panel ov-wt"></div>
    </div>
    <div class="ov-3">
      <div class="ov-panel"><h4>Campaign snapshots</h4><p class="muted small">Each brand's latest ad or post (Meta Ad Library, Instagram).</p>
        <div class="ov-snaps">${snaps.map(m => `<figure class="vg-card" data-i="${M.indexOf(m)}" tabindex="0"><div class="vg-img"><img loading="lazy" src="${base}${esc(m.file)}" alt="${esc(m.brand)} ${esc(m.platform)}"><span class="vg-badge">${esc(m.platform)}</span></div><figcaption><div class="vg-meta"><b class="bp-${m.brand.toLowerCase()}">${esc(m.brand)}</b></div></figcaption></figure>`).join("")}</div>
        <a href="#gallery" class="ov-link">Open the campaign gallery →</a></div>
      <div class="ov-panel"><h4>Data coverage</h4><p class="muted small">Records collected per channel in the period.</p>${cov}
        <a href="#watch" data-view="watch" class="ov-link">Coverage detail →</a></div>
    </div>`;
  const anchor = es.querySelector(".onestrip") || es.querySelector(".vhead");
  anchor.insertAdjacentElement("afterend", el);

  const drawWar = rival => {
    el.querySelector(".ov-radar").innerHTML = radar(rival);
    el.querySelector(".ov-wt").innerHTML = warTable(rival);
    el.querySelector(".ov-rv").innerHTML = `<i style="background:${COL[rival]}"></i>${esc(rival)}`;
  };
  drawWar("AIA");
  el.querySelector(".ov-rival").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
    el.querySelectorAll(".ov-rival button").forEach(x => x.classList.toggle("on", x === b)); drawWar(b.dataset.r); });
  el.addEventListener("click", e => { const g = e.target.closest(".ov-go"); if (!g) return;
    const k = document.querySelector(`#kd button[data-i="${g.dataset.kd}"]`); if (k) k.click(); });
})();
