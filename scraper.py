import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

RBI_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
HEADERS = {
    "User-Agent": "IndiaRegulatoryTracker/0.2 (+https://github.com/Azmth369/india-regulatory-tracker)"
}


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def extract_date(text):
    patterns = [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def parse_publication_page(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = clean_text(soup.get_text(" ", strip=True))
    return {
        "published_at": extract_date(text),
        "content": text[:12000],
    }


def scrape_rbi(limit=50):
    response = requests.get(RBI_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    items, seen = [], set()
    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = urljoin(RBI_URL, link["href"])

        if not title or len(title) < 10 or href in seen:
            continue
        if "rbi.org.in" not in href:
            continue

        lower = title.lower()
        if not any(word in lower for word in (
            "press release", "notification", "circular", "reserve bank"
        )):
            continue

        seen.add(href)
        item = {
            "source": "RBI",
            "title": title,
            "url": href,
            "published_at": None,
            "summary": None,
            "content": None,
        }

        try:
            page = parse_publication_page(href)
            item.update(page)
        except requests.RequestException:
            pass

        items.append(item)
        if len(items) >= limit:
            break

    return items


def save_items(items, db_path):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    inserted = 0

    for item in items:
        conn.execute("""
            INSERT INTO documents
                (source, title, url, published_at, summary, content, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                published_at=excluded.published_at,
                content=excluded.content,
                fetched_at=excluded.fetched_at
        """, (
            item["source"], item["title"], item["url"],
            item.get("published_at"), item.get("summary"),
            item.get("content"), now,
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted
