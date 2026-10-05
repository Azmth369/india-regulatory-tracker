# India Regulatory Tracker

Personal-use regulatory intelligence terminal for tracking Indian government and financial-regulator publications.

## Current build

- Flask web dashboard
- Supabase PostgreSQL persistence with SQLite fallback for local development
- RBI press-release ingestion with full publication-text extraction
- Correct RBI link filtering using actual press-release IDs
- Automatic refresh every 30 minutes
- Gemini and Sarvam analysis
- Defensive AI response parsing and useful API errors
- Per-document AI Q&A
- Search and importance/category filters
- Extracted-source text viewer
- Optional HTTP Basic authentication for personal use
- Render deployment configuration

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Environment variables

### Database

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` — server-only secret
- `SUPABASE_SECRET_KEY` — optional alternative server-only Supabase key
- `DATABASE_PATH` — SQLite path used only when Supabase variables are absent

### AI

- `AI_PROVIDER` — `none`, `gemini`, or `sarvam`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` — defaults to `gemini-2.5-flash`
- `SARVAM_API_KEY`
- `SARVAM_MODEL` — defaults to `sarvam-105b`

The provider can also be selected per analysis/Q&A request.

### Scheduler

- `ENABLE_SCHEDULER=true|false`
- `SCRAPE_INTERVAL_SECONDS=1800`

### Personal-use authentication

Set both variables to protect the Render app with HTTP Basic Auth:

- `TRACKER_USERNAME`
- `TRACKER_PASSWORD`

If they are not set, authentication is disabled. The `/health` endpoint remains public for Render health checks.

## Render

The included `render.yaml` runs Gunicorn with one worker and multiple threads. One worker is intentional because the current MVP contains an in-process scheduler; this prevents multiple scheduler instances.

For a larger deployment, the scheduler should be moved to a dedicated background job/worker.

## Supabase

The production app stores regulatory documents and AI Q&A history in the connected Supabase project.

Tables:

- `documents`
- `ai_questions`

Row Level Security is enabled. The browser does not connect directly to Supabase; database access is performed server-side.

## Roadmap

1. Harden RBI source-specific ingestion
2. Add SEBI
3. Add MCA
4. Add Union ministries
5. Add source/category-specific importance rules
6. Add historical search and date ranges
7. Add company/sector impact mapping
8. Add watchlists and alerts
9. Move scheduled jobs to a dedicated worker
