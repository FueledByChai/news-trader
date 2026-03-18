"""
news_fetcher.py  —  News sources for session-based bot
───────────────────────────────────────────────────────
Fetches headlines from the past N hours (one full session window).
No API keys required. No Fear & Greed. No deduplication needed —
we want the full session picture every time.
"""

import requests
import feedparser
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)


CRYPTO_RSS_FEEDS = [
    ("Coindesk",         "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph",    "https://cointelegraph.com/rss"),
    ("Decrypt",          "https://decrypt.co/feed"),
    ("Bitcoinist",       "https://bitcoinist.com/feed/"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
    ("Yahoo Finance",    "https://finance.yahoo.com/rss/headline?s=BTC-USD"),
    ("NewsBTC",          "https://www.newsbtc.com/feed/"),
    ("The Block",        "https://www.theblock.co/rss.xml"),
]


def _parse_feed(name: str, url: str, limit: int, max_age_hours: float) -> list:
    """Parse a single RSS feed and return headlines within the age window."""
    try:
        feed   = feedparser.parse(url)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        results = []

        for entry in feed.entries[:limit * 3]:
            title = entry.get("title", "").strip()
            if not title:
                continue

            try:
                pub = entry.get("published") or entry.get("updated", "")
                if pub:
                    pub_dt = parsedate_to_datetime(pub)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
            except Exception:
                pass   # include if we can't parse date

            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()

            results.append(f"[{name}] {title}")
            if len(results) >= limit:
                break

        return results
    except Exception as e:
        log.warning(f"RSS feed '{name}' failed: {e}")
        return []


def fetch_crypto_rss(limit_per_feed: int = 10, hours_back: float = 8.0) -> dict:
    """
    Fetch headlines from all crypto RSS feeds within the session window.
    Runs all feeds in parallel.
    """
    all_headlines = []
    sources_hit   = []

    with ThreadPoolExecutor(max_workers=len(CRYPTO_RSS_FEEDS)) as executor:
        futures = {
            executor.submit(_parse_feed, name, url, limit_per_feed, hours_back): name
            for name, url in CRYPTO_RSS_FEEDS
        }
        for future in as_completed(futures):
            name = futures[future]
            headlines = future.result()
            if headlines:
                all_headlines.extend(headlines)
                sources_hit.append(name)

    log.info(f"  Crypto RSS: {len(all_headlines)} headlines "
             f"from {len(sources_hit)}/{len(CRYPTO_RSS_FEEDS)} feeds "
             f"(last {hours_back:.1f}h): {', '.join(sources_hit)}")

    return {"source": "crypto_rss", "headlines": all_headlines, "sources_hit": sources_hit}


def fetch_google_news(query: str = "Bitcoin BTC price crypto", limit: int = 20) -> dict:
    """Fetch Google News RSS — no API key."""
    try:
        encoded = requests.utils.quote(query)
        url  = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)

        headlines = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            if title:
                headlines.append(title)

        log.info(f"  Google News: {len(headlines)} headlines")
        return {"source": "google_news", "headlines": headlines}
    except Exception as e:
        log.warning(f"Google News failed: {e}")
        return {"source": "google_news", "headlines": []}


def fetch_session_news(cfg: dict, hours_back: float = 8.0) -> dict:
    """
    Fetch all news sources for the current session window.
    Called once at each session open.
    """
    sent = cfg.get("sentiment", {})
    limit_per_feed = sent.get("rss_limit_per_feed", 10)
    gn_limit       = sent.get("google_news_limit", 20)

    log.info(f"  Fetching session news (last {hours_back:.1f}h)...")

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_rss = executor.submit(fetch_crypto_rss, limit_per_feed, hours_back)
        f_gn  = executor.submit(fetch_google_news,
                                "Bitcoin BTC crypto price market",
                                gn_limit)

    rss = f_rss.result()
    gn  = f_gn.result()

    total = len(rss.get("headlines", [])) + len(gn.get("headlines", []))
    log.info(f"  Total headlines fetched: {total}")

    return {
        "crypto_rss":  rss,
        "google_news": gn,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "hours_back":  hours_back,
    }