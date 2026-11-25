/* ---------- Highlight the key insights and the most useful information, colour-coded (20 Nov 2026) ----------
   Text is not changed. Inside key-insight boxes, insight cards, strengths / weaknesses, recommendations and the detail
   panel:
     - key figures (percentages, HK$/US$ amounts, "N times") are coloured by what the sentence says about them:
       green = growth or a lead, red = a fall or a gap, blue = other key figure;
     - insurer names take their brand colour.
   A short colour key sits at the top of the Executive Summary and Insights pages. Links are left untouched. */
(function () {
  const NUM = /((?:HK|US|S)\$\s?[\d,.]+\s?(?:bn|billion|million|m)?\b|\b\d[\d,.]*\s?%|\b\d[\d,.]*(?:\.\d+)?\s?(?:times|x)\b)/;
  const BRAND = /\b(Prudential|AIA|Manulife|AXA)\b/;
  const RX = new RegExp(NUM.source + "|" + BRAND.source, "g");
  const UP = /\b(rose|rise|rising|grew|grow|growth|up|higher|highest|increase[sd]?|gain(?:ed|s)?|jump(?:ed)?|led|leads?|ahead|most|best|top|strong(?:est)?|more than|record)\b/i;
  const DOWN = /\b(fell|fall(?:ing|s)?|down|lower|lowest|decline[sd]?|drop(?:ped|s)?|slow(?:ed)?|behind|least|weak(?:est)?|only|trail(?:s|ed)?|lag(?:s|ging)?|shrink(?:ing)?|cut|loss|below)\b/i;
  const SCOPE = ".insight p, #insights .ins-grid p, .swi p, .swi .vs, .ds-content p, .ov-rec, .ov-ev, .kd .s, .fx-pane p, #modIns td";
  const lastAt = (rx, s) => { const g = new RegExp(rx.source, "gi"); let i = -1, m; while ((m = g.exec(s))) i = m.index; return i; };
  const tone = before => {
    const s = before.slice(-60), u = lastAt(UP, s), d = lastAt(DOWN, s);
    if (u < 0 && d < 0) return "nu";
    return u > d ? "up" : "dn";                   // the nearest direction word before the figure decides
  };
  const mark = root => root.querySelectorAll(SCOPE).forEach(el => {
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, { acceptNode: n => {
      RX.lastIndex = 0;
      return n.parentElement.closest("a, b.kn, b.kb, .bp-pill, .bp, script, style, .mi-pic, .ov-img-src") || !RX.test(n.nodeValue) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; } });
    const nodes = []; while (tw.nextNode()) nodes.push(tw.currentNode);
    nodes.forEach(n => {
      const s = n.nodeValue, frag = document.createDocumentFragment(); let last = 0, m;
      // the sentence so far (text before this node in the same block) helps judge direction
      const prev = (n.previousSibling?.textContent || "").slice(-60);
      RX.lastIndex = 0;
      while ((m = RX.exec(s))) {
        if (m.index > last) frag.append(s.slice(last, m.index));
        const b = document.createElement("b");
        if (BRAND.test(m[0]) && !/\d/.test(m[0])) { b.className = "kb kb-" + m[0].toLowerCase(); }
        else { b.className = "kn kn-" + tone(prev + s.slice(0, m.index)); }
        b.textContent = m[0]; frag.append(b); last = m.index + m[0].length;
      }
      if (last < s.length) frag.append(s.slice(last));
      n.replaceWith(frag);
    });
  });
  mark(document);

  // colour key at the top of the Executive Summary and the Insights page
  const KEY = `<div class="ckey" role="note"><span class="ckey-h">Colour key</span>
    <span><b class="kn kn-up">+8%</b> growth or a lead</span><span><b class="kn kn-dn">−6%</b> a fall or a gap</span><span><b class="kn kn-nu">57%</b> other key figure</span>
    <span><b class="kb kb-prudential">Prudential</b> <b class="kb kb-aia">AIA</b> <b class="kb kb-manulife">Manulife</b> <b class="kb kb-axa">AXA</b> brand colours</span>
    <span><span class="conf c-fact">Observed</span> <span class="conf c-int">Interpretation</span> <span class="conf c-sug">Suggested</span></span>
    <span><mark>highlighted</mark> = the key point</span></div>`;
  [["#es", ".ov"], ["#p6", "#modIns"]].forEach(([sec, before]) => {
    const s = document.querySelector(sec), b = s?.querySelector(before);
    if (s && !s.querySelector(".ckey")) (b?.closest(".tbl-wrap") || b || s.firstElementChild)?.insertAdjacentHTML("beforebegin", KEY);
  });

  // live panels redraw their text when filters change: re-apply shortly after (only new text is touched)
  let t = null;
  new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => mark(document), 250); })
    .observe(document.querySelector("main") || document.body, { childList: true, subtree: true });
  const ds = document.querySelector(".dsheet .ds-body");
  if (ds) new MutationObserver(() => mark(ds.parentElement)).observe(ds, { childList: true });
})();
