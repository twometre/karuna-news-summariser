# pipeline.py — shared run logic for scheduler, admin /run, and Discord bot.
import os
import fcntl
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from config import LOG_PATH, LOCK_PATH
from db import get_setting, mark_seen

def setup_logging():
    """Rotate the app log — it lives on a USB stick and grew unbounded."""
    handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(handler)

@contextmanager
def pipeline_lock():
    """Cross-container mutual exclusion: all three services share this file
    via the bind mount, and flock() is kernel-level so it works across them."""
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise RuntimeError("Another pipeline run is already in progress")
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()

def run_pipeline():
    from crawler import fetch_articles
    from summariser import summarise_batch
    from notifier import send_to_discord

    bkk_time = datetime.now(timezone(timedelta(hours=7))).strftime("%d %b %Y %H:%M ICT")
    logging.info(f"=== Pipeline started at {bkk_time} ===")
    print(f"\n[{bkk_time}] Pipeline starting...")

    try:
        with pipeline_lock():
            limit = int(get_setting("news_per_run") or 10)
            articles = fetch_articles(limit=limit)
            if not articles:
                logging.warning("No new articles found")
                print("⚠️  No new articles found")
                return False
            print(f"✅ Fetched {len(articles)} articles")
            summaries = summarise_batch(articles)
            print(f"✅ Summarised {len(summaries)} articles")
            # Mark seen BEFORE sending: a failed Discord post must not cause
            # the article to be re-summarised (and re-billed) next run.
            for s in summaries:
                mark_seen(s["url"], s["title"])
            return send_to_discord(summaries)
    except RuntimeError as e:
        logging.warning(str(e))
        print(f"⏭️  {e}")
        return False
