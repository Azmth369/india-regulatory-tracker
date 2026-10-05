# India Regulatory Tracker

Render-ready prototype for collecting Indian regulatory/public-sector updates.

## MVP

- Flask web application
- SQLite persistence
- RBI scraper with publication content extraction
- Optional Gemini AI analysis
- JSON API
- Render deployment configuration
- Persistent Render disk for SQLite data

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

Scrape RBI:

```bash
curl -X POST http://localhost:5000/api/scrape/rbi
```

Analyze a document:

```bash
curl -X POST http://localhost:5000/api/analyze/1
```

## Environment variables

- `DATABASE_PATH` — SQLite path; Render uses `/var/data/regulatory.db`
- `GEMINI_API_KEY` — optional Gemini API key
- `GEMINI_MODEL` — optional model name, defaults to `gemini-2.5-flash`

Without an AI key, the tracker still works; AI enrichment returns a skipped response.

## Render

The included `render.yaml` creates a Python web service using Gunicorn and a 1 GB persistent disk.

Next: scheduled ingestion, automatic AI enrichment, better source-specific parsers, and additional sources such as SEBI, MCA and ministries.
