# admin.py — Karuna Admin Panel v0.1.0

import threading
import re
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, session

from config import ADMIN_PASSWORD, LOG_PATH
from db import get_conn, get_setting, set_setting, init_db

app = Flask(__name__)
app.secret_key = "karuna-admin-s3cr3t-key-2026"
ICT = timezone(timedelta(hours=7))

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authed'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def get_next_run():
    now = datetime.now(ICT)
    hours = [int(h) for h in (get_setting("schedule_hours") or "0,6,12,18").split(",")]
    hours.sort()
    for h in hours:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate.strftime("%H:%M ICT")
    tomorrow = now.replace(hour=hours[0], minute=0, second=0, microsecond=0) + timedelta(days=1)
    return tomorrow.strftime("%H:%M ICT (+1d)")

def parse_logs(n=50):
    lines = []
    try:
        with open(LOG_PATH, 'r') as f:
            raw = f.readlines()[-n:]
        for line in raw:
            line = line.strip()
            if not line:
                continue
            ts = line[11:19] if len(line) > 19 else ""
            msg = line[32:] if len(line) > 32 else line
            if "[ERROR]" in line:
                level, icon = "err", "✗"
            elif "[WARNING]" in line:
                level, icon = "warn", "!"
            elif any(x in msg for x in ["Sent", "Pipeline", "initialised", "started"]):
                level, icon = "ok", "✓"
            else:
                level, icon = "info", "i"
            lines.append({"ts": ts, "level": level, "icon": icon, "msg": msg})
    except Exception:
        pass
    return lines

def get_feeds_from_db():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT url, name, category FROM feeds ORDER BY category, name")
        return [{"url": r[0], "name": r[1], "category": r[2]} for r in c.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM seen_articles")
        seen = c.fetchone()[0]
        feeds = get_feeds_from_db()
        cats = len(set(f['category'] for f in feeds))
        today = datetime.now(ICT).strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*) FROM seen_articles WHERE date(seen_at) = ?", (today,))
        sent_today = c.fetchone()[0]
        word_limit = int(get_setting("summary_max_words") or 80)
        return {"seen_count": seen, "feed_count": len(feeds), "category_count": cats,
                "sent_today": sent_today, "word_limit": word_limit}
    except Exception:
        return {"seen_count": 0, "feed_count": 0, "category_count": 0, "sent_today": 0, "word_limit": 80}
    finally:
        conn.close()

def get_token_stats():
    price_in, price_out = 0.80, 4.00
    avg_input, avg_output = 600, 150
    fx_rate, budget_usd = 34.0, 5.0
    schedule = get_setting("schedule_hours") or "0,6,12,18"
    runs_per_day = len(schedule.split(","))
    news_per_run = int(get_setting("news_per_run") or 10)
    runs_month = runs_per_day * 30
    articles_month = runs_month * news_per_run
    tokens_in = articles_month * avg_input
    tokens_out = articles_month * avg_output
    cost_usd = (tokens_in / 1_000_000 * price_in) + (tokens_out / 1_000_000 * price_out)
    cost_thb = cost_usd * fx_rate
    budget_thb = budget_usd * fx_rate
    return {
        "runs_month": runs_month,
        "tokens_month": f"{(tokens_in + tokens_out):,}",
        "cost_thb": f"{cost_thb:.1f}",
        "budget_thb": f"{budget_thb:.0f}",
        "gauge_pct": min(100, round(cost_thb / budget_thb * 100)),
        "avg_input_tokens": avg_input,
        "avg_output_tokens": avg_output,
        "price_in": price_in,
        "price_out": price_out,
        "fx_rate": fx_rate,
    }

def mask_secret(val):
    if not val:
        return "(not set)"
    return val[:6] + "…" + val[-4:] if len(val) > 12 else "••••••"

@app.route('/')
def index():
    return redirect('/dashboard' if session.get('authed') else '/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    messages = []
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['authed'] = True
            return redirect('/dashboard')
        messages.append(("Incorrect password", "err"))
    return render_template('login.html', messages=messages, next_run="")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
        messages=session.pop('flash', []),
        stats=get_stats(),
        logs=parse_logs(8),
        token=get_token_stats(),
        next_run=get_next_run())

@app.route('/run', methods=['POST'])
@login_required
def run_now():
    def _run():
        from crawler import fetch_articles
        from summariser import summarise_batch
        from notifier import send_to_discord
        articles = fetch_articles(limit=int(get_setting("news_per_run") or 10))
        summaries = summarise_batch(articles)
        send_to_discord(summaries)
    threading.Thread(target=_run, daemon=True).start()
    session['flash'] = [("Pipeline started — check Discord in ~30 seconds", "ok")]
    return redirect('/dashboard')

