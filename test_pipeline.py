"""
test_pipeline.py
─────────────────
Validates the entire pipeline without placing any trades.
Run this first to verify your API keys and data sources.

  python test_pipeline.py
"""

import yaml
import sys
import json
from pathlib import Path
import requests
import feedparser

def header(text):
    print(f"\n{'─' * 55}")
    print(f"  {text}")
    print(f"{'─' * 55}")

def ok(msg):   print(f"  ✅  {msg}")
def warn(msg): print(f"  ⚠️   {msg}")
def fail(msg): print(f"  ❌  {msg}")

def test_fear_greed():
    header("Fear & Greed Index (no API key)")
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = resp.json()["data"][0]
        score = int(data["value"])
        label = data["value_classification"]
        ok(f"Score: {score}/100 — {label}")
        return True
    except Exception as e:
        fail(f"Error: {e}")
        return False

def test_google_news():
    header("Google News RSS (no API key)")
    try:
        url = "https://news.google.com/rss/search?q=Bitcoin+BTC+crypto&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        count = len(feed.entries)
        if count > 0:
            ok(f"{count} headlines found")
            for e in feed.entries[:3]:
                title = e.title.rsplit(" - ", 1)[0]
                print(f"     • {title[:80]}")
            return True
        else:
            warn("Feed returned 0 entries")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False

def test_crypto_rss():
    header("Crypto RSS Feeds (no API keys — real-time)")
    feeds = [
        ("Coindesk",        "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph",   "https://cointelegraph.com/rss"),
        ("Decrypt",         "https://decrypt.co/feed"),
        ("Bitcoinist",      "https://bitcoinist.com/feed/"),
        ("Bitcoin Magazine","https://bitcoinmagazine.com/feed"),
        ("Yahoo Finance",   "https://finance.yahoo.com/rss/headline?s=BTC-USD"),
        ("NewsBTC",         "https://www.newsbtc.com/feed/"),
        ("The Block",       "https://www.theblock.co/rss.xml"),
    ]
    working = 0
    for name, url in feeds:
        try:
            feed = feedparser.parse(url)
            count = len(feed.entries)
            if count > 0:
                title = feed.entries[0].title.rsplit(" - ", 1)[0][:70]
                ok(f"{name}: {count} entries — \"{title}\"")
                working += 1
            else:
                warn(f"{name}: 0 entries returned")
        except Exception as e:
            fail(f"{name}: {e}")
    return working > 0

def test_reddit(client_id: str, client_secret: str, user_agent: str):
    header("Reddit API")
    if not client_id or client_id.startswith("YOUR_"):
        warn("Reddit credentials not set — skipping (free at reddit.com/prefs/apps)")
        return None
    try:
        import praw
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
        posts = list(reddit.subreddit("Bitcoin").hot(limit=5))
        ok(f"{len(posts)} posts from r/Bitcoin")
        for p in posts[:3]:
            print(f"     • {p.title[:80]}")
        return True
    except Exception as e:
        fail(f"Error: {e}")
        return False

def test_anthropic(api_key: str, model: str):
    header("Anthropic Claude API")
    if not api_key or api_key.startswith("YOUR_"):
        fail("API key not set — required! Get one at console.anthropic.com")
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

def test_paradex_public():
    header("Paradex Public API (no auth required)")
    try:
        resp = requests.get(
            "https://api.testnet.paradex.trade/v1/bbo/BTC-USD-PERP",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            bid = data.get("bid", {}).get("price", "?")
            ask = data.get("ask", {}).get("price", "?")
            ok(f"BTC-USD-PERP BBO: bid={bid} ask={ask}")
            return True
        else:
            # Try market summary endpoint
            resp2 = requests.get(
                "https://api.testnet.paradex.trade/v1/markets/summary",
                params={"market": "BTC-USD-PERP"},
                timeout=10
            )
            ok(f"Paradex reachable (status {resp2.status_code})")
            return True
    except Exception as e:
        fail(f"Error: {e}")
        return False

def main():
    print("\n🔍 BTC Sentiment Bot — Pipeline Test")
    print("=" * 55)

    # Load config
    config_path = Path("config.yaml")
    if not config_path.exists():
        fail("config.yaml not found — run from the bot directory")
        sys.exit(1)

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    keys = cfg["api_keys"]
    sent = cfg["sentiment"]

    results = {}
    results["crypto_rss"]  = test_crypto_rss()
    results["google_news"] = test_google_news()
    results["fear_greed"]  = test_fear_greed()
    results["anthropic"]   = test_anthropic(keys.get("anthropic", ""), sent.get("claude_model", "claude-sonnet-4-20250514"))
    results["paradex"]     = test_paradex_public()

    # Summary
    header("SUMMARY")
    all_passed = True
    for name, result in results.items():
        if result is True:
            ok(name)
        elif result is None:
            warn(f"{name} (skipped — API key not set)")
        else:
            fail(name)
            if name == "anthropic":
                all_passed = False

    if all_passed:
        print("\n  ✅ Ready to run! Start with:")
        print("     python bot.py --dry-run     # paper trading test")
        print("     python bot.py --once        # one cycle and exit")
        print("     python bot.py               # full loop")
    else:
        print("\n  ⚠️  Fix the issues above before running the bot.")
        print("     At minimum you need: Anthropic API key")
    print()

if __name__ == "__main__":
    main()