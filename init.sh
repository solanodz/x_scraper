#!/usr/bin/env bash
# init.sh — sincroniza dependencias y verifica el baseline.
# No apilar trabajo nuevo sobre un baseline roto.
set -euo pipefail

cd "$(dirname "$0")"

echo "== X Scraper Terminal :: init =="

# --- Python (scraper / backend) ---
if [ -d ".venv" ]; then
  echo "[py] usando .venv existente"
else
  echo "[py] creando .venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [ -f "requirements.txt" ]; then
  echo "[py] instalando requirements.txt"
  pip install -q -r requirements.txt
fi

echo "[py] verificando sintaxis del scraper"
python -m py_compile scrape_example.py
python -m py_compile scraper/__init__.py scraper/sources.py scraper/serialize.py scraper/store.py scraper/embeddings.py scraper/ingest.py scraper/filters.py scraper/worker.py scraper/retention.py scraper/backfill.py scraper/article_enrichment.py scraper/relevance.py scraper/story_cluster.py scraper/adapters/__init__.py scraper/adapters/base.py scraper/adapters/alpha_vantage.py scraper/adapters/rss.py scraper/adapters/marketaux.py scraper/adapters/x_complement.py

echo "[py] verificando sintaxis del backend"
python -m py_compile \
  backend/__init__.py \
  backend/services/__init__.py \
  backend/services/types.py \
  backend/services/retrieval.py \
  backend/services/search.py \
  backend/services/summarize.py \
  backend/services/ask.py \
  backend/services/briefing.py \
  backend/services/llm.py \
  backend/services/tools.py \
  backend/services/agent.py \
  backend/services/chat_history.py \
  backend/services/research_steps.py \
  backend/services/research_agent.py \
  backend/services/corpus_stats.py \
  backend/services/market_data.py \
  backend/app/__init__.py \
  backend/app/auth.py \
  backend/app/db.py \
  backend/app/main.py \
  backend/app/schemas.py \
  backend/app/services/__init__.py \
  backend/app/services/signals_repo.py \
  backend/app/services/chat_repo.py \
  backend/app/services/ticker_watch_repo.py \
  backend/app/routes/__init__.py \
  backend/app/routes/signals.py \
  backend/app/routes/chat.py \
  backend/app/routes/ingest.py \
  backend/app/routes/quotes.py \
  backend/app/routes/watch.py \
  backend/scripts/__init__.py \
  backend/scripts/verify_f4.py \
  backend/scripts/verify_f5.py \
  backend/scripts/verify_f7.py \
  backend/scripts/verify_f8.py \
  backend/scripts/verify_f9.py \
  backend/scripts/verify_f10.py \
  backend/scripts/verify_f11.py \
  backend/scripts/verify_f12.py \
  backend/scripts/verify_f13.py \
  backend/scripts/verify_f14.py \
  backend/scripts/verify_f15.py \
  backend/scripts/verify_f16.py \
  backend/scripts/verify_f17.py \
  backend/scripts/verify_f18.py \
  backend/scripts/verify_f19.py \
  backend/scripts/verify_f20.py \
  backend/scripts/verify_f21.py \
  backend/scripts/verify_f22.py \
  backend/scripts/verify_f23.py

# --- Docker services (Store: Postgres + pgvector) ---
if [ -f "docker-compose.yml" ] || [ -f "compose.yaml" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "[docker] validando configuración de compose"
    docker compose config >/dev/null
  else
    echo "[docker] docker no disponible — omitiendo validación de compose"
  fi
else
  echo "[docker] aún sin compose (pendiente F1)"
fi

# --- Frontend (Next.js) ---
if [ -f "frontend/package.json" ]; then
  echo "[web] instalando dependencias de frontend"
  (cd frontend && npm install --silent)
else
  echo "[web] aún sin frontend (pendiente F6)"
fi

echo ""
echo "== baseline OK =="
echo "Startup: revisar progress.md -> feature_list.json -> feature activa"
