import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

RBI_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; IndiaRegulatoryTracker/0.1; "
        "+https://github.com/Azmth369/india-regulatory-tracker)"
    )
}


def clean_text(value):
    return re.sub(r"\\s+", " ", value or "").strip()


def scrape_rbi():
    response = requests.get(RBI_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = urljoin(RBI_URL, link["href"])

        if not title or len(title) < 10:
            continue
        if href in seen:
            continue
        if "rbi.org.in" not in href:
            continue

        lower = title.lower()
        if not any(word in lower for word in (
            "press release", "notification", "circular", "rbi", "reserve bank"
        )):
            continue

        seen.add(href)
        items.append({
            "source": "RBI",
            "title": title,
            "url": href,
            "published_at": None,
            "summary": None,
        })

        if len(items) >= 50:
            break

    return items


def save_items(items, db_path):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    inserted = 0

    for item in items:
        try:
            conn.execute("""
                INSERT INTO documents
                    (source, title, url, published_at, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    published_at=excluded.published_at,
                    summary=excluded.summary
            """, (
                item["source"],
                item["title"],
                item["url"],
                item.get("published_at"),
                item.get("summary"),
                now,
            ))
            inserted += 1
        except sqlite3.Error:
            continue

    conn.commit()
    conn.close()
    return inserted
