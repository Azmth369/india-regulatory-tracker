# India Regulatory Tracker

A Render-ready prototype for collecting Indian regulatory/public-sector updates.

## Current MVP

- Flask web application
- SQLite persistence
- RBI source prototype
- JSON API
- Manual RBI scrape endpoint
- Render deployment configuration
- Persistent Render disk for SQLite data

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

Populate RBI data:

```bash
curl -X POST http://localhost:5000/api/scrape/rbi
```

## API

- `GET /health`
- `GET /api/documents?limit=50`
- `POST /api/scrape/rbi`

## Render

The included `render.yaml` creates a Python web service using Gunicorn and a 1 GB persistent disk mounted at `/var/data`.

For the next iteration, the project can add scheduled scraping, source-specific parsers, deduplication improvements, document/PDF extraction, and optional Gemini/Sarvam summarization.
