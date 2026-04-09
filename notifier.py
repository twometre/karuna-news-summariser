import requests
import logging
from datetime import datetime, timezone, timedelta
from config import LOG_PATH
from db import get_setting, mark_seen

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

CATEGORY_EMOJI = {"tech": "💻", "gaming": "🎮", "world": "🌏"}

def send_to_discord(articles):
    webhook_url = get_setting("discord_webhook_url") or __import__('config').DISCORD_WEBHOOK_URL
    if not webhook_url:
        logging.error("No Discord webhook URL configured")
        return False

    bkk_time = datetime.now(timezone(timedelta(hours=7)))
    time_str = bkk_time.strftime("%d %b %Y · %H:%M ICT")

    try:
        requests.post(webhook_url, json={
            "content": f"📡 **Karuna News Summariser** — {time_str}\n{len(articles)} stories from your feeds"
        }).raise_for_status()
    except Exception as e:
        logging.error(f"Failed to send header: {e}")
        return False

    success = 0
    for i, article in enumerate(articles, 1):
        summary_lines = article["summary"].split("\n")
        clean_summary = "\n".join(l for l in summary_lines if not l.strip().startswith("Source:")).strip()
        embed = {
            "title": f"{CATEGORY_EMOJI.get(article['category'], '📰')} {article['title']}",
            "description": clean_summary,
            "url": article["url"],
            "color": {"tech": 0x5865F2, "gaming": 0x57F287, "world": 0xFF9F1C}.get(article["category"], 0xAAAAAA),
            "footer": {"text": f"#{i} · {article['category'].upper()} · Karuna News Summariser"}
        }
        try:
            requests.post(webhook_url, json={"embeds": [embed]}).raise_for_status()
            mark_seen(article["url"], article["title"])
            success += 1
        except Exception as e:
            logging.error(f"Failed to send article {i}: {e}")

    logging.info(f"Sent {success}/{len(articles)} articles to Discord")
    print(f"✅ Sent {success}/{len(articles)} articles to Discord")
    return success > 0
