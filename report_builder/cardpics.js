/* ---------- Pictures on the strengths / weaknesses cards and the company profile cards (20 Nov 2026) ----------
   Each card shows a screenshot of a page it links to (MOVESHOT: page screenshots and cited PDF pages) or a news
   article's lead image (NEWSIMG), never the same picture twice in a group. Card text is not changed. */
(function () {
  const base = typeof MEDIA_BASE !== "undefined" ? MEDIA_BASE : "/media/";
  const shots = typeof MOVESHOT !== "undefined" ? MOVESHOT : {};
  const news = typeof NEWSIMG !== "undefined" ? NEWSIMG : {};
  const byUrl = {}; if (typeof EVID !== "undefined") EVID.forEach(r => { if (r[10] && !byUrl[r[10]]) byUrl[r[10]] = r; });
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const imgFor = u => shots[u] || (byUrl[u] && news[byUrl[u][0]]) || null;

  function decorate(cards, used, prefer) {
    cards.forEach(card => {
      if (card.querySelector(":scope > .cp-img")) return;
      let links = [...card.querySelectorAll("a[href^='http']")];
      const isPdf = a => /\.pdf($|[?#])/i.test(a.getAttribute("href"));
      links = [...links.filter(a => !isPdf(a)), ...links.filter(isPdf)];   // a web page or article picture before a report page
      if (prefer) links = [...links.filter(prefer), ...links.filter(a => !prefer(a))];
      for (const a of links) {
        const u = a.getAttribute("href"), f = imgFor(u);
        if (!f || used.has(f)) continue;
        // two results reports share a layout: a second report picture of the same page number looks like a repeat
        const pg = isPdf(a) && (/\bp\.?\s*(\d+)/i.exec(a.textContent) || [])[1];
        if (pg && used.has("pdf-page-" + pg)) continue;
        if (pg) used.add("pdf-page-" + pg);
        used.add(f);
        const host = (u.split("/")[2] || "").replace(/^www\./, "");
        const label = a.textContent.replace(/\s+/g, " ").trim().slice(0, 40);
        card.insertAdjacentHTML("afterbegin", `<a class="cp-img" href="${e(u)}" target="_blank" rel="noopener"><img loading="lazy" src="${base}${e(f)}" alt=""><span class="ov-img-src">${e(label ? label + " · " : "")}${e(host)}</span></a>`);
        break;
      }
    });
  }
  const swUsed = new Set();
  decorate([...document.querySelectorAll("#swS .swi, #swW .swi")], swUsed);
  // Cards whose evidence is a count rather than a linked page get a picture of that evidence from the collected ad and
  // video library (media/media.json), labelled with its source (24 Nov 2026).
  const FALLBACK = {
    "Ads arrive in a year-end burst": { f: "ad_prudential_1115134424441704.jpg", u: "https://www.facebook.com/ads/library/?id=1115134424441704",
      label: "Prudential Instagram ad, 31 Oct 2026 · Meta Ad Library" },
    "Thin on Google ads and YouTube": { f: "youtube_aia_OCgQZgbx_QQ.jpg", u: "https://www.youtube.com/watch?v=OCgQZgbx_QQ",
      label: "AIA on YouTube, 12.4m views · youtube.com" },
    "Shrinking while rivals grow": { f: "news_xnr-894a2344a9c7.jpg", u: "https://www.ii.co.uk/analysis-commentary/prudential-investors-react-mixed-half-year-results-ii540104",
      label: "Investors react to mixed half-year results, 27 Aug 2026 · ii.co.uk" },
    "The historic core is lagging": { f: "doc_1152d732c37746.jpg", u: "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0827/2025082700009.pdf",
      label: "HY 2025 results, p.25 · hkexnews.hk" },
    "Engaged followers across platforms": { f: "facebook_prudential_1547833204047459.jpg", u: "https://www.facebook.com/reel/1511570627674165/",
      label: "Prudential Facebook reel, 30 Sep 2026: 2,160 likes, 41 comments · facebook.com" },
    "Trails AIA+ and Manulife": { f: "move_1d3daeb1e365b5.jpg", u: "https://apps.apple.com/hk/app/myprudential-%E8%BC%95%E9%AC%86%E7%AE%A1%E7%90%86%E6%82%A8%E7%9A%84%E4%BF%9D%E5%96%AE/id435695045?uo=4",
      label: "myPrudential on the App Store, rated 3.8 · apps.apple.com" },
  };
  document.querySelectorAll("#swS .swi, #swW .swi").forEach(card => {
    if (card.querySelector(":scope > .cp-img")) return;
    const key = Object.keys(FALLBACK).find(t => card.textContent.includes(t)); if (!key) return;
    const x = FALLBACK[key]; if (swUsed.has(x.f)) return; swUsed.add(x.f);
    card.insertAdjacentHTML("afterbegin", `<a class="cp-img" href="${e(x.u)}" target="_blank" rel="noopener"><img loading="lazy" src="${base}${e(x.f)}" alt=""><span class="ov-img-src">${e(x.label)}</span></a>`);
  });
  // company profiles: the insurer's own website first, then its releases
  decorate([...document.querySelectorAll("#cogrid .cocard")], new Set(), a => /^website$/i.test(a.textContent.trim()) || /homepage|home page/i.test(a.textContent));
})();
