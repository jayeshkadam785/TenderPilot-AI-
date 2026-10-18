# TenderPilot AI — MVP starter

TenderPilot AI helps MSMEs review public tender opportunities, screen requirements, track deadline/corrigendum changes, identify document-pack gaps, and flag EMD for human approval.

## Project files

- `index.html` — the existing TenderPilot AI frontend, kept as a single HTML file with CSV export enabled.
- `backend/main.py` — FastAPI starter API: health check, synthetic demo tender endpoint, and rule-based notice analyzer.
- `backend/requirements.txt` — Python dependencies.
- `backend/.env.example` — placeholders for future integrations; contains no secrets.

## Important status

This is an MVP starter, not a live tender-monitoring service. The frontend remains unchanged and is not yet connected to the backend endpoints. The API returns synthetic demo tender data and uses simple pattern matching; it does not access government portals, verify corrigenda, use Gemini, or connect to Supabase. Never treat its extracted dates/amounts as verified. A production build needs permitted official data sources, source snapshots/evidence, document downloading and parsing, persistent storage, scheduled checks, and security review.

## Run the frontend

Open `index.html` in Chrome or Edge. CSV export works in the browser. To avoid browser-origin limitations when testing APIs, serve the folder locally:

```bash
python -m http.server 5500
```

Then open `http://localhost:5500`.

## Run the backend (Python 3.10+)

From the project root:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

If Python reports that `backend` is not a package, create an empty `backend/__init__.py` file and retry.

API URLs:

- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/tenders`
- Interactive API docs: `http://127.0.0.1:8000/docs`

Example analyze request (Swagger UI at `/docs` is easiest):

```json
{
  "title": "IT services tender",
  "source_url": "https://example.gov.in/tender-notice",
  "notice_text": "Bid submission deadline: 25/10/2026. EMD: ₹50,000. Minimum annual turnover ₹20 lakh. Similar work experience 2 years. Submit GST certificate and work order."
}
```

The example source URL is illustrative; do not treat it as a real tender source.

## Upload to GitHub

1. Extract the ZIP file.
2. Sign in to GitHub and create a **new empty repository** named `TenderPilot-AI` (do not initialize it with a README if you plan to upload this README).
3. In the repository, choose **Add file → Upload files**.
4. Upload the contents of the extracted `TenderPilot_AI_GitHub_Project` folder (upload `index.html`, `README.md`, `.gitignore`, and the `backend` folder—not the ZIP itself).
5. Commit the upload with a message such as `Add TenderPilot AI MVP frontend and API starter`.

### Optional: publish the static frontend

For GitHub Pages, open repository **Settings → Pages**, choose deployment from the `main` branch and `/ (root)`, then save. The HTML frontend will be hosted as a static site; this does **not** deploy the Python backend. Deploy the backend separately to a Python-capable host and configure allowed CORS origins to your real frontend domain before connecting them.

## Safety and trust rules

- Only use public sources that permit automated access; respect terms, rate limits, and robots rules.
- Store official source URL, fetch time, document version/hash, and evidence snippet for each extracted fact.
- Mark deadlines `UNVERIFIED` until checked against the latest official notice/corrigendum.
- Mark packs `INCOMPLETE` when a required annexure/document is missing.
- Flag EMD for human approval; do not initiate payments automatically.
- Do not bypass logins, OTP, CAPTCHAs, or access controls.
- Keep all API keys server-side. Never commit `.env` or Supabase service-role credentials. Enable database row-level security before storing user data.
