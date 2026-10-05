import os
import threading
import time

from flask import Flask, jsonify, render_template, request

from ai import AIError, AI_PROVIDER, ask_with_gemini, ask_with_sarvam, analyze_document
from db import get_document, init_db, list_documents, save_ai_question, update_analysis
from scraper import scrape_rbi, save_items
from worker import run_once

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@app.route("/")
def index():
    return render_template("index.html", documents=list_documents(100))


@app.route("/health")
def health():
    configured = {
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "sarvam": bool(os.getenv("SARVAM_API_KEY")),
    }
    return jsonify({
        "status": "ok",
        "database": "supabase" if os.getenv("SUPABASE_URL") and (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
        ) else "sqlite",
        "ai": configured,
        "default_provider": AI_PROVIDER,
    })


@app.get("/api/documents")
def documents():
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    return jsonify(list_documents(limit))


@app.get("/api/documents/<int:document_id>")
def document(document_id):
    row = get_document(document_id)
    if row is None:
        return jsonify({"error": "document not found"}), 404
    return jsonify(row)


@app.post("/api/analyze/<int:document_id>")
def analyze(document_id):
    row = get_document(document_id)
    if row is None:
        return jsonify({"error": "document not found"}), 404

    try:
        provider = request.args.get("provider")
        if not provider and request.is_json:
            provider = (request.get_json(silent=True) or {}).get("provider")
        provider = (provider or AI_PROVIDER).lower()

        if provider not in ("gemini", "sarvam"):
            return jsonify({"status": "error", "error": "Select Gemini or Sarvam."}), 400

        result = analyze_document(row.get("title"), row.get("content"), provider=provider)
        if result is None:
            return jsonify({"status": "error", "error": f"{provider} is not configured."}), 400

        update_analysis(document_id, result, provider)
        return jsonify({
            "status": "ok",
            "document_id": document_id,
            "analysis": result,
            "provider": provider,
        })
    except AIError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 502
    except Exception as exc:
        app.logger.exception("Analysis failed")
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.post("/api/ask/<int:document_id>")
def ask_ai(document_id):
    row = get_document(document_id)
    if row is None:
        return jsonify({"error": "document not found"}), 404

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    provider = (payload.get("provider") or request.args.get("provider") or AI_PROVIDER).lower()

    if not question:
        return jsonify({"error": "question is required"}), 400
    if provider not in ("gemini", "sarvam"):
        return jsonify({"error": "select Gemini or Sarvam"}), 400
    if not row.get("content"):
        return jsonify({"error": "This document has no extracted content."}), 400

    prompt = f"""You are an Indian regulatory intelligence analyst.
Answer the user's question using ONLY the RBI publication below. Do not invent facts.
If the publication does not contain enough information, say so clearly.

Publication title: {row.get("title")}
Publication:
{(row.get("content") or "")[:16000]}

User question:
{question}

Give a concise, practical answer. Mention important dates, thresholds, entities or obligations when relevant.
"""

    try:
        answer = ask_with_gemini(prompt) if provider == "gemini" else ask_with_sarvam(prompt)
        save_ai_question(document_id, provider, question, answer)
        return jsonify({"status": "ok", "provider": provider, "answer": answer})
    except AIError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 502
    except Exception as exc:
        app.logger.exception("AI question failed")
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.post("/api/scrape/rbi")
def scrape_rbi_route():
    try:
        items = scrape_rbi()
        saved = save_items(items, None)
        return jsonify({
            "status": "ok",
            "found": len(items),
            "saved": saved,
            "message": "RBI press releases refreshed.",
        })
    except Exception as exc:
        app.logger.exception("RBI scrape failed")
        return jsonify({"status": "error", "error": str(exc)}), 500


def start_scheduler():
    if os.getenv("ENABLE_SCHEDULER", "true").lower() != "true":
        return

    def loop():
        interval = max(int(os.getenv("SCRAPE_INTERVAL_SECONDS", "1800")), 300)
        time.sleep(10)
        while True:
            try:
                run_once()
            except Exception as exc:
                app.logger.exception("Scheduler error: %s", exc)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="regulatory-scheduler").start()


init_db()
start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
