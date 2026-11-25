# Deployment

The report is deployed as a Vercel project running one Python function (`app/api/index.py`).

## 1. Build

```powershell
python -I report_builder/build.py
```

This writes the deployable app to `vercel_prudential_report/` (the code in `app/` plus the built `private/report.html`,
`private/corpus.md`, media and narration clips).

## 2. Environment variables (Vercel, Production, Sensitive)

| Variable | Purpose |
|---|---|
| `REPORT_USERNAME` | Sign-in username |
| `REPORT_PASSWORD` | Sign-in password |
| `GEMINI_API_KEY` | Model key for the "Ask Intelligence" chat |

Set them with the Vercel CLI from the app folder. Pass values on standard input, never on the command line:

```powershell
cmd /c "vercel env add REPORT_PASSWORD production --sensitive < value.txt"
```

The app **fails closed**: without `REPORT_USERNAME` and `REPORT_PASSWORD` nobody can sign in. Changing either value
signs everyone out, because the session cookie is derived from both.

## 3. Deploy

```powershell
cd vercel_prudential_report
vercel deploy --prod --yes
```

## 4. Check the live site

| Request | Expected |
|---|---|
| `GET /` (signed out) | 200, the sign-in page |
| `GET /api/status` (signed out) | 401 |
| `GET /private/report.html` | 404 (never served directly) |
| Sign in, then `GET /` | The report |

Before every deploy, scan the files to be uploaded for credential values (the `.env` values must never appear in any
uploaded file) and run `report_builder/check_all_links.py`.
