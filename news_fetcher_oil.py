"""
news_fetcher_oil.py  —  News sources for Brent Crude session-based bot
──────────────────────────────────────────────────────────────────────
Fetches oil-specific AND geopolitical headlines from the past N hours.
Geopolitical feeds are keyword-filtered to keep only oil-relevant stories.
No API keys required.
"""

import re
import requests
import feedparser
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)


# ─── Oil-specific RSS feeds ─────────────────────────────────

OIL_RSS_FEEDS = [
    ("OilPrice.com",     "https://oilprice.com/rss/main"),
    ("Rigzone",          "https://www.rigzone.com/news/rss/rigzone_latest.aspx"),
    ("Yahoo Brent",      "https://finance.yahoo.com/rss/headline?s=BZ=F"),
    ("Yahoo WTI",        "https://finance.yahoo.com/rss/headline?s=CL=F"),
    ("Yahoo Nat Gas",    "https://finance.yahoo.com/rss/headline?s=NG=F"),
]


# ─── Geopolitical RSS feeds (filtered for oil relevance) ────

GEOPOLITICAL_RSS_FEEDS = [
    ("Al Jazeera",   "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC World",    "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters World","https://www.reutersagency.com/feed/"),
]

# Keywords that signal a geopolitical headline may affect oil prices.
# Matched case-insensitively against the headline text.
GEO_OIL_KEYWORDS = re.compile(
    r"oil|crude|petroleum|energy|fuel|gasoline|diesel|refiner|lng|"
    r"opec|saudi|iran|iraq|russia|venezuela|libya|nigeria|angola|"
    r"middle east|gulf|pipeline|sanction|embargo|tariff|"
    r"barrel|production|supply|demand|inventory|reserve|"
    r"war|conflict|tension|military|attack|strike|drone|missile|"
    r"hurricane|storm|flood|earthquake|"
    r"shipping|strait|hormuz|suez|red sea|houthi|"
    r"natural gas|shale|fracking|drilling|offshore",
    re.IGNORECASE,
)


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


def _parse_geo_feed(name: str, url: str, limit: int, max_age_hours: float) -> list:
    """
    Parse a geopolitical RSS feed, keeping only headlines that match
    oil-relevant keywords.
    """
    try:
        feed   = feedparser.parse(url)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        results = []

        for entry in feed.entries[:limit * 5]:  # scan more since we filter
            title = entry.get("title", "").strip()
            if not title:
                continue

            # Keyword filter — skip headlines irrelevant to oil
            if not GEO_OIL_KEYWORDS.search(title):
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
                pass

            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()

            results.append(f"[{name}/Geo] {title}")
            if len(results) >= limit:
                break

        return results
    except Exception as e:
        log.warning(f"Geopolitical feed '{name}' failed: {e}")
        return []


def fetch_oil_rss(limit_per_feed: int = 10, hours_back: float = 8.0) -> dict:
    """
    Fetch headlines from all oil RSS feeds within the session window.
    Runs all feeds in parallel.
    """
    all_headlines = []
    sources_hit   = []

    with ThreadPoolExecutor(max_workers=len(OIL_RSS_FEEDS)) as executor:
        futures = {
            executor.submit(_parse_feed, name, url, limit_per_feed, hours_back): name
            for name, url in OIL_RSS_FEEDS
        }
        for future in as_completed(futures):
            name = futures[future]
            headlines = future.result()
            if headlines:
                all_headlines.extend(headlines)
                sources_hit.append(name)

    log.info(f"  Oil RSS: {len(all_headlines)} headlines "
             f"from {len(sources_hit)}/{len(OIL_RSS_FEEDS)} feeds "
             f"(last {hours_back:.1f}h): {', '.join(sources_hit)}")

    return {"source": "oil_rss", "headlines": all_headlines, "sources_hit": sources_hit}


def fetch_geopolitical_rss(limit_per_feed: int = 15, hours_back: float = 8.0) -> dict:
    """
    Fetch oil-relevant geopolitical headlines.
    Headlines are keyword-filtered to keep only those potentially affecting oil.
    """
    all_headlines = []
    sources_hit   = []

    with ThreadPoolExecutor(max_workers=len(GEOPOLITICAL_RSS_FEEDS)) as executor:
        futures = {
            executor.submit(_parse_geo_feed, name, url, limit_per_feed, hours_back): name
            for name, url in GEOPOLITICAL_RSS_FEEDS
        }
        for future in as_completed(futures):
            name = futures[future]
            headlines = future.result()
            if headlines:
                all_headlines.extend(headlines)
                sources_hit.append(name)

    log.info(f"  Geopolitical RSS: {len(all_headlines)} oil-relevant headlines "
             f"from {len(sources_hit)}/{len(GEOPOLITICAL_RSS_FEEDS)} feeds "
             f"(last {hours_back:.1f}h): {', '.join(sources_hit)}")

    return {"source": "geopolitical_rss", "headlines": all_headlines, "sources_hit": sources_hit}


def fetch_google_news_oil(limit: int = 20) -> dict:
    """Fetch Google News RSS for oil-specific queries — no API key."""
    query = "crude oil brent OPEC production price"
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

        log.info(f"  Google News (oil): {len(headlines)} headlines")
        return {"source": "google_news_oil", "headlines": headlines}
    except Exception as e:
        log.warning(f"Google News (oil) failed: {e}")
        return {"source": "google_news_oil", "headlines": []}


def fetch_google_news_geopolitical(limit: int = 20) -> dict:
    """Fetch Google News RSS for geopolitical queries affecting oil — no API key."""
    query = "Middle East Russia sanctions oil energy supply OPEC"
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

        log.info(f"  Google News (geopolitical): {len(headlines)} headlines")
        return {"source": "google_news_geo", "headlines": headlines}
    except Exception as e:
        log.warning(f"Google News (geopolitical) failed: {e}")
        return {"source": "google_news_geo", "headlines": []}


def fetch_session_news(cfg: dict, hours_back: float = 8.0) -> dict:
    """
    Fetch all news sources for the current session window.
    Called once at each session open.

    Returns oil RSS + geopolitical RSS + Google News (oil + geo).
    """
    sent = cfg.get("sentiment", {})
    limit_per_feed = sent.get("rss_limit_per_feed", 10)
    gn_limit       = sent.get("google_news_limit", 20)
    geo_limit      = sent.get("geopolitical_rss_limit", 15)

    log.info(f"  Fetching oil session news (last {hours_back:.1f}h)...")

    with ThreadPoolExecutor(max_workers=4) as executor:
        f_oil_rss = executor.submit(fetch_oil_rss, limit_per_feed, hours_back)
        f_geo_rss = executor.submit(fetch_geopolitical_rss, geo_limit, hours_back)
        f_gn_oil  = executor.submit(fetch_google_news_oil, gn_limit)
        f_gn_geo  = executor.submit(fetch_google_news_geopolitical, gn_limit)

    oil_rss = f_oil_rss.result()
    geo_rss = f_geo_rss.result()
    gn_oil  = f_gn_oil.result()
    gn_geo  = f_gn_geo.result()

    total = (len(oil_rss.get("headlines", []))
             + len(geo_rss.get("headlines", []))
             + len(gn_oil.get("headlines", []))
             + len(gn_geo.get("headlines", [])))
    log.info(f"  Total oil+geo headlines fetched: {total}")

    return {
        "oil_rss":          oil_rss,
        "geopolitical_rss": geo_rss,
        "google_news_oil":  gn_oil,
        "google_news_geo":  gn_geo,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "hours_back":       hours_back,
    }
