import time
from datetime import datetime, timezone

from ai import analyze_document
from db import list_unanalyzed, update_analysis
from scraper import scrape_rbi, save_items


def enrich_new_documents():
    rows = list_unanalyzed(10)
    count = 0
    for row in rows:
        try:
            result = analyze_document(row.get("title"), row.get("content"))
            if result and result.get("summary"):
                from ai import AI_PROVIDER
                update_analysis(row["id"], result, AI_PROVIDER)
                count += 1
        except Exception as exc:
            print(f"AI enrichment failed for document {row.get('id')}: {exc}")
    return count


def run_once():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checking RBI...")
    try:
        items = scrape_rbi()
        saved = save_items(items, None)
        analyzed = enrich_new_documents()
        print(f"RBI check complete: {len(items)} found, {saved} saved/updated, {analyzed} analyzed")
    except Exception as exc:
        print(f"RBI check failed: {exc}")


if __name__ == "__main__":
    run_once()
    while True:
        time.sleep(1800)
        run_once()
