# Karuna News Summariser v0.1.0
# config.py

import os

DATA_DIR = "/mnt/usb-storage/karuna"
DB_PATH = os.path.join(DATA_DIR, "db", "karuna.db")
LOG_PATH = os.path.join(DATA_DIR, "logs", "karuna.log")

SUMMARY_MAX_WORDS = 80
NEWS_PER_RUN = 10

RSS_FEEDS = [
    {"url": "https://hnrss.org/frontpage", "category": "tech"},
    {"url": "https://www.blognone.com/news/feed", "category": "tech"},
    {"url": "https://www.techpowerup.com/rss/news.xml", "category": "tech"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "category": "tech"},
    {"url": "https://feeds.feedburner.com/aiweekly", "category": "tech"},
    {"url": "https://www.eurogamer.net/feed", "category": "gaming"},
    {"url": "https://www.pocketgamer.com/feed/", "category": "gaming"},
    {"url": "https://toucharcade.com/feed/", "category": "gaming"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "world"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "world"},
    {"url": "https://rss.dw.com/rdf/rss-en-all", "category": "world"},
    {"url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml", "category": "world"},
]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

ADMIN_PASSWORD = "87345A6d"
ADMIN_HINT = "-----A6d"
