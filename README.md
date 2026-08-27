# FAi-PRISM

**Product Recommendation Impact & Sales Metrics** - FieldAssist's PR impact dashboard.

Upload a PR Impact Report (`.xlsx`), choose the comparison window, and get a full
analysis plus a client-ready recommendation report - all computed exactly from the
report (deterministic, no AI in the numbers).

## Run locally
```bash
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\app.py
# open http://127.0.0.1:5000
```

## Deploy (Render)
Connect this repo to Render as a **Blueprint** - `render.yaml` configures gunicorn +
Python 3.12. Start on the free plan to test; move to **Starter** (always-on, >=1 GB RAM)
for the CST team so there is no cold-start wait and large reports have headroom.

## How it works
```
Upload .xlsx -> pick reference window(s) -> analysis (exact metrics) -> question flow -> report
```

## Structure
- `src/` - engine: `loader` (fast read + aggregate), `factpack` (metrics), `blocks` +
  `render` (report), `assemble` (question -> report), `excel_report` (analysis workbook),
  and `app.py` (Flask server + API).
- `web/` - the dashboard UI: upload / analysis / recommendation.

Per-user sessions keep concurrent uploads isolated. `data/` and `output/` are runtime
folders (git-ignored) and are created automatically.
