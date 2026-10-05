import json
import os
import requests

AI_PROVIDER = os.getenv("AI_PROVIDER", "none").lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_MODEL = os.getenv("SARVAM_MODEL", "sarvam-105b")
SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"


def analysis_prompt(title, content):
    return f"""You are an Indian regulatory intelligence analyst.
Analyze this RBI publication.

Title: {title}
Content:
{content[:14000]}

Return ONLY valid JSON with these keys:
summary: concise 3-5 sentence summary
category: one of Banking, Monetary Policy, Payments, NBFC, Forex, Markets, Consumer, Compliance, Other
importance: one of Low, Medium, High, Critical
affected_sectors: array of short sector names
market_impact: concise explanation of likely market/business impact; say "No clear market impact" if none
action_required: concise practical implication for a business/investor
"""


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
                "responseMimeType": "application/json"
            }
        },
        timeout=60,
    )
    response.raise_for_status()
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


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
                    "content": "Return only valid JSON matching the requested keys."
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    return json.loads(text)


def analyze_document(title, content, provider=None):
    provider = (provider or AI_PROVIDER).lower()
    if not content:
        return None

    prompt = analysis_prompt(title, content)

    if provider == "gemini":
        return analyze_with_gemini(prompt)
    if provider == "sarvam":
        return analyze_with_sarvam(prompt)
    return None
