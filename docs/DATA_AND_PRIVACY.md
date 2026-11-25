# Data and privacy

This is a **public repository**, so it contains code and documentation only.

## Kept out of the repository

| Item | Why |
|---|---|
| Built report (`private/report.html`) and chat knowledge base (`private/corpus.md`) | Client deliverable |
| Report content files (`body.html`, `data.js`, `dashboard.js`) | Client analysis, narrative and evidence data |
| Collected data (`data/`, `*.db`, `*.jsonl`, `*.xlsx`, Apify exports, insights) | Collected and licensed research data |
| Media and narration (`media/`, `narration/`) | Page captures, ad creatives and recorded audio |
| Credentials (`.env`, `.report-access.env`, Vercel settings) | Secrets |
| Press-office contact details | Personal data: read at run time from a git-ignored `media_contacts.local.json` |
| The earlier Next.js prototype (`web/`) | Superseded, and it bundles collected data |

`.gitignore` enforces these exclusions.

## How personal data is handled

- Press releases often end with a media-contact block (names, mobile numbers, emails). Before the report or the chat
  knowledge base is built, all email addresses and Hong Kong phone numbers are stripped, and the build asserts that
  none remain.
- The chat is instructed never to share personal contact details.

## How sources are collected

- Public pages only. Logins are not bypassed and bot protections (for example Cloudflare challenges) are not
  circumvented; such sources are recorded as unavailable or collected from the Internet Archive where a public copy
  exists.
- Licensed research data is labelled as such in the report and is never published in this repository.
