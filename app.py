import os
import sqlite3
from flask import Flask, jsonify, render_template, request

from scraper import scrape_rbi, save_items

app = Flask(__name__)
DB_PATH = os.getenv("DATABASE_PATH", "regulatory.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
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
    # Upgrade databases created by the first MVP.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    if "content" not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    conn.commit()
    conn.close()


@app.route("/")
def index():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, source, title, url, published_at, summary
        FROM documents
        ORDER BY COALESCE(published_at, fetched_at) DESC
        LIMIT 100
    """).fetchall()
    conn.close()
    return render_template("index.html", documents=rows)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/documents")
def documents():
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    conn = get_db()
    rows = conn.execute("""
        SELECT id, source, title, url, published_at, summary, fetched_at
        FROM documents
        ORDER BY COALESCE(published_at, fetched_at) DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.get("/api/documents/<int:document_id>")
def document(document_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "document not found"}), 404
    return jsonify(dict(row))


@app.post("/api/scrape/rbi")
def scrape_rbi_route():
    try:
        items = scrape_rbi()
        saved = save_items(items, DB_PATH)
        return jsonify({"status": "ok", "found": len(items), "saved": saved})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
