import feedparser
import logging
from config import LOG_PATH, NEWS_PER_RUN
from db import is_seen, get_conn, get_setting

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

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

def fetch_articles(limit=NEWS_PER_RUN):
    feeds = get_feeds()
    max_per_source = int(get_setting("max_per_source") or 2)

    # แยก feeds ตาม category
    by_cat = {}
    for feed in feeds:
        by_cat.setdefault(feed["category"], []).append(feed)

    categories = list(by_cat.keys())
    n_cats = len(categories)
    base_quota = limit // n_cats
    remainder = limit % n_cats
    quota = {cat: base_quota + (1 if i < remainder else 0)
             for i, cat in enumerate(categories)}

    selected = []
    seen_titles = set()

    for cat, cat_feeds in by_cat.items():
        cat_quota = quota[cat]

        # ดึงทุก entry จากทุก feed ใน category นี้ก่อน พร้อม track source
        pool = []
        for feed in cat_feeds:
            source_url = feed["url"]
            try:
                parsed = feedparser.parse(source_url)
                for entry in parsed.entries:
                    url = entry.get("link", "")
                    title = entry.get("title", "")
                    summary = entry.get("summary", entry.get("description", ""))
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

        # Round-robin ตาม source — หยิบทีละ 1 จากแต่ละ source วนไป
        # จนกว่าจะครบ quota หรือหมด pool
        source_counts = {}
        round_num = 1

        while len(selected) < limit:
            added_this_round = 0

            for feed in cat_feeds:
                if len(selected) >= limit:
                    break
                src = feed["url"]
                if source_counts.get(src, 0) >= max_per_source:
                    continue

                # หา entry ถัดไปจาก source นี้ที่ยังไม่ถูกเลือก
                for article in pool:
                    if article["source"] != src:
                        continue
                    if article["title"] in seen_titles:
                        continue
                    if source_counts.get(src, 0) >= max_per_source:
                        break

                    # เช็คว่า category นี้ยังไม่เกิน quota
                    cat_selected = sum(1 for s in selected if s["category"] == cat)
                    if cat_selected >= cat_quota:
                        break

                    selected.append(article)
                    seen_titles.add(article["title"])
                    source_counts[src] = source_counts.get(src, 0) + 1
                    added_this_round += 1
                    break

            if added_this_round == 0:
                break  # ไม่มีอะไรเพิ่มได้แล้ว หยุด
            round_num += 1

        cat_total = sum(1 for s in selected if s["category"] == cat)
        logging.info(f"[{cat}] {cat_total}/{cat_quota} articles — max {max_per_source}/source")

    logging.info(f"Fetched {len(selected)} articles total | quota={quota} | max_per_source={max_per_source}")
    return selected
