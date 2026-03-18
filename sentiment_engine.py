"""
sentiment_engine.py  —  Session news scorer
────────────────────────────────────────────
Sends all headlines from the current session window to Claude and asks
for the general news bias. No extremes required — even a slight lean counts.
"""

import json
import logging
import anthropic
from datetime import datetime, timezone

log = logging.getLogger(__name__)


SESSION_PROMPT = """You are analyzing Bitcoin/crypto news headlines to determine the general sentiment bias for a trading session.

Your job is simple: read the headlines and tell me whether the overall tone is bullish, bearish, or neutral.

Rules:
- You do NOT need an extreme — even a slight lean counts
- Look at the weight of evidence across all headlines
- Ignore individual outliers; focus on the overall tone
- Price going up / institutional buying / positive regulatory news = BULLISH
- Price falling / fear / negative news / uncertainty = BEARISH
- Mixed with no clear lean = NEUTRAL

Output JSON only, no markdown:
{
  "news_bias": "<BULLISH | BEARISH | NEUTRAL>",
  "contrarian_direction": "<SHORT | LONG | LONG>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2 sentences max explaining the dominant theme>",
  "headline_count": <number of headlines reviewed>
}

Note on contrarian_direction:
  BULLISH news  → SHORT  (fade the bulls)
  BEARISH news  → LONG   (fade the bears)
  NEUTRAL       → LONG   (default long bias when no clear signal)"""


def score_session(raw_data: dict, cfg: dict, session_name: str = "") -> dict:
    """
    Score all headlines from the session window.
    Returns dict with news_bias, contrarian_direction, confidence, reasoning.
    """
    client = anthropic.Anthropic(api_key=cfg["api_keys"]["anthropic"])
    model  = cfg["sentiment"].get("claude_model", "claude-sonnet-4-20250514")

    # Build content
    parts = []
    if session_name:
        parts.append(f"## Session: {session_name}")
        parts.append("")

    rss = raw_data.get("crypto_rss", {})
    gn  = raw_data.get("google_news", {})

    all_headlines = rss.get("headlines", []) + gn.get("headlines", [])

    if not all_headlines:
        log.warning("No headlines available — defaulting to NEUTRAL/LONG")
        return _default("No headlines fetched")

    parts.append(f"## Headlines ({len(all_headlines)} total)")
    for h in all_headlines:
        parts.append(f"  • {h}")

    content = "\n".join(parts)
    log.info(f"  Sending {len(all_headlines)} headlines to Claude ({len(content)} chars)...")

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=500,
            system=SESSION_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.7))))
        result["timestamp"]  = datetime.now(timezone.utc).isoformat()

        log.info(f"  Claude: bias={result['news_bias']}  "
                 f"→ direction={result['contrarian_direction']}  "
                 f"confidence={result['confidence']:.2f}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e}")
        return _default(f"Parse error: {e}")
    except anthropic.APIError as e:
        log.error(f"API error: {e}")
        return _default(f"API error: {e}")
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return _default(str(e))


def _default(reason: str) -> dict:
    return {
        "news_bias":            "NEUTRAL",
        "contrarian_direction": "LONG",
        "confidence":           0.0,
        "reasoning":            reason,
        "headline_count":       0,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
        "error":                reason,
    }