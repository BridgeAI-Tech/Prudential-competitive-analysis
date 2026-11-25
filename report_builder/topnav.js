/* ---------- InkTank-style structure (20 Nov 2026, operator's choice) ----------
   Numbered tabs across the top (1. Leadership Brief, 2. Executive Summary, ...), and each page opens with a numbered,
   upper-case heading plus the period badge. Supplementary pages follow the core tabs. Page content is unchanged. */
(function () {
  const nav = document.querySelector("nav.toc.dnav"); if (!nav) return;
  document.documentElement.classList.add("topnav");
  let n = 0;
  nav.querySelectorAll("a[href^='#']").forEach(a => {
    if (a.hasAttribute("data-open-chat")) return;
    const sec2 = a.classList.contains("sec2");
    if (!sec2) { n += 1; a.dataset.no = n; }
    const v = a.dataset.view, sec = v && document.getElementById(v), h2 = sec?.querySelector(".sec-head h2") || sec?.querySelector("h2");
    if (h2 && !h2.querySelector(".secno")) {
      if (!sec2) h2.insertAdjacentHTML("afterbegin", `<span class="secno">${n}.</span> `);
      h2.classList.add("tn-h");
      if (!h2.parentElement.querySelector(".sec-period")) h2.insertAdjacentHTML("afterend", `<span class="sec-period">Nov 2025 – Oct 2026 · 12 months</span>`);
    }
  });
  // the Ask Intelligence tab sits at the end, after the supplementary pages
  const ai = nav.querySelector("a[data-open-chat]"); if (ai) nav.appendChild(ai);
  // keep the active tab in view when switching pages
  const keep = () => nav.querySelector("a.active, a[aria-current]")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  document.addEventListener("click", e => { if (e.target.closest("nav.toc a, [data-view]")) setTimeout(keep, 60); });
  setTimeout(keep, 300);
})();
