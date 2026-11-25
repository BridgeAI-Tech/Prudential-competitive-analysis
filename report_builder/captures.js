/* ---------- Live browser captures wall (InkTank-style; Stitch design system) — 20 Nov 2026 ----------
   Images, not links: real screenshots of the pages behind the evidence (CAPTURES, headless Chromium) plus the real ad,
   post, video and website images (MEDIA). Filters by channel and brand; click opens a lightbox with "Open original" and
   "Open evidence record" (the dashboard's own evidence routing).                                                    */
(function () {
  const seenU = new Set();                     // one card per page (app-store reviews share one app page)
  const caps = (typeof CAPTURES !== "undefined" ? CAPTURES : [])
    .filter(c => !/facebook\.com|linkedin\.com|instagram\.com/i.test((c.final_url || "") + " " + (c.source || "")))   // login walls show nothing of the source
    .filter(c => !seenU.has(c.url) && seenU.add(c.url));
  const media = (typeof MEDIA !== "undefined" ? MEDIA : []);
  if (!caps.length && !media.length) return;
  const BASE = location.protocol === "file:" ? "../report_app/prudential/media/" : "/media/";
  const BR = ["Prudential", "AIA", "Manulife", "AXA"];
  const CH = { "Meta ad": "Paid ads", Instagram: "Social", Facebook: "Social", YouTube: "Video", Website: "Websites", Xiaohongshu: "Little Red Book (Xiaohongshu)", WeChat: "WeChat (微信)" };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = d => { const s = String(d || ""); const m = /^(\d{4})-?(\d{2})-?(\d{2})/.exec(s); return m ? `${+m[3]} ${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+m[2] - 1]} ${m[1]}` : s; };
  const items = [
    ...caps.map(c => ({ brand: c.brand, ch: c.channel, src: c.source || c.plat, date: fmt(c.date), file: c.file, kb: c.kb, url: c.url, title: c.title, live: c.captured })),
    ...media.map(m => ({ brand: m.brand, ch: CH[m.platform] || m.platform, src: m.platform === "Meta ad" ? "Meta Ad Library" : m.platform, date: fmt(m.date), file: m.file, url: m.url,
                         title: m.title || m.text, live: m.captured || "", pilot: m.pilot }))
  ].filter(x => BR.includes(x.brand));
  const chans = ["All", ...["Paid ads", "Social", "Video", "Websites", "News", "App stores", "Little Red Book (Xiaohongshu)", "WeChat (微信)", "Little Red Book & WeChat"].filter(c => items.some(x => x.ch === c))];
  let fc = "All", fb = "All";

  const host = document.getElementById("es")?.querySelector(".ov-war") || document.querySelector("#es .ov") || document.getElementById("es");
  const sec = document.createElement("section");
  sec.className = "lc reveal in";
  sec.id = "captures";
  sec.innerHTML = `<div class="lc-head"><div><h3><span class="lc-ico">◉</span> Live browser captures</h3>
      <p>Real screenshots of the pages, ads and posts behind the evidence — every channel, every brand. Click one to see it full size and open its evidence record.</p></div>
      <span class="lc-count"><b>${items.length}</b> captures</span></div>
    <div class="lc-filters"><div class="lc-pills lc-ch">${chans.map(c => `<button type="button" data-c="${esc(c)}" class="${c === "All" ? "on" : ""}">${esc(c)}${c === "All" ? "" : `<i>${items.filter(x => x.ch === c).length}</i>`}</button>`).join("")}</div>
      <div class="lc-pills lc-br"><button type="button" data-b="All" class="on">All</button>${BR.map(b => `<button type="button" data-b="${b}" class="bp-pill bp-${b.toLowerCase()}">${b}</button>`).join("")}</div></div>
    <div class="lc-grid"></div><button type="button" class="pd-more lc-more">Show more ▾</button>`;
  (host.closest(".ov") ? host.closest(".ov") : host).insertAdjacentElement(host.closest(".ov") ? "beforeend" : "afterend", sec);
  let limit = 18;
  const draw = () => {
    const xs = items.filter(x => (fc === "All" || x.ch === fc) && (fb === "All" || x.brand === fb));
    sec.querySelector(".lc-grid").innerHTML = xs.slice(0, limit).map((x, i) => `<figure class="lc-card" tabindex="0" data-k="${items.indexOf(x)}">
        <div class="lc-img"><img loading="lazy" src="${BASE}${esc(x.file)}" alt="${esc(x.brand)} ${esc(x.src)}"><span class="lc-eye" aria-hidden="true">👁</span>${x.pilot ? '<span class="lc-pilot">pilot</span>' : ""}</div>
        <figcaption><span class="bp-pill bp-${x.brand.toLowerCase()}">${esc(x.brand)}</span><div class="lc-src">${esc(x.src)}</div>
          <div class="lc-meta"><span>${esc(x.date || "")}${x.kb ? ` · ${x.kb} KB` : ""}</span><span class="lc-live">✓ ${x.live ? "live" : "source"}</span></div></figcaption></figure>`).join("")
      || '<p class="muted small">No captures for this filter.</p>';
    sec.querySelector(".lc-more").hidden = xs.length <= limit;
  };
  draw();
  sec.addEventListener("click", e => {
    const c = e.target.closest(".lc-ch button"), b = e.target.closest(".lc-br button");
    if (c) { fc = c.dataset.c; limit = 18; sec.querySelectorAll(".lc-ch button").forEach(x => x.classList.toggle("on", x === c)); draw(); }
    if (b) { fb = b.dataset.b; limit = 18; sec.querySelectorAll(".lc-br button").forEach(x => x.classList.toggle("on", x === b)); draw(); }
    if (e.target.closest(".lc-more")) { limit += 18; draw(); }
    const card = e.target.closest(".lc-card"); if (card) open(+card.dataset.k);
  });
  sec.addEventListener("keydown", e => { const card = e.target.closest(".lc-card"); if (card && e.key === "Enter") open(+card.dataset.k); });

  // lightbox: full capture, caption, original link, and the evidence record (routed by the dashboard's link handler)
  const lb = document.createElement("div");
  lb.className = "lc-lb"; lb.hidden = true;
  lb.innerHTML = `<div class="lc-lb-box" role="dialog" aria-modal="true" aria-label="Capture"><button type="button" class="lc-x" aria-label="Close">×</button><img alt=""><div class="lc-lb-t"></div></div>`;
  document.body.appendChild(lb);
  function open(k) {
    const x = items[k]; if (!x) return;
    lb.querySelector("img").src = BASE + x.file;
    lb.querySelector(".lc-lb-t").innerHTML = `<span class="bp-pill bp-${x.brand.toLowerCase()}">${esc(x.brand)}</span>
      <div class="lc-src" style="margin-top:8px">${esc(x.src)} · <span class="mono">${esc(x.date || "")}</span>${x.live ? ` · captured ${esc(x.live)}` : ""}</div>
      <p>${esc(x.title || "")}</p>
      ${x.url ? `<div class="lc-acts"><a href="${esc(x.url)}" class="btn primary lc-evlink">Open evidence record →</a>
        <a href="${esc(x.url)}" target="_blank" rel="noopener" class="small">Open the original ↗</a></div>` : ""}
      ${x.pilot ? '<p class="muted small">Pilot channel (collection tested 19 Nov 2026); not yet in the counts.</p>' : ""}`;
    lb.hidden = false; lb.querySelector(".lc-x").focus();
  }
  lb.addEventListener("click", e => {
    if (e.target === lb || e.target.closest(".lc-x")) lb.hidden = true;
    const ev = e.target.closest(".lc-evlink") || (e.target.matches(".lc-lb-box > img") ? lb.querySelector(".lc-evlink") : null);   // the picture itself opens the evidence record
    if (ev) {                                   // hand the link to the dashboard's evidence routing (it listens inside main sections)
      e.preventDefault(); lb.hidden = true;
      const a = document.createElement("a"); a.href = ev.getAttribute("href"); a.style.display = "none";
      (document.querySelector("#es") || document.body).appendChild(a); a.click(); a.remove();
    }
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape") lb.hidden = true; });
})();
