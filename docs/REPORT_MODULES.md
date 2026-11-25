# Report modules

The report is one self-contained HTML page. `report_builder/build.py` injects the **design layers** into `<head>` and
the **page modules** after the data, in the order below. Later layers build on earlier ones, so the order matters.
Modules change presentation only: insight text and numbers come from the data and content.

## Design layers (CSS, in load order)

| File | Purpose |
|---|---|
| `visual.css` | White space, galleries and progressive-disclosure styles |
| `theme.css` | Design tokens (colours, cards, borders) and layout patterns |
| `stitch.css` | Stitch design system: typography (incl. JetBrains Mono for headings) and components |
| `explorer.css` | Interactive layer: numbered rows, evidence explorer, mainland-social section, card pictures |
| `pritesh.css` | Final monochrome enterprise skin, loaded last; layout fixes (balanced grids, side-by-side panels, equal-height cards) |

## Page modules (JS, in load order)

| Module | What it does |
|---|---|
| `visual.js` | Visual layer: source galleries with a lightbox, progressive disclosure of explainers and detail |
| `overview.js` | Executive overview built from the dashboard's own data: source strip, takeaways and key figures |
| `captures.js` | Live captures wall: real screenshots of the pages behind the evidence, plus ads, posts and videos, filterable by channel |
| `explorer.js` | Findings explorer: insight cards re-hosted in a filterable, numbered layout with an evidence panel |
| `news.js` | News in pictures: every news or newsroom record with a lead image, title, source and links |
| `cardpics.js` | Pictures on the strengths and gaps cards and the company profile cards, never the same picture twice in a group |
| `sheet.js` | Image-first cards and the detail panel ("Tap for detail"); equal card heights in the strengths and gaps columns |
| `highlight.js` | Colour-codes the key insights and the most useful figures without changing the text |
| `cnsoc.js` | Mainland social conversation: Little Red Book (Xiaohongshu) and WeChat posts, share of conversation, filters |
| `geo.js` | Physical footprint: scorecards, district map, district table and location moves |
| `linkthumbs.js` | Small pictures beside sources in lists and tables (top posts, app ratings, product line-up) |
| `brief.js` | Pictures on the Leadership Brief: bottom line, company rows, results documents, actions, watch list |
| `modcards.js` | Module cards: each module's key insight as a picture, the companies involved and a one-line headline |
| `topnav.js` | Numbered tabs across the top (1. Leadership Brief, 2. Executive Summary, …) and page headings |
| `order.js` | Review-call improvements: charts and metrics first, evidence back button, "See more" controls, platform filters, balanced card grids |
| `chartstop.js` | Moves charts to the top of each section and pairs related panels side by side |

## Built from the data (private)

The dashboard logic (charts, heat tables, timeline, filters, coverage tables) lives in the private content file
`dashboard.js`, because it embeds report narrative. See [ARCHITECTURE.md](ARCHITECTURE.md#inputs-the-builder-expects).

## Chat

`system_prompt.txt` sets the rules for "Ask Intelligence": answer only from the knowledge base, cite sources with links,
keep facts and inferences apart, and never share personal contact details.
