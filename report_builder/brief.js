/* ---------- Pictures on the Leadership Brief (20 Nov 2026) ----------
   The bottom line, each company row, the results documents, every strength and weakness, the five actions and the
   watch list get a picture of the page they cite (page screenshot, report page or article image). A strength or
   action with no link of its own borrows the picture of its card on Strengths, Gaps & Actions. Pictures open the
   evidence record (bigger picture, detail, original link). No text is changed. */
(function () {
  const one = document.getElementById("one");
  if (!one || typeof window.EVIMG !== "function") return;
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const host = u => (u.split("/")[2] || "").replace(/^www\d?\./, "");
  const used = new Set();
  const tile = (src, href, label, cls) => `<button type="button" class="ob-pic ${cls || ""}" data-href="${e(href)}" data-label="${e(label)}" title="Open the evidence record"><img loading="lazy" src="${e(src)}" alt=""><span class="ob-cap">${e(label)}</span></button>`;
  // first cited link that has a picture not yet shown on the brief
  const pick = (links, allowRepeat) => {
    for (const a of links) {
      const u = a.getAttribute("href"), src = window.EVIMG(u);
      if (src && (allowRepeat || !used.has(src))) { used.add(src); return { src, u, label: `${a.textContent.replace(/\s+/g, " ").trim().slice(0, 34)} · ${host(u)}` }; }
    }
    return null;
  };
  const links = el => [...el.querySelectorAll("a[href^='http']")].filter(a => !a.closest("details"));
  // the picture already on a Strengths, Gaps & Actions card
  const cardPic = (name, allowRepeat) => {
    const card = [...document.querySelectorAll("#swS .swi, #swW .swi")].find(c => c.querySelector(".a")?.textContent.trim() === name);
    const img = card && card.querySelector(".cp-img img"), src = img && img.getAttribute("src");
    if (!src || (!allowRepeat && used.has(src))) return null;
    // the card's picture element is no longer a link (the card opens its panel): find the link the picture came from
    const cl = [...card.querySelectorAll("a[href^='http']")];
    const a = cl.find(x => window.EVIMG(x.getAttribute("href")) === src) || cl[0];
    if (!a) return null;
    used.add(src);
    const u = a.getAttribute("href");
    return { src, u, label: `${name} · ${host(u)}` };
  };
  const withPic = (li, p) => {
    if (!p || li.querySelector(":scope > .ob-pic")) return;
    const body = document.createElement("div"); body.className = "ob-body";
    body.append(...li.childNodes); li.append(body);
    li.insertAdjacentHTML("afterbegin", tile(p.src, p.u, p.label, "ob-th"));
    li.classList.add("ob-li"); li.parentElement.classList.add("ob-list");
  };

  // 1. the bottom line: the report page it cites
  const bl = one.querySelector(".onepage > .op-box");
  if (bl && !bl.classList.contains("ob-hero")) {
    const p = pick(links(bl));
    if (p) { const txt = document.createElement("div"); txt.className = "ob-txt"; txt.append(...bl.childNodes); bl.append(txt);
      bl.classList.add("ob-hero"); bl.insertAdjacentHTML("beforeend", tile(p.src, p.u, p.label, "ob-big")); }
  }

  // 2. the four companies: a screenshot of each insurer's own website
  if (typeof COMPANY !== "undefined") {
    one.querySelectorAll("#opCo tbody tr").forEach((tr, i) => {
      const c = COMPANY[i], td = tr.cells[0]; if (!c || !c.site || td.querySelector(".ob-pic")) return;
      const src = window.EVIMG(c.site); if (!src) return;
      used.add(src); td.insertAdjacentHTML("beforeend", tile(src, c.site, `Website · ${host(c.site)}`, "ob-co"));
    });
  }

  // 3. the results table: the document behind each insurer's column, shown under the table
  const resTbl = [...one.querySelectorAll("table")].find(t => /Profit or value from new policies/.test(t.textContent));
  if (resTbl && !one.querySelector(".ob-docs")) {
    const brands = [...resTbl.tHead.rows[0].cells].slice(1).map(th => th.textContent.trim());
    const cards = brands.map((b, k) => {
      const col = [...resTbl.tBodies[0].rows].flatMap(r => links(r.cells[k + 1] || document.createElement("td")));
      let p = pick(col);
      if (p) p.label = p.label.replace(/^source · /i, "Results document · ");
      if (!p && typeof COMPANY !== "undefined") { const c = COMPANY.find(x => x.b === b); const src = c && window.EVIMG(c.site); if (src) p = { src, u: c.site, label: `Website · ${host(c.site)}` }; }
      return p ? `<div class="ob-doc"><div class="ob-doc-b"><span class="bp bp-${b.toLowerCase()}">${e(b)}</span></div>${tile(p.src, p.u, p.label)}</div>` : "";
    }).join("");
    if (cards) resTbl.closest(".tbl-wrap").insertAdjacentHTML("afterend", `<div class="ob-docs" aria-label="The results documents behind this table">${cards}</div>`);
  }

  // a bullet with no link and no card picture: the page it describes (visibility: the one wealth-plan launch that was publicised)
  const FIX = { "Paid and video reach": "https://www.prudential.com.hk/en/about-us/newsroom/prudential-announces-survey-and-enlight-launch/" };
  const shot = u => { const src = window.EVIMG(u); return src ? { src, u, label: `Enlight launch release · ${host(u)}` } : null; };

  // 4. strengths and weaknesses: the page each bullet cites, else its card's picture
  one.querySelectorAll("li[data-sw]").forEach(li => {
    const names = li.dataset.sw.split(";").map(k => k.split("|")[1]);
    withPic(li, pick(links(li)) || names.map(n => cardPic(n)).find(Boolean) || names.map(n => cardPic(n, true)).find(Boolean) || pick(links(li), true) || (FIX[names[0]] && shot(FIX[names[0]])));
  });

  // 5. top five actions: the picture of the bullet each one answers (wealth plans: the one plan launch that was publicised)
  const briefPic = name => { const b = one.querySelector(`li.ob-li[data-sw*="|${name}"] > .ob-pic`);
    return b ? { src: b.querySelector("img").getAttribute("src"), u: b.dataset.href, label: b.dataset.label } : null; };
  const ACT = ["The customer app", "Paid and video reach", "Cross-border healthcare service", "Agency momentum", null];
  const actOl = [...one.querySelectorAll(".op-box")].find(b => /Top five actions/.test(b.querySelector("h4")?.textContent || ""))?.querySelector("ol");
  if (actOl) [...actOl.children].forEach((li, i) => withPic(li, pick(links(li)) || (ACT[i] && briefPic(ACT[i])) || pick(links(li), true)));

  // 6. watch next: the release each item cites
  const watch = [...one.querySelectorAll(".op-box")].find(b => /Watch next/.test(b.querySelector("h4")?.textContent || ""))?.querySelector("ul");
  if (watch) [...watch.children].forEach(li => withPic(li, pick(links(li)) || pick(links(li), true)));

  one.addEventListener("click", ev => {
    const b = ev.target.closest(".ob-pic"); if (!b) return;
    ev.preventDefault(); ev.stopPropagation();
    if (window.routeEv) window.routeEv(b.dataset.href, b.dataset.label); else open(b.dataset.href, "_blank", "noopener");
  });
})();
