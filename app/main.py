import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from db import init_db, get_setting
from pipeline import run_pipeline, setup_logging

setup_logging()

def handle_shutdown(sig, frame):
    print("\n🛑 Karuna shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    init_db()

    # Migrate feeds from config if DB empty
    from db import get_conn
    from config import RSS_FEEDS
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM feeds")
    if c.fetchone()[0] == 0:
        name_map = {
            'hnrss.org':'Hacker News','blognone.com':'Blognone',
            'techpowerup.com':'TechPowerUp','theverge.com':'The Verge (AI)',
            'feedburner.com':'AI Weekly','eurogamer.net':'Eurogamer',
            'pocketgamer.com':'Pocket Gamer','toucharcade.com':'TouchArcade',
            'aljazeera.com':'Al Jazeera','bbci.co.uk':'BBC World',
            'dw.com':'Deutsche Welle','channelnewsasia.com':'CNA',
        }
        for feed in RSS_FEEDS:
            domain = [k for k in name_map if k in feed['url']]
            name = name_map[domain[0]] if domain else feed['url']
            try:
                conn.execute("INSERT OR IGNORE INTO feeds (url, name, category) VALUES (?, ?, ?)",
                             (feed['url'], name, feed['category']))
            except Exception:
                pass
        conn.commit()
        logging.info("Feeds migrated to DB")
    conn.close()

    schedule = get_setting("schedule_hours") or "0,6,12,18"
    hours = ",".join(h.strip() for h in schedule.split(","))

    print("🌿 Karuna News Summariser v0.3.0 starting...")
    scheduler = BlockingScheduler(timezone="Asia/Bangkok")
    scheduler.add_job(run_pipeline, CronTrigger(hour=hours, minute=0, timezone="Asia/Bangkok"))

    print("🚀 Running initial pipeline now...")
    run_pipeline()
    print(f"⏰ Scheduler active — runs at {schedule} ICT")
    logging.info("Scheduler started")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        handle_shutdown(None, None)
