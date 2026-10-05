import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

RBI_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
HEADERS = {
    "User-Agent": "IndiaRegulatoryTracker/1.0 (+https://github.com/Azmth369/india-regulatory-tracker)",
    "Accept": "text/html,application/xhtml+xml",
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

    for tag in soup(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("div", id=re.compile("content", re.I))
        or soup.body
        or soup
    )
    text = clean_text(main.get_text(" ", strip=True))

    return {
        "published_at": extract_date(text),
        "content": text[:16000],
    }


def _is_press_release_link(href):
    # Current RBI press-release entries use BS_PressReleaseDisplay.aspx?prid=...
    return "rbi.org.in" in href.lower() and "bs_pressreleasedisplay.aspx?prid=" in href.lower()


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
        if not _is_press_release_link(href):
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
            item.update(parse_publication_page(href))
        except requests.RequestException:
            pass

        items.append(item)
        if len(items) >= limit:
            break

    return items


def save_items(items, db_path=None):
    from db import cleanup_rbi_noise, upsert_documents

    saved = upsert_documents(items)
    cleanup_rbi_noise()
    return saved
