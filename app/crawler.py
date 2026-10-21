import re
import html
import logging
import requests
import feedparser
from config import LOG_PATH, NEWS_PER_RUN, FETCH_TIMEOUT
from db import is_seen, get_conn, get_setting

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

UA = {"User-Agent": "Mozilla/5.0 (compatible; KarunaRSS/0.3)"}
TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text):
    """Feed summaries often carry markup — strip it so the LLM gets clean text."""
    return html.unescape(TAG_RE.sub(" ", text or "")).strip()

def get_feeds():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT url, category FROM feeds")
        return [{"url": r[0], "category": r[1]} for r in c.fetchall()]
    except Exception:
        from config import RSS_FEEDS
        return RSS_FEEDS
    finally:
        conn.close()

def fetch_feed(url):
    """Fetch with a hard timeout, then parse. feedparser.parse(url) can hang forever."""
    resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=UA)
    resp.raise_for_status()
    return feedparser.parse(resp.content)

def build_pool(cat_feeds, cat, seen_titles):
    pool = []
    for feed in cat_feeds:
        source_url = feed["url"]
        try:
            parsed = fetch_feed(source_url)
            for entry in parsed.entries:
                url = entry.get("link", "")
                title = entry.get("title", "")
                summary = strip_html(entry.get("summary", entry.get("description", "")))
                if not url or not title or is_seen(url) or title in seen_titles:
                    continue
                pool.append({
                    "url": url,
                    "title": title,
                    "summary": summary,
                    "category": cat,
                    "source": source_url,
                })
        except Exception as e:
            logging.warning(f"Failed to fetch {source_url}: {e}")
    return pool

def round_robin(pool, feeds, max_per_source, already_selected, budget, selected, seen_titles):
    """Pick up to `budget` articles round-robin across sources, respecting per-source cap.
    `already_selected` counts picks already made for this category in an earlier pass."""
    source_counts = {f["url"]: 0 for f in feeds}
    for s in already_selected:
        source_counts[s["source"]] = source_counts.get(s["source"], 0) + 1

    picked = 0
    while picked < budget:
        added_this_round = 0
        for feed in feeds:
            if picked >= budget:
                break
            src = feed["url"]
            if source_counts.get(src, 0) >= max_per_source:
                continue
            for article in pool:
                if article["source"] != src or article["title"] in seen_titles:
                    continue
                selected.append(article)
                seen_titles.add(article["title"])
                source_counts[src] = source_counts.get(src, 0) + 1
                picked += 1
                added_this_round += 1
                break
        if added_this_round == 0:
            break
    return picked

def fetch_articles(limit=NEWS_PER_RUN):
    feeds = get_feeds()
    max_per_source = int(get_setting("max_per_source") or 2)

    by_cat = {}
    for feed in feeds:
        by_cat.setdefault(feed["category"], []).append(feed)

    categories = list(by_cat.keys())
    n_cats = len(categories)
    base_quota = limit // n_cats
    remainder = limit % n_cats
    quota = {cat: base_quota + (1 if i < remainder else 0)
             for i, cat in enumerate(categories)}

    seen_titles = set()
    pools = {cat: build_pool(cat_feeds, cat, seen_titles)
             for cat, cat_feeds in by_cat.items()}

    selected = []
    # Pass 1 — fill each category up to its quota.
    for cat in categories:
        round_robin(pools[cat], by_cat[cat], max_per_source,
                    already_selected=[], budget=quota[cat],
                    selected=selected, seen_titles=seen_titles)

    # Pass 2 — backfill: if some categories came up short, spend the slack on
    # categories that still have fresh articles (same per-source cap).
    deficit = limit - len(selected)
    if deficit > 0:
        for cat in categories:
            if deficit <= 0:
                break
            already = [s for s in selected if s["category"] == cat]
            deficit -= round_robin(pools[cat], by_cat[cat], max_per_source,
                                   already_selected=already, budget=deficit,
                                   selected=selected, seen_titles=seen_titles)

    for cat in categories:
        cat_total = sum(1 for s in selected if s["category"] == cat)
        logging.info(f"[{cat}] {cat_total}/{quota[cat]} articles — max {max_per_source}/source")
    logging.info(f"Fetched {len(selected)} articles total | quota={quota} | max_per_source={max_per_source}")
    return selected
