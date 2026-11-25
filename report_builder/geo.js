/* ---------- Geo footprint, redesigned (20 Nov 2026) ----------
   Same data as before (STATS.maps: Google Maps listings collected 12 Nov 2026, official walk-in centres, 2021 census
   reach, location moves). New presentation:
     1. one scorecard per insurer (service points, districts, residents reached, walk-in centres, Google rating);
     2. a map that opens on district summaries (one donut per district: each insurer's share of listings), with a
        switch to every location and insurer filters;
     3. district-by-district table that flags where rivals are present and Prudential is not;
     4. location moves as picture cards (the source page or article), opening their evidence record.
   The old tile map and pin map are replaced; the brand table, official centres and reach note stay. */
(function () {
  const G = typeof STATS !== "undefined" && STATS.maps; if (!G || !document.getElementById("footprintWrap")) return;
  const B = ["Prudential", "AIA", "Manulife", "AXA"], S = G.summary;
  const COL = { Prudential: "#D6343C", AIA: "#C27A00", Manulife: "#1A9A6C", AXA: "#2A78D6" };
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DIST = { "Central and Western": [22.2826, 114.1452], "Wan Chai": [22.2766, 114.1756], "Eastern": [22.2840, 114.2241], "Southern": [22.2458, 114.1600],
    "Yau Tsim Mong": [22.3110, 114.1700], "Sham Shui Po": [22.3307, 114.1622], "Kowloon City": [22.3282, 114.1916], "Wong Tai Sin": [22.3420, 114.1953],
    "Kwun Tong": [22.3133, 114.2258], "Kwai Tsing": [22.3547, 114.1260], "Tsuen Wan": [22.3707, 114.1149], "Tuen Mun": [22.3918, 113.9773],
    "Yuen Long": [22.4445, 114.0222], "North": [22.4940, 114.1380], "Tai Po": [22.4508, 114.1641], "Sha Tin": [22.3833, 114.1880],
    "Sai Kung": [22.3814, 114.2705], "Islands": [22.2611, 113.9461] };
  const off = b => (G.official || []).filter(o => o.brand === b);
  const R = G.reach?.by_brand || {};
  const wrap = document.getElementById("footprintWrap");
  const ins = wrap.querySelector(".insight");

  // ---- 1. scorecards
  const card = b => { const s = S[b], d = s.districts.length, r = R[b];
    return `<div class="geo-card${b === "Prudential" ? " me" : ""}" style="--c:${COL[b]}">
      <div class="geo-h"><span class="bp-pill bp-${b.toLowerCase()}">${b}</span>${b === "Prudential" ? '<span class="geo-you">Our client</span>' : ""}</div>
      <div class="geo-kpis">
        <div><b>${s.points}</b><span>service points on Google Maps</span></div>
        <div><b>${d}<small>/18</small></b><span>districts covered</span><i class="geo-bar"><i style="width:${Math.round(100 * d / 18)}%"></i></i></div>
        <div><b>${r ? r.pct + "%" : "–"}</b><span>of residents live in a covered district</span></div>
        <div><b>${off(b).length}</b><span>walk-in centres on its own website</span></div>
      </div>
      <div class="geo-rate"><span class="geo-star">★ ${s.avg_rating ?? "–"}</span> all-time Google rating (${(s.all_time_reviews || 0).toLocaleString()} reviews)
        ${s.window_reviews ? `<br><span class="${s.negative_pct >= 50 ? "geo-neg" : ""}">${s.window_reviews} reviews in the 12 months · ${s.window_avg_stars}★ · ${s.negative_pct}% negative</span>` : "<br><span class=\"muted\">No reviews in the 12 months</span>"}</div>
    </div>`; };

  // ---- 3. district table (where each insurer is; gaps for Prudential)
  const rows = Object.keys(DIST).map(d => ({ d, v: B.map(b => (G.grid[d] || {})[b] || 0) })).map(x => ({ ...x, t: x.v.reduce((a, c) => a + c, 0) }));
  const used = rows.filter(x => x.t).sort((a, c) => c.t - a.t), empty = rows.filter(x => !x.t).map(x => x.d);
  const gaps = used.filter(x => !x.v[0] && x.v.slice(1).some(Boolean));
  const dot = (n, b) => n ? `<span class="geo-dot" style="background:${COL[b]}">${n}</span>` : '<span class="geo-none">–</span>';
  const dtable = `<div class="tbl-wrap"><table class="geo-tbl"><thead><tr><th>District</th>${B.map(b => `<th class="num"><span class="bp-pill bp-${b.toLowerCase()}">${b}</span></th>`).join("")}<th class="num">All</th><th></th></tr></thead>
    <tbody>${used.map(x => `<tr${!x.v[0] && x.v.slice(1).some(Boolean) ? ' class="geo-gap"' : ""}><td><b>${e(x.d)}</b></td>${x.v.map((n, i) => `<td class="num">${dot(n, B[i])}</td>`).join("")}<td class="num"><b>${x.t}</b></td>
      <td>${!x.v[0] && x.v.slice(1).some(Boolean) ? '<span class="geo-flag">Rivals here, not Prudential</span>' : ""}</td></tr>`).join("")}</tbody></table></div>
    <p class="small muted">No insurer has a Google Maps listing in ${empty.length} districts: ${empty.join(", ")}.</p>`;

  // ---- 4. location moves as picture cards
  // moves whose own source page has no screenshot: coverage of the same event, captioned with where it came from (24 Nov 2026)
  const MOVE_PIC = { "http://web.archive.org/web/20260514220226/https://www.manulife.com.hk/en/individual/about/newsroom/manulife-partners-with-mind-hk-to-establish-new-wellbeing-consultation-hub-in-mong-kok.html":
    ["move_7be16b2042f9c1.jpg", "Insurance Business, 9 Apr 2026 · insurancebusinessmag.com"] };
  const mbase = typeof MEDIA_BASE !== "undefined" ? MEDIA_BASE : "/media/";
  const moves = (G.news || []).map(n => { const fb = MOVE_PIC[n.source_url];
    const img = (typeof window.EVIMG === "function" ? window.EVIMG(n.source_url) : "") || (fb ? mbase + fb[0] : "");
    return `<article class="nw-card geo-move" data-u="${e(n.source_url)}" data-l="${e(n.what)}" tabindex="0" role="button">
      ${img ? `<div class="nw-img"><img loading="lazy" src="${img}" alt="">${fb && !window.EVIMG?.(n.source_url) ? `<span class="ov-img-src">${e(fb[1])}</span>` : ""}</div>` : ""}
      <div class="nw-body"><div class="nw-meta"><span class="bp-pill bp-${n.brand.toLowerCase()}">${n.brand}</span><span class="mono">${fmtD(+n.date.replace(/-/g, ""))}</span></div>
        <div class="cn-chips"><span class="ds-tag">${e(n.kind || "move")}</span>${n.district && n.district !== "Not stated" ? `<span class="ds-tag">${e(n.district)}</span>` : ""}</div>
        <div class="nw-t">${e(n.what)}</div>
        ${n.note ? `<div class="nw-src">${e(n.note)}</div>` : ""}
        <div class="nw-acts"><span class="cn-open">Evidence record →</span><span class="small muted">${e(n.publisher || "")}</span></div></div></article>`; }).join("");

  const box = document.createElement("div");
  box.className = "geo reveal in"; box.id = "geoX";
  box.innerHTML = `<div class="geo-cards">${B.map(card).join("")}</div>
    <div class="geo-pair">
    <div class="card geo-mapcard">
      <div class="geo-bar-top"><div><div class="chart-title">Where they are</div><div class="small muted">Google Maps listings collected ${e(G.collected)}. District view: each circle is one district, sized by listings, split by insurer. Click a circle or a mark for details.</div></div>
        <div class="geo-ctl"><div class="fx-seg geo-mode"><button type="button" data-m="d" class="on">By district</button><button type="button" data-m="p">Every location</button></div>
          <div class="lc-pills geo-br">${B.map(b => `<button type="button" data-b="${b}" class="bp-pill bp-${b.toLowerCase()} on">${b}</button>`).join("")}</div></div></div>
      <div id="geoMap"></div>
      <div class="legend small">${B.map(b => `<span><i style="background:${COL[b]}"></i>${b}</span>`).join("")}<span><i style="background:#64748B;border-radius:2px"></i>square = service or health centre · round = office</span></div>
    </div>
    <div class="card"><div class="chart-title">District by district</div>
      <div class="small muted">Google Maps service points per district, most covered first. ${gaps.length ? `<b>${gaps.length} district${gaps.length === 1 ? "" : "s"}</b> where rivals have a listing and Prudential has none are flagged.` : ""}</div>${dtable}</div>
    </div>
    ${moves ? `<div class="card"><div class="chart-title">Location moves in the 12 months</div><div class="small muted">Openings, expansions, leases and relocations, newest first. Click one for its evidence record.</div>
      <div class="nw-grid geo-moves">${moves}</div></div>` : ""}`;
  (ins || wrap.querySelector("h3")).insertAdjacentElement("afterend", box);
  // the old tile map, pin map and moves list are replaced by the views above
  [document.getElementById("fpMap")?.closest(".card"), document.getElementById("fpNewsCard")].forEach(x => { if (x) x.style.setProperty("display", "none", "important"); });
  // the district tile chart leads the section (24 Nov 2026)
  const tiles = document.getElementById("fpTiles")?.closest(".card");
  if (tiles) (ins || wrap.querySelector("h3")).insertAdjacentElement("afterend", tiles);

  box.addEventListener("click", ev => { const m = ev.target.closest(".geo-move"); if (m) window.routeEv?.(m.dataset.u, m.dataset.l); });
  box.addEventListener("keydown", ev => { const m = ev.target.closest(".geo-move"); if (m && ev.key === "Enter") window.routeEv?.(m.dataset.u, m.dataset.l); });

  // ---- 2. the map (Leaflet, loaded on first view)
  let map, layer, mode = "d"; const on = new Set(B);
  const donut = (vals, total) => { const r = 15 + 5 * Math.sqrt(total), c = 2 * Math.PI * (r - 5); let off0 = 0;
    const segs = vals.map((v, i) => { if (!v) return ""; const len = c * v / total, s = `<circle r="${r - 5}" cx="${r}" cy="${r}" fill="none" stroke="${COL[B[i]]}" stroke-width="9" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-off0}" transform="rotate(-90 ${r} ${r})"/>`; off0 += len; return s; }).join("");
    return { html: `<svg width="${2 * r}" height="${2 * r}" viewBox="0 0 ${2 * r} ${2 * r}"><circle r="${r - 1}" cx="${r}" cy="${r}" fill="#fff" stroke="#E2E8F0"/>${segs}<text x="${r}" y="${r + 4}" text-anchor="middle" font-size="12" font-weight="700" fill="#0F172A">${total}</text></svg>`, r }; };
  const draw = () => {
    if (!map) return; layer.clearLayers(); const L = window.L, pts = [];
    if (mode === "d") {
      Object.entries(DIST).forEach(([d, ll]) => {
        const vals = B.map(b => on.has(b) ? ((G.grid[d] || {})[b] || 0) : 0), t = vals.reduce((a, c) => a + c, 0); if (!t) return;
        const { html, r } = donut(vals, t);
        const list = G.locs.filter(l => l.d === d && on.has(l.b)).map(l => `<li><span style="color:${COL[l.b]};font-weight:700">${l.b}</span> ${e(l.n)}${l.r ? ` · ★${l.r}` : ""} <a href="${e(l.u)}" target="_blank" rel="noopener">map ↗</a></li>`).join("");
        L.marker(ll, { icon: L.divIcon({ html, className: "geo-donut", iconSize: [2 * r, 2 * r], iconAnchor: [r, r] }) })
          .bindPopup(`<b>${e(d)}</b> · ${t} listing${t === 1 ? "" : "s"}<br>${B.map((b, i) => vals[i] ? `<span style="color:${COL[b]}">${b} ${vals[i]}</span>` : "").filter(Boolean).join(" · ")}<ul class="geo-pop">${list}</ul>`)
          .bindTooltip(`${d}: ${t}`, { direction: "top", offset: [0, -r] }).addTo(layer); pts.push(ll);
      });
    } else {
      const seen = {};
      G.locs.filter(l => on.has(l.b)).forEach(l => {
        const k = l.lat.toFixed(4) + "," + l.lng.toFixed(4), n = (seen[k] = (seen[k] || 0) + 1) - 1;
        const ll = [l.lat + Math.sin(n * 2.4) * 0.0012 * n, l.lng + Math.cos(n * 2.4) * 0.0012 * n];
        const sq = /centre/i.test(l.k);
        L.marker(ll, { icon: L.divIcon({ html: `<span class="geo-pin${sq ? " sq" : ""}" style="background:${COL[l.b]}"></span>`, className: "", iconSize: [16, 16], iconAnchor: [8, 8] }) })
          .bindPopup(`<b style="color:${COL[l.b]}">${l.b}</b> · ${e(l.k)}<br><b>${e(l.n)}</b><br>${e(l.d)}${l.r ? ` · ★${l.r} (${l.rc} reviews)` : ""}<br><a href="${e(l.u)}" target="_blank" rel="noopener">Open in Google Maps ↗</a>`)
          .addTo(layer); pts.push(ll);
      });
    }
    if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 13 });
  };
  const init = () => {
    const L = window.L; if (map || !L) return;
    map = L.map("geoMap", { scrollWheelZoom: false, zoomControl: true });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", { maxZoom: 16, attribution: "Tiles © Esri" }).addTo(map);
    layer = L.layerGroup().addTo(map); draw();
    new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById("geoMap"));
  };
  const load = () => {
    if (window.L) return init();
    if (!document.querySelector('link[href*="leaflet"]')) { const c = document.createElement("link"); c.rel = "stylesheet"; c.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"; document.head.appendChild(c); }
    const s = document.createElement("script"); s.src = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"; s.onload = init;
    s.onerror = () => { document.getElementById("geoMap").innerHTML = '<p class="small muted" style="padding:12px">The map could not load; the table below has the same data.</p>'; };
    document.head.appendChild(s);
  };
  new IntersectionObserver((es, o) => { if (es.some(x => x.isIntersecting)) { o.disconnect(); load(); } }).observe(document.getElementById("geoMap"));
  box.querySelector(".geo-mode").addEventListener("click", ev => { const b = ev.target.closest("button"); if (!b) return; mode = b.dataset.m;
    box.querySelectorAll(".geo-mode button").forEach(x => x.classList.toggle("on", x === b)); draw(); });
  box.querySelector(".geo-br").addEventListener("click", ev => { const b = ev.target.closest("button"); if (!b) return;
    on.has(b.dataset.b) ? on.delete(b.dataset.b) : on.add(b.dataset.b); if (!on.size) on.add(b.dataset.b); b.classList.toggle("on", on.has(b.dataset.b)); draw(); });
})();
