import os
import sqlite3
import time
from datetime import datetime, timezone

from ai import analyze_document
from scraper import scrape_rbi, save_items

DB_PATH = os.getenv("DATABASE_PATH", "regulatory.db")
INTERVAL_SECONDS = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "1800"))


def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_at TEXT,
            summary TEXT,
            content TEXT,
            fetched_at TEXT NOT NULL
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    if "content" not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    conn.commit()
    conn.close()


def enrich_new_documents():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, content
        FROM documents
        WHERE content IS NOT NULL AND length(content) > 100
          AND (summary IS NULL OR summary = '')
        ORDER BY id ASC
        LIMIT 10
    """).fetchall()
    conn.close()

    count = 0
    for row in rows:
        try:
            result = analyze_document(row["title"], row["content"])
            if result and result.get("summary"):
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "UPDATE documents SET summary = ? WHERE id = ?",
                    (result["summary"], row["id"])
                )
                conn.commit()
                conn.close()
                count += 1
        except Exception as exc:
            print(f"AI enrichment failed for document {row['id']}: {exc}")
    return count


def run_once():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checking RBI...")
    try:
        items = scrape_rbi()
        saved = save_items(items, DB_PATH)
        analyzed = enrich_new_documents()
        print(f"RBI check complete: {len(items)} found, {saved} saved/updated, {analyzed} analyzed")
    except Exception as exc:
        print(f"RBI check failed: {exc}")


if __name__ == "__main__":
    ensure_db()
    run_once()
    while True:
        time.sleep(INTERVAL_SECONDS)
        run_once()
