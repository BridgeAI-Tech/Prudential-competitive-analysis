/* ---------- Charts and graphs at the top (22 Nov 2026, operator request; Pritesh/InkTank layout) ----------
   In every section the charts (with their heading, short explainer and legend) move to the top: right after the section
   title and its key-insight / "if you do one thing" strip, under a "Visual analytics" heading. In the executive summary the
   KPI tiles and charts move above the takeaway cards. Nothing is removed or re-rendered: the same DOM nodes are moved, so
   chart data, clicks and evidence links keep working. Tabbed content (Products "hci-off" panes) and galleries are left alone. */
(function () {
  const qa = (s, r = document) => [...r.querySelectorAll(s)];
  const big = s => {
    const w = +(s.getAttribute("width") || 0), vb = s.viewBox && s.viewBox.baseVal ? s.viewBox.baseVal.width : 0;
    const r = s.getBoundingClientRect().width;
    return Math.max(w, vb, r) >= 140;
  };
  const isChart = el => el && el.nodeType === 1 && !el.matches(".hci-off, .sup-wrap, details, .tbl-wrap, .insight, .ov, nav, .fbar") &&
    (el.matches("canvas") || el.querySelector("canvas") || (el.matches("svg") && big(el)) || qa("svg", el).some(big) || el.matches("#tiles, .tiles, .kpis, #appSummary, #appRatings"));
  const HEAD = ".vhead, .sec-head, #evBarHold, .onestrip, .ckey, .insight.mc, .ct-h";
  const LEAD = "button.pd-more, p.muted.small, p.small.muted";

  function arrange(sec) {
    if (sec.dataset.ctDone) return;
    const kids = [...sec.children];
    // anchor: the run of heading / key-message blocks at the top of the section
    let anchor = null;
    const first = kids.findIndex(k => k.matches(HEAD));        // the title block may follow a pinned "what changed" table (Competitor activity)
    if (first < 0) return;
    for (const k of kids.slice(first)) { if (k.matches(HEAD)) anchor = k; else break; }
    if (!anchor) return;
    const start = kids.indexOf(anchor);
    const groups = [];
    kids.forEach((c, i) => {
      if (i <= start || !isChart(c)) return;
      const g = [c];
      let p = c.previousElementSibling;                       // heading + explainer that introduce the chart
      while (p && kids.indexOf(p) > start && !g.includes(p) && (p.matches(LEAD) || p.matches("h3, h4"))) {
        if (p.matches(".hci-off")) break;
        g.unshift(p);
        if (p.matches("h3, h4")) break;
        p = p.previousElementSibling;
      }
      let n = c.nextElementSibling;                           // legend / note that belongs to the chart
      while (n && (n.matches(".legend, .heat-note") || (c.matches("#tiles") && n.matches("p.small.muted")))) { g.push(n); n = n.nextElementSibling; }
      groups.push(g);
    });
    // executive summary: the InkTank "war room" charts inside the overview block come up as well
    const war = sec.querySelector(".ov .ov-war");
    if (war) groups.unshift([war]);
    // visuals pinned above the section title (Competitor activity heatmap) go under the title, first in the visual block
    const pre = kids.slice(0, first);
    if (pre.length) groups.unshift(pre);
    const flat = [...new Set(groups.flat())];
    if (!flat.length) return;
    const h = document.createElement("h3");
    h.className = "ct-h"; h.textContent = "Visual analytics";
    let at = anchor;
    at.insertAdjacentElement("afterend", h); at = h;
    flat.forEach(el => { at.insertAdjacentElement("afterend", el); el.classList.add("ct-moved"); at = el; });
    sec.dataset.ctDone = "1";
  }

  // Brand & campaigns: engagement-by-month line chart and median-engagement bar chart side by side (operator, 22 Nov 2026);
  // the "most engaging posts" list keeps its own full-width row underneath.
  function pairEngagement() {
    const er = document.getElementById("erMonth"), lk = document.getElementById("likes");
    if (!er || !lk || document.querySelector(".ct-pair")) return;
    const erCard = er.closest(".card"), lkCard = lk.closest(".card"), grid = lkCard && lkCard.parentElement;
    if (!erCard || !lkCard || !grid) return;
    const lead = [];
    let p = erCard.previousElementSibling;
    while (p && !p.matches(".ct-h") && (p.matches(LEAD) || p.matches("h3, h4"))) { lead.unshift(p); if (p.matches("h3, h4")) break; p = p.previousElementSibling; }
    const pair = document.createElement("div"); pair.className = "ct-pair ct-moved";
    const left = document.createElement("div"); left.className = "ct-col";
    const right = document.createElement("div"); right.className = "ct-col ct-col-r";
    // both panels get the same structure: title (+LIVE) -> subtitle / how-to-read -> chart -> legend.
    // The line chart's heading, "how to read" button and explainer move inside its card, like the bar chart's title.
    erCard.insertAdjacentElement("beforebegin", pair);
    const head = document.createElement("div"); head.className = "ct-card-head";
    lead.forEach(el => { if (el.matches("h3, h4")) el.classList.add("ct-card-title"); head.append(el); });
    if (lead.length) erCard.prepend(head);
    const lkTitle = lkCard.querySelector(".chart-title"), lkSub = lkCard.querySelector(":scope > .small.muted");
    if (lkTitle) { const h2 = document.createElement("div"); h2.className = "ct-card-head"; h2.append(lkTitle); if (lkSub) h2.append(lkSub); lkCard.prepend(h2); }
    erCard.classList.add("ct-panel"); lkCard.classList.add("ct-panel", "ct-panel-bars");
    // two equal panels, one chart each (the bar chart is drawn at the line chart's shape in dashboard.js, so both are the same size);
    // "most engaging posts" moves to the top right under the charts (review call feedback)
    left.append(erCard); right.append(lkCard); pair.append(left, right);
    grid.classList.add("ct-single");
    const tp = document.getElementById("topPosts");
    const tpCard = tp ? tp.closest(".card") : null;
    if (tpCard && tpCard !== erCard && tpCard !== lkCard) {
      pair.insertAdjacentElement("afterend", tpCard);
      tpCard.classList.add("ct-moved", "ct-top-posts");
    }
  }

  // heatmap tables that read as charts join the visual block (operator, 22 Nov 2026): theme x brand share / engagement
  function moveHeatmaps() {
    ["themeTbl"].forEach(id => {
      const t = document.getElementById(id); if (!t || t.dataset.ctHeat) return;
      const wrap = t.closest(".tbl-wrap") || t, sec = wrap.closest("section"); if (!sec) return;
      const g = [wrap]; let p = wrap.previousElementSibling;
      while (p && (p.matches(LEAD) || p.matches("h3, h4"))) { g.unshift(p); if (p.matches("h3, h4")) break; p = p.previousElementSibling; }
      let at = sec.querySelector(":scope > .ct-pair") || sec.querySelector(":scope > .ct-h");
      if (!at) return;
      g.forEach(el => { at.insertAdjacentElement("afterend", el); el.classList.add("ct-moved"); at = el; });
      t.dataset.ctHeat = "1";
    });
  }

  // two related tables side by side in compact, matching panels (operator, 22 Nov 2026)
  const TABLE_PAIRS = [["narrTbl", "ctaTbl"],           // Brand & campaigns: emotional positioning | calls to action
                       [/What works, by brand and type of post/i, /responded to the Tai Po fire/i, "ct-fire"]];   // Social, ads & search
  // a table by id, or by the h3 heading that introduces it
  const tableOf = k => {
    if (typeof k === "string") return document.getElementById(k);
    const h = qa("main section h3").find(x => k.test(x.textContent)); if (!h) return null;
    let n = h.nextElementSibling;
    while (n && !n.matches(".tbl-wrap, table") && !n.matches("h3")) n = n.nextElementSibling;
    return n && !n.matches("h3") ? (n.matches("table") ? n : n.querySelector("table")) : null;
  };
  function pairTables() {
    TABLE_PAIRS.forEach(([a, b, extra]) => {
      const ta = tableOf(a), tb = tableOf(b);
      if (!ta || !tb || ta.dataset.ctPair) return;
      if (extra) tb.classList.add(extra);
      const pairCls = extra ? extra + "-pair" : "";
      const grab = t => {
        const wrap = t.closest(".tbl-wrap") || t, g = [wrap]; let p = wrap.previousElementSibling;
        while (p && (p.matches(LEAD) || p.matches("h3, h4"))) { g.unshift(p); if (p.matches("h3, h4")) break; p = p.previousElementSibling; }
        return g;
      };
      const ga = grab(ta), gb = grab(tb);
      const pair = document.createElement("div"); pair.className = "ct-pair ct-tpair" + (pairCls ? " " + pairCls : "");
      ga[0].insertAdjacentElement("beforebegin", pair);
      [ga, gb].forEach(g => {
        const col = document.createElement("div"); col.className = "ct-col";
        const panel = document.createElement("div"); panel.className = "card ct-panel ct-tpanel";
        const head = document.createElement("div"); head.className = "ct-card-head";
        g.forEach(el => { if (el.matches(".tbl-wrap, table")) return; if (el.matches("h3, h4")) el.classList.add("ct-card-title"); head.append(el); });
        panel.append(head, g[g.length - 1]); col.append(panel); pair.append(col);
      });
      ta.dataset.ctPair = "1";
    });
  }

  // Social, ads & search: Google searches month by month (chart) | ads running by start month (table), as two equal panels
  // at the top. The chart's title and Chinese / English toggle were left behind by the generic move; they join its panel header.
  function pairSearch() {
    const dp = document.getElementById("dpTrend"); if (!dp || document.querySelector(".ct-spair")) return;
    const dpCard = dp.closest(".card"), sec = dp.closest("section"); if (!dpCard || !sec) return;
    const h3s = qa(":scope > h3", sec);
    const dpH = h3s.find(h => /Google searches in Hong Kong/i.test(h.textContent));
    const adsH = h3s.find(h => /ads running on/i.test(h.textContent));
    const adsCard = adsH && adsH.nextElementSibling && adsH.nextElementSibling.matches(".card, .tbl-wrap") ? adsH.nextElementSibling : null;
    const pair = document.createElement("div"); pair.className = "ct-pair ct-spair ct-moved";
    dpCard.insertAdjacentElement("beforebegin", pair);
    const panel = (card, h, extras) => {
      const col = document.createElement("div"); col.className = "ct-col";
      const head = document.createElement("div"); head.className = "ct-card-head";
      if (h) { h.classList.add("ct-card-title"); head.append(h); }
      extras.forEach(x => x && head.append(x));
      card.classList.add("ct-panel"); card.prepend(head); col.append(card); return col;
    };
    const toggle = dpH && dpH.nextElementSibling && dpH.nextElementSibling.querySelector("button") && !dpH.nextElementSibling.matches(".card") ? dpH.nextElementSibling : null;
    const how = dpCard.querySelector(":scope > button.pd-more"), howP = how && how.nextElementSibling && how.nextElementSibling.matches("p, .small") ? how.nextElementSibling : null;
    if (toggle) toggle.classList.add("ct-toggle");
    pair.append(panel(dpCard, dpH, [toggle, how, howP]));
    if (adsCard) { adsCard.classList.add("ct-tpanel"); pair.append(panel(adsCard, adsH, [])); }
    else pair.classList.add("ct-pair-one");
  }


  // Competitor activity: "What kind of activity" table | moves timeline chart, side by side (24 Nov 2026)
  function pairActivity() {
    const h = document.getElementById("mixTop"), tw = document.getElementById("mixTbl")?.closest(".tbl-wrap"), sw = document.getElementById("swimCard");
    if (!h || !tw || !sw || h.closest(".ct-apair")) return;
    const a = [h]; let n = h.nextElementSibling;
    while (n && n !== tw && n.matches(LEAD)) { a.push(n); n = n.nextElementSibling; }
    const note = tw.nextElementSibling && tw.nextElementSibling.matches("p.small.muted, p.muted.small") ? tw.nextElementSibling : null;
    const leg = document.getElementById("swimLegend");
    const pair = document.createElement("div"); pair.className = "ct-pair ct-apair";
    h.insertAdjacentElement("beforebegin", pair);
    const colA = document.createElement("div"); colA.className = "ct-col";
    const panel = document.createElement("div"); panel.className = "card ct-panel ct-tpanel";
    const head = document.createElement("div"); head.className = "ct-card-head";
    a.forEach(el => { if (el.matches("h3, h4")) el.classList.add("ct-card-title"); head.append(el); });
    panel.append(head, tw); if (note) panel.append(note); colA.append(panel);
    const colB = document.createElement("div"); colB.className = "ct-col";
    colB.append(sw); if (leg) colB.append(leg);
    pair.append(colA, colB);
  }
  const run = () => { qa("main > section.view, main > section.sec").forEach(arrange); pairEngagement(); moveHeatmaps(); pairTables(); pairSearch(); pairActivity(); };
  if (document.readyState === "complete") setTimeout(run, 700);
  else window.addEventListener("load", () => setTimeout(run, 700));
  // sections drawn later (tab switches) get the same layout
  document.addEventListener("click", e => { if (e.target.closest("nav a, [data-view]")) setTimeout(run, 600); });
})();
