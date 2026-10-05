import json
import os
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def analyze_document(title, content):
    if not GEMINI_API_KEY or not content:
        return None

    prompt = f"""You are an Indian regulatory intelligence analyst.
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

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)
