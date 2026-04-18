"""
test_pipeline_oil.py
─────────────────────
Validates the Brent Crude pipeline without placing any trades.
Run this first to verify your API keys and oil news sources.

  python test_pipeline_oil.py
"""

import os
import yaml
import sys
import json
import re
from pathlib import Path
import requests
import feedparser
from dotenv import load_dotenv

def header(text):
    print(f"\n{'=' * 55}")
    print(f"  {text}")
    print(f"{'=' * 55}")

def ok(msg):   print(f"  +  {msg}")
def warn(msg): print(f"  ?  {msg}")
def fail(msg): print(f"  X  {msg}")


def test_oil_rss():
    header("Oil RSS Feeds (no API keys)")
    feeds = [
        ("OilPrice.com",  "https://oilprice.com/rss/main"),
        ("Rigzone",       "https://www.rigzone.com/news/rss/rigzone_latest.aspx"),
        ("Yahoo Brent",   "https://finance.yahoo.com/rss/headline?s=BZ=F"),
        ("Yahoo WTI",     "https://finance.yahoo.com/rss/headline?s=CL=F"),
        ("Yahoo Nat Gas", "https://finance.yahoo.com/rss/headline?s=NG=F"),
    ]
    working = 0
    for name, url in feeds:
        try:
            feed = feedparser.parse(url)
            count = len(feed.entries)
            if count > 0:
                title = feed.entries[0].title.rsplit(" - ", 1)[0][:70]
                ok(f"{name}: {count} entries -- \"{title}\"")
                working += 1
            else:
                warn(f"{name}: 0 entries returned")
        except Exception as e:
            fail(f"{name}: {e}")
    return working > 0


def test_geopolitical_rss():
    header("Geopolitical RSS Feeds (keyword-filtered)")
    feeds = [
        ("Al Jazeera",    "https://www.aljazeera.com/xml/rss/all.xml"),
        ("BBC World",     "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters World", "https://www.reutersagency.com/feed/"),
    ]
    geo_keywords = re.compile(
        r"oil|crude|energy|opec|saudi|iran|iraq|russia|"
        r"middle east|pipeline|sanction|barrel|production|"
        r"war|conflict|tension|military|hurricane|shipping|strait",
        re.IGNORECASE,
    )
    working = 0
    for name, url in feeds:
        try:
            feed = feedparser.parse(url)
            count = len(feed.entries)
            if count > 0:
                # Show total and filtered count
                filtered = [e for e in feed.entries if geo_keywords.search(e.get("title", ""))]
                ok(f"{name}: {count} total, {len(filtered)} oil-relevant")
                if filtered:
                    title = filtered[0].title.rsplit(" - ", 1)[0][:70]
                    print(f"       -> \"{title}\"")
                working += 1
            else:
                warn(f"{name}: 0 entries returned")
        except Exception as e:
            fail(f"{name}: {e}")
    return working > 0


def test_google_news_oil():
    header("Google News — Oil queries (no API key)")
    queries = [
        ("Oil direct", "crude oil brent OPEC production price"),
        ("Geopolitical", "Middle East Russia sanctions oil energy supply OPEC"),
    ]
    working = 0
    for label, query in queries:
        try:
            encoded = requests.utils.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            count = len(feed.entries)
            if count > 0:
                ok(f"{label}: {count} headlines")
                for e in feed.entries[:3]:
                    title = e.title.rsplit(" - ", 1)[0][:70]
                    print(f"       -> \"{title}\"")
                working += 1
            else:
                warn(f"{label}: 0 entries")
        except Exception as e:
            fail(f"{label}: {e}")
    return working > 0


def test_anthropic(api_key: str, model: str):
    header("Anthropic Claude API")
    if not api_key or api_key.startswith("YOUR_") or api_key == "KEY_HERE":
        fail("API key not set -- required! Get one at console.anthropic.com")
        return False
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": 'Respond with exactly: {"score": 0.5, "test": "ok"}'}]
        )
        text = msg.content[0].text.strip()
        parsed = json.loads(text)
        ok(f"Claude responded: {parsed}")
        return True
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_paradex_oil():
    header("Paradex Public API — BZ-USD-PERP (no auth required)")
    market = "BZ-USD-PERP"
    try:
        # Try testnet first
        resp = requests.get(
            f"https://api.testnet.paradex.trade/v1/markets/summary",
            params={"market": market},
            timeout=10
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for item in results:
                if item.get("symbol") == market:
                    mark = item.get("mark_price", "?")
                    ok(f"{market} mark price: ${mark}")
                    return True
            # Market not found in results
            warn(f"{market} not found in testnet results -- check market symbol on Paradex")
            print("       Available markets:")
            for item in results[:10]:
                print(f"         {item.get('symbol', '?')}")
            return True  # API reachable, just wrong market name
        else:
            warn(f"Paradex testnet returned status {resp.status_code}")
            return True
    except Exception as e:
        fail(f"Error: {e}")
        return False


def main():
    print("\n  Brent Crude Sentiment Bot -- Pipeline Test")
    print("=" * 55)

    # Load config
    config_path = Path("config_oil.yaml")
    if not config_path.exists():
        fail("config_oil.yaml not found -- run from the bot directory")
        sys.exit(1)

    load_dotenv()

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    keys = cfg["api_keys"]
    sent = cfg["sentiment"]

    # Override with env var if available
    env_key = os.getenv("ANTHROPIC_API_KEY")
    if env_key:
        keys["anthropic"] = env_key

    results = {}
    results["oil_rss"]        = test_oil_rss()
    results["geopolitical"]   = test_geopolitical_rss()
    results["google_news"]    = test_google_news_oil()
    results["anthropic"]      = test_anthropic(keys.get("anthropic", ""), sent.get("claude_model", "claude-sonnet-4-20250514"))
    results["paradex"]        = test_paradex_oil()

    # Summary
    header("SUMMARY")
    all_passed = True
    for name, result in results.items():
        if result is True:
            ok(name)
        elif result is None:
            warn(f"{name} (skipped)")
        else:
            fail(name)
            if name == "anthropic":
                all_passed = False

    if all_passed:
        print("\n  Ready to run! Start with:")
        print("     python bot_oil.py --dry-run     # paper trading test")
        print("     python bot_oil.py --once        # one cycle and exit")
        print("     python bot_oil.py               # full loop")
    else:
        print("\n  Fix the issues above before running the bot.")
        print("     At minimum you need: Anthropic API key")
    print()

if __name__ == "__main__":
    main()
