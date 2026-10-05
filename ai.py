import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "none").lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_MODEL = os.getenv("SARVAM_MODEL", "sarvam-105b")
SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"


class AIError(RuntimeError):
    """A user-facing AI integration error."""


def _json_response(response, provider):
    try:
        return response.json()
    except ValueError as exc:
        body = (response.text or "").strip()
        raise AIError(
            f"{provider} returned a non-JSON response"
            + (f": {body[:300]}" if body else ".")
        ) from exc


def _response_error(response, provider):
    payload = _json_response(response, provider)
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return f"{provider}: {message}"
        if error:
            return f"{provider}: {error}"
    return f"{provider} request failed with HTTP {response.status_code}"


def _parse_json(raw, provider):
    if isinstance(raw, dict):
        return raw
    if raw is None:
        raise AIError(
            f"{provider} returned an empty response. "
            "This usually means the model used its output budget on reasoning."
        )
    if not isinstance(raw, str):
        raise AIError(f"{provider} returned an unexpected response type.")

    text = raw.strip()
    if not text:
        raise AIError(f"{provider} returned empty content.")

    text = re.sub(r"^\s*\x60{3}(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\x60{3}\s*$", "", text).strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                raise AIError(
                    f"{provider} returned invalid JSON: {text[:300]}"
                ) from exc
        else:
            raise AIError(
                f"{provider} returned invalid JSON: {text[:300]}"
            ) from exc

    if not isinstance(value, dict):
        raise AIError(f"{provider} returned JSON, but not a JSON object.")
    return value


def _extract_gemini_text(payload):
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not candidates:
        prompt_feedback = payload.get("promptFeedback") if isinstance(payload, dict) else None
        raise AIError(f"Gemini returned no candidates. {prompt_feedback or ''}".strip())

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text") for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        finish = candidates[0].get("finishReason")
        raise AIError(f"Gemini returned no text content (finish reason: {finish or 'unknown'}).")
    return "\n".join(texts).strip()


def _extract_sarvam_text(payload):
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices:
        raise AIError("Sarvam returned no choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
        if texts:
            return "\n".join(texts).strip()

    finish = choices[0].get("finish_reason")
    raise AIError(
        "Sarvam returned no visible answer"
        + (f" (finish reason: {finish})" if finish else ".")
    )


def analysis_prompt(title, content):
    return f"""You are an Indian regulatory intelligence analyst.
Analyze this RBI publication.

Title: {title}
Content:
{content[:14000]}

Return ONLY one JSON object with exactly these keys:
summary: concise 3-5 sentence summary
category: one of Banking, Monetary Policy, Payments, NBFC, Forex, Markets, Consumer, Compliance, Other
importance: one of Low, Medium, High, Critical
affected_sectors: array of short sector names
market_impact: concise explanation of likely market/business impact; say "No clear market impact" if none
action_required: concise practical implication for a business/investor
"""


def _normalize_analysis(result):
    if not isinstance(result, dict):
        raise AIError("AI returned an invalid analysis object.")

    allowed_categories = {
        "Banking", "Monetary Policy", "Payments", "NBFC",
        "Forex", "Markets", "Consumer", "Compliance", "Other",
    }
    allowed_importance = {"Low", "Medium", "High", "Critical"}

    sectors = result.get("affected_sectors", [])
    if isinstance(sectors, str):
        sectors = [x.strip() for x in sectors.split(",") if x.strip()]
    elif not isinstance(sectors, list):
        sectors = []

    category = result.get("category")
    importance = result.get("importance")

    return {
        "summary": str(result.get("summary") or "").strip(),
        "category": category if category in allowed_categories else "Other",
        "importance": importance if importance in allowed_importance else "Medium",
        "affected_sectors": [str(x).strip() for x in sectors if str(x).strip()],
        "market_impact": str(result.get("market_impact") or "No clear market impact").strip(),
        "action_required": str(result.get("action_required") or "No specific action identified.").strip(),
    }


def analyze_with_gemini(prompt):
    if not GEMINI_API_KEY:
        return None

    response = requests.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        },
        timeout=90,
    )
    if not response.ok:
        raise AIError(_response_error(response, "Gemini"))

    return _parse_json(_extract_gemini_text(_json_response(response, "Gemini")), "Gemini")


def analyze_with_sarvam(prompt):
    if not SARVAM_API_KEY:
        return None

    response = requests.post(
        SARVAM_URL,
        headers={
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": SARVAM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only one valid JSON object matching the requested keys.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "reasoning_effort": "low",
            "max_tokens": 2200,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    if not response.ok:
        raise AIError(_response_error(response, "Sarvam"))

    return _parse_json(_extract_sarvam_text(_json_response(response, "Sarvam")), "Sarvam")


def ask_with_gemini(prompt):
    if not GEMINI_API_KEY:
        raise AIError("Gemini API key is not configured.")

    response = requests.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        },
        timeout=90,
    )
    if not response.ok:
        raise AIError(_response_error(response, "Gemini"))
    return _extract_gemini_text(_json_response(response, "Gemini"))


def ask_with_sarvam(prompt):
    if not SARVAM_API_KEY:
        raise AIError("Sarvam API key is not configured.")

    response = requests.post(
        SARVAM_URL,
        headers={
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": SARVAM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "reasoning_effort": "low",
            "max_tokens": 1600,
        },
        timeout=120,
    )
    if not response.ok:
        raise AIError(_response_error(response, "Sarvam"))
    return _extract_sarvam_text(_json_response(response, "Sarvam"))


def analyze_document(title, content, provider=None):
    provider = (provider or AI_PROVIDER).lower()
    if not content:
        raise AIError("This document has no extracted content to analyze.")

    prompt = analysis_prompt(title, content)

    if provider == "gemini":
        result = analyze_with_gemini(prompt)
    elif provider == "sarvam":
        result = analyze_with_sarvam(prompt)
    else:
        return None

    if result is None:
        return None
    return _normalize_analysis(result)
