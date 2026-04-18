"""
sentiment_engine_oil.py  —  Oil session news scorer
────────────────────────────────────────────────────
Sends oil + geopolitical headlines to Claude and asks for the
overall oil-market bias. Contrarian logic inverts the bias for trading.
"""

import json
import logging
import anthropic
from datetime import datetime, timezone

log = logging.getLogger(__name__)


SESSION_PROMPT = """You are analyzing news headlines to determine their net impact on crude oil prices for a trading session.

You will receive two categories of headlines:
1. **Oil-specific news** — directly about crude oil, OPEC, refineries, inventories, production
2. **Geopolitical news** — conflicts, sanctions, diplomacy that could affect oil supply or demand

Your job: read ALL headlines and determine whether the overall tone is BULLISH or BEARISH for oil prices.

## What moves oil prices:

BULLISH for oil (prices likely to rise):
- Middle East tensions, conflicts, military strikes (supply disruption risk)
- OPEC/OPEC+ production cuts or compliance
- Sanctions on oil producers (Russia, Iran, Venezuela)
- Pipeline/refinery outages or attacks
- Inventory drawdowns (lower than expected)
- Hurricane/storm threats to Gulf of Mexico production
- Strong economic growth signals (demand)
- Shipping disruptions (Strait of Hormuz, Red Sea, Suez)

BEARISH for oil (prices likely to fall):
- OPEC+ production increases or quota cheating
- Economic slowdown, recession fears, weak demand data
- US shale production increases
- Diplomatic breakthroughs reducing geopolitical risk
- Inventory builds (higher than expected)
- Strong US dollar
- EV adoption / demand destruction signals
- Peace deals, ceasefire agreements in oil-producing regions

## Rules:
- You do NOT need an extreme — even a slight lean counts
- Look at the weight of evidence across ALL headlines (oil + geopolitical)
- Geopolitical headlines should be weighted by their potential oil supply/demand impact
- Ignore headlines that have no plausible oil price impact
- Focus on the overall tone, not individual outliers

Output JSON only, no markdown:
{
  "news_bias": "<BULLISH | BEARISH | NEUTRAL>",
  "contrarian_direction": "<SHORT | LONG | LONG>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2 sentences max explaining the dominant theme and its oil price impact>",
  "headline_count": <number of headlines reviewed>
}

Note on contrarian_direction:
  BULLISH oil news  → SHORT  (fade the bulls — price rise already priced in)
  BEARISH oil news  → LONG   (fade the bears — price drop overdone)
  NEUTRAL           → LONG   (default long bias when no clear signal)"""


def score_session(raw_data: dict, cfg: dict, session_name: str = "") -> dict:
    """
    Score all oil + geopolitical headlines from the session window.
    Returns dict with news_bias, contrarian_direction, confidence, reasoning.
    """
    client = anthropic.Anthropic(api_key=cfg["api_keys"]["anthropic"])
    model  = cfg["sentiment"].get("claude_model", "claude-sonnet-4-20250514")

    # Build content from all sources
    parts = []
    if session_name:
        parts.append(f"## Session: {session_name}")
        parts.append("")

    oil_rss = raw_data.get("oil_rss", {})
    geo_rss = raw_data.get("geopolitical_rss", {})
    gn_oil  = raw_data.get("google_news_oil", {})
    gn_geo  = raw_data.get("google_news_geo", {})

    oil_headlines = oil_rss.get("headlines", []) + gn_oil.get("headlines", [])
    geo_headlines = geo_rss.get("headlines", []) + gn_geo.get("headlines", [])
    all_headlines = oil_headlines + geo_headlines

    if not all_headlines:
        log.warning("No headlines available — defaulting to NEUTRAL/LONG")
        return _default("No headlines fetched")

    if oil_headlines:
        parts.append(f"## Oil-Specific Headlines ({len(oil_headlines)})")
        for h in oil_headlines:
            parts.append(f"  - {h}")
        parts.append("")

    if geo_headlines:
        parts.append(f"## Geopolitical Headlines ({len(geo_headlines)})")
        for h in geo_headlines:
            parts.append(f"  - {h}")

    content = "\n".join(parts)
    log.info(f"  Sending {len(all_headlines)} headlines to Claude "
             f"({len(oil_headlines)} oil + {len(geo_headlines)} geo, "
             f"{len(content)} chars)...")

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
                 f"-> direction={result['contrarian_direction']}  "
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
