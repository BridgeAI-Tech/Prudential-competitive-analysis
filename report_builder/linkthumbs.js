/* ---------- Pictures beside sources in lists and tables (20 Nov 2026) ----------
   Most engaging posts, app ratings (store pages) and the health and critical illness line-up (product pages): each
   source link gets a small picture of its page (screenshot, post image or article image). Clicking the picture opens
   the evidence record (larger picture, details, original link). Text and links are unchanged. */
(function () {
  if (typeof window.EVIMG !== "function") return;
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const th = a => { const u = a.getAttribute("href"), f = window.EVIMG(u);
    return f ? `<span class="lt-th" role="button" tabindex="0" title="Open the evidence record" data-u="${e(u)}" data-l="${e(a.textContent.trim())}"><img loading="lazy" src="${f}" alt=""></span>` : ""; };
  const run = () => {
    // most engaging posts: picture at the start of each item
    document.querySelectorAll("#topPosts li").forEach(li => { if (li.dataset.lt) return; li.dataset.lt = "1";
      const a = li.querySelector("a[href^='http']"); if (!a) return; const h = th(a); if (!h) return;
      const body = document.createElement("div"); while (li.firstChild) body.appendChild(li.firstChild); li.insertAdjacentHTML("afterbegin", h); li.appendChild(body); });
    // app ratings: picture of the store page in the App column
    document.querySelectorAll("#appTbl tbody tr").forEach(tr => { if (tr.dataset.lt) return; tr.dataset.lt = "1";
      const a = tr.querySelector("a[href^='http']"), cell = tr.cells[1]; if (!a || !cell) return; const h = th(a); if (h) cell.insertAdjacentHTML("afterbegin", h); });
    // health and CI line-up: each product link becomes picture + name
    document.querySelectorAll("#hciLineup tbody td a[href^='http']").forEach(a => { if (a.closest(".lt-item")) return;
      const h = th(a); if (!h) return; const w = document.createElement("span"); w.className = "lt-item"; a.replaceWith(w); w.insertAdjacentHTML("afterbegin", h); w.appendChild(a); });
  };
  run();
  ["#topPosts", "#appTbl tbody", "#hciLineup tbody"].forEach(s => { const el = document.querySelector(s); if (el) new MutationObserver(() => { clearTimeout(el._lt); el._lt = setTimeout(run, 120); }).observe(el, { childList: true }); });
  const go = ev => { const p = ev.target.closest(".lt-th"); if (!p) return; ev.preventDefault(); ev.stopPropagation(); window.routeEv?.(p.dataset.u, p.dataset.l); };
  document.addEventListener("click", go, true);
  document.addEventListener("keydown", ev => { if (ev.key === "Enter") go(ev); }, true);
})();