@app.route('/feeds')
@login_required
def feeds():
    return render_template('feeds.html',
        messages=session.pop('flash', []),
        feeds=get_feeds_from_db(),
        next_run=get_next_run())

@app.route('/feeds/add', methods=['POST'])
@login_required
def feeds_add():
    url = request.form.get('url', '').strip()
    name = request.form.get('name', '').strip()
    category = request.form.get('category', 'tech')
    if not url or not name:
        session['flash'] = [("URL and name are required", "err")]
        return redirect('/feeds')
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO feeds (url, name, category) VALUES (?, ?, ?)", (url, name, category))
        conn.commit()
        session['flash'] = [("Feed added — applied immediately", "ok")]
    except Exception as e:
        session['flash'] = [(f"Error: {e}", "err")]
    finally:
        conn.close()
    return redirect('/feeds')

@app.route('/feeds/remove', methods=['POST'])
@login_required
def feeds_remove():
    url = request.form.get('url', '')
    conn = get_conn()
    try:
        conn.execute("DELETE FROM feeds WHERE url = ?", (url,))
        conn.commit()
        session['flash'] = [("Feed removed", "ok")]
    except Exception as e:
        session['flash'] = [(f"Error: {e}", "err")]
    finally:
        conn.close()
    return redirect('/feeds')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html',
        messages=session.pop('flash', []),
        schedule_hours=get_setting("schedule_hours") or "0,6,12,18",
        news_per_run=get_setting("news_per_run") or "10",
        word_limit=get_setting("summary_max_words") or "80",
        max_per_source=get_setting("max_per_source") or "2",
        api_key_hint=mask_secret(get_setting("anthropic_api_key")),
        webhook_hint=mask_secret(get_setting("discord_webhook_url")),
        next_run=get_next_run())

@app.route('/settings/schedule', methods=['POST'])
@login_required
def settings_schedule():
    hours_raw = request.form.get('schedule_hours', '').strip()
    news_raw = request.form.get('news_per_run', '10').strip()
    hours_valid = re.match(r'^(\d{1,2},)*\d{1,2}$', hours_raw) and \
                  all(0 <= int(h) <= 23 for h in hours_raw.split(','))
    if not hours_valid:
        session['flash'] = [("Invalid hours — use comma-separated 0-23 e.g. 0,6,12,18", "err")]
        return redirect('/settings')
    if not news_raw.isdigit() or not 1 <= int(news_raw) <= 20:
        session['flash'] = [("Articles per run must be 1–20", "err")]
        return redirect('/settings')
    set_setting("schedule_hours", hours_raw)
    set_setting("news_per_run", news_raw)
    session['flash'] = [("Schedule updated — restart Karuna service to apply", "warn")]
    return redirect('/settings')

@app.route('/settings/summary', methods=['POST'])
@login_required
def settings_summary():
    val = request.form.get('word_limit', '80')
    if val.isdigit() and 30 <= int(val) <= 200:
        set_setting("summary_max_words", val)
        session['flash'] = [(f"Word limit set to {val} — applied immediately", "ok")]
    else:
        session['flash'] = [("Invalid value — must be 30–200", "err")]
    return redirect('/settings')

@app.route('/settings/apikey', methods=['POST'])
@login_required
def settings_apikey():
    key = request.form.get('api_key', '').strip()
    if key.startswith('sk-'):
        set_setting("anthropic_api_key", key)
        session['flash'] = [("API key updated — applied immediately", "ok")]
    else:
        session['flash'] = [("Invalid key — must start with sk-", "err")]
    return redirect('/settings')

@app.route('/settings/webhook', methods=['POST'])
@login_required
def settings_webhook():
    url = request.form.get('webhook_url', '').strip()
    if url.startswith('https://discord.com/api/webhooks/'):
        set_setting("discord_webhook_url", url)
        session['flash'] = [("Webhook updated — applied immediately", "ok")]
    else:
        session['flash'] = [("Invalid webhook URL", "err")]
    return redirect('/settings')

@app.route('/logs')
@login_required
def logs():
    return render_template('logs.html',
        messages=[],
        logs=parse_logs(100),
        next_run=get_next_run())


@app.route('/settings/diversity', methods=['POST'])
@login_required
def settings_diversity():
    val = request.form.get('max_per_source', '2')
    if val.isdigit() and 1 <= int(val) <= 5:
        set_setting('max_per_source', val)
        session['flash'] = [(f'Max per source set to {val} — applied immediately', 'ok')]
    else:
        session['flash'] = [('Invalid value — must be 1–5', 'err')]
    return redirect('/settings')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8765, debug=False)
