#!/bin/bash
# Karuna deploy: /opt/karuna (this repo) → /opt/docker/karuna (compose project)
# The Dockerfile does `COPY app/ .` — code MUST land in app/, never the project root.
# (2026-10-21: rsync to root once produced a stale-code image and a double digest.)
set -euo pipefail
SRC=/opt/karuna
DST=/opt/docker/karuna

rsync -a --delete --exclude '__pycache__' "$SRC/app/" "$DST/app/"
rsync -a "$SRC/requirements.txt" "$SRC/Dockerfile" "$SRC/docker-compose.yml" "$DST/"
# .env is deliberately never touched by this script.

cd "$DST"
docker compose up -d --build
docker compose ps
