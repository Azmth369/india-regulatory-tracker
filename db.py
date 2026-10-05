import os
import sqlite3
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
DB_PATH = os.getenv("DATABASE_PATH", "regulatory.db")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest(path, method="GET", params=None, payload=None):
    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=_headers(),
        params=params,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json() if response.content else []


def _sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if USE_SUPABASE:
        return
    conn = _sqlite()
    conn.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE, published_at TEXT, summary TEXT, content TEXT,
        category TEXT, importance TEXT, affected_sectors TEXT, market_impact TEXT,
        action_required TEXT, ai_provider TEXT, analyzed_at TEXT, fetched_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
        provider TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def list_documents(limit=100):
    if USE_SUPABASE:
        return _rest("documents", params={
            "select": "id,source,title,url,published_at,summary,category,importance,affected_sectors,market_impact,action_required,ai_provider,analyzed_at,fetched_at",
            "order": "created_at.desc",
            "limit": limit,
        })
    conn = _sqlite()
    rows = conn.execute("""SELECT id,source,title,url,published_at,summary,category,importance,
        affected_sectors,market_impact,action_required,ai_provider,analyzed_at,fetched_at
        FROM documents ORDER BY fetched_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(document_id):
    if USE_SUPABASE:
        rows = _rest("documents", params={"select": "*", "id": f"eq.{document_id}", "limit": 1})
        return rows[0] if rows else None
    conn = _sqlite()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_documents(items):
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in items:
        rows.append({
            "source": item["source"],
            "title": item["title"],
            "url": item["url"],
            "published_at": item.get("published_at"),
            "summary": item.get("summary"),
            "content": item.get("content"),
            "fetched_at": now,
        })
    if not rows:
        return 0

    if USE_SUPABASE:
        result = _rest(
            "documents",
            method="POST",
            params={"on_conflict": "url"},
            payload=rows,
        )
        return len(result)

    conn = _sqlite()
    for row in rows:
        conn.execute("""INSERT INTO documents
            (source,title,url,published_at,summary,content,fetched_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(url) DO UPDATE SET title=excluded.title,
            published_at=excluded.published_at, content=excluded.content,
            fetched_at=excluded.fetched_at""",
            (row["source"],row["title"],row["url"],row["published_at"],
             row["summary"],row["content"],now))
    conn.commit()
    count = len(rows)
    conn.close()
    return count


def update_analysis(document_id, result, provider):
    analyzed_at = datetime.now(timezone.utc).isoformat()
    values = {
        "summary": result.get("summary"),
        "category": result.get("category"),
        "importance": result.get("importance"),
        "affected_sectors": ", ".join(result.get("affected_sectors", [])),
        "market_impact": result.get("market_impact"),
        "action_required": result.get("action_required"),
        "ai_provider": provider,
        "analyzed_at": analyzed_at,
    }
    if USE_SUPABASE:
        _rest("documents", method="PATCH", params={"id": f"eq.{document_id}"}, payload=values)
        return

    conn = _sqlite()
    conn.execute("""UPDATE documents SET summary=?,category=?,importance=?,affected_sectors=?,
        market_impact=?,action_required=?,ai_provider=?,analyzed_at=? WHERE id=?""",
        (*values.values(), document_id))
    conn.commit()
    conn.close()


def list_unanalyzed(limit=10):
    if USE_SUPABASE:
        return _rest("documents", params={
            "select": "id,title,content",
            "content": "not.is.null",
            "summary": "is.null",
            "order": "id.asc",
            "limit": limit,
        })
    conn = _sqlite()
    rows = conn.execute("""SELECT id,title,content FROM documents
        WHERE content IS NOT NULL AND length(content)>100
        AND (summary IS NULL OR summary='') ORDER BY id ASC LIMIT ?""",(limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ai_question(document_id, provider, question, answer):
    value = {
        "document_id": document_id,
        "provider": provider,
        "question": question,
        "answer": answer if isinstance(answer, str) else str(answer),
    }
    if USE_SUPABASE:
        _rest("ai_questions", method="POST", payload=[value])
        return
    conn = _sqlite()
    conn.execute("""INSERT INTO ai_questions(document_id,provider,question,answer,created_at)
        VALUES (?,?,?,?,?)""",(document_id,provider,question,value["answer"],datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
