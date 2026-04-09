# Karuna News Summariser


> Named after Karuna Buakhamsri (กรุณา บัวคำศรี) — a legendary Thai journalist whose work embodied clarity, courage, and dedication to informed public discourse. This project is a small tribute to that spirit.

## What is this

A self-hosted RSS news summariser that runs on a home server, fetches articles from curated feeds, summarises each one in under 80 words using the Claude API, and delivers them to Discord — four times a day, no doomscrolling required.

Built as a vibe coding experiment: can you build something genuinely useful, running on your own hardware, without it becoming a full-time job? Turns out yes.

## Features

- RSS feed aggregation across Tech, Gaming, and World News categories
- Summarisation via `claude-haiku-4-5` — fast, cheap, good enough
- Deduplication across runs — no repeat articles
- Discord delivery with category colour coding
- Web-based admin panel — manage feeds, settings, API keys, view logs
- Scheduled at 00:00 / 06:00 / 12:00 / 18:00 ICT

## Stack

- `feedparser` — RSS parsing
- `anthropic` — summarisation
- `flask` — admin panel (port 8765)
- `apscheduler` — scheduling
- `sqlite` — deduplication + settings storage

## Project structure

```
main.py        — scheduler entry point
crawler.py     — RSS fetching
summariser.py  — Claude API calls
notifier.py    — Discord webhook delivery
admin.py       — Flask admin panel
db.py          — SQLite helpers
config.py      — env-based configuration
templates/     — admin panel HTML
```

## Setup

Copy `env.example` to `/etc/karuna.env` and fill in your keys. Designed to run as a systemd service on Ubuntu Server.

```bash
cp env.example /etc/karuna.env
# edit /etc/karuna.env with your keys
sudo systemctl enable --now karuna karuna-admin
```

## Versioning

Follows `MAJOR.MINOR.PATCH` — semver, loosely. Breaking changes bump MAJOR, new features bump MINOR, fixes bump PATCH.
