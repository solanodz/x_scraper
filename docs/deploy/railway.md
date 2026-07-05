# Railway — API + Worker

Deploy both backend services from the monorepo root using the root `Dockerfile`. Railway builds one image; each service overrides only the start command and environment.

## Prerequisites

- GitHub repo connected to [Railway](https://railway.app)
- Supabase project with schema applied (`infra/supabase/migrations/001_init.sql`)
- Secrets ready (see env tables below)

## Project setup

1. **New Project** → Deploy from GitHub → select this repo.
2. Railway detects the root `Dockerfile` automatically.
3. Create **two services** from the same repo (duplicate the service or add a second one):

| Service | Start command |
|---------|---------------|
| `xscraper-api` | *(vacío — usa `CMD` del Dockerfile)* o ver abajo |
| `xscraper-worker` | `python -m scraper.worker --interval 1800` |

Both services use the same Dockerfile build; only the start command differs.

> **API y `$PORT`:** con Dockerfile, Railway no expande `$PORT` en exec form. El `CMD` del Dockerfile ya usa `sh -c` con `${PORT}`. Dejá el **Custom Start Command vacío** en el API, o usá:
>
> ```bash
> sh -c "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
> ```

## Service 1: `xscraper-api`

**Start command:** dejá vacío (usa el `CMD` del Dockerfile) **o**:

```bash
sh -c "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
```

No uses `uvicorn ... --port $PORT` a secas: Docker exec form no expande `$PORT` y el healthcheck falla.

**Health check:** path `/health` (public, no auth). Expected response:

```json
{"status":"ok"}
```

**Environment variables:**

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | yes | Supabase **pooler** URI (transaction mode, port **6543**) |
| `SUPABASE_JWT_SECRET` | yes | Supabase → Settings → API → JWT Settings → JWT Secret |
| `AUTH_ENABLED` | yes | `true` in production |
| `OPENAI_API_KEY` | yes | Embeddings + Research Chat |
| `FINNHUB_API_KEY` | yes | Market Data primario (Quote Strip + Signal Detail) |
| `ALPHA_VANTAGE_API_KEY` | no | Fallback quotes + news ingest; graceful degradation if empty |
| `WATCHLIST` | no | Default watchlist tickers (see `.env.example`) |
| `SIGNAL_FILTER` | no | `relevant` (default), `cashtag`, `strict`, or `off` |
| `SIGNAL_MIN_LIKES` | no | Minimum likes filter (default `0`) |
| `SIGNAL_REQUIRE_LINK` | no | `true` / `false` (default `false`) |
| `QUOTE_CACHE_TTL_SECONDS` | no | Quote cache TTL (default `900`) |
| `QUOTE_MAX_DAILY_REQUESTS` | no | Alpha Vantage fallback daily cap (default `25`) |
| `CORS_ORIGINS` | yes | Comma-separated origins, e.g. `https://<app>.vercel.app,http://localhost:3000` |

**Example `CORS_ORIGINS`:**

```
CORS_ORIGINS=https://x-scraper-terminal.vercel.app,http://localhost:3000
```

Include every Vercel preview/production URL the Operator uses. Redeploy the API after changing CORS.

## Service 2: `xscraper-worker`

**Start command:**

```bash
python -m scraper.worker --interval 1800
```

Runs Ingestion every 30 minutes. For a one-off ingest after deploy, use Railway shell or a temporary override:

```bash
python -m scraper.worker --once
```

**Persistent volume:** mount at `/data` for twscrape account state.

| Mount | Path | Purpose |
|-------|------|---------|
| Volume | `/data` | `ACCOUNTS_DB=/data/accounts.db` |

Railway → Worker service → **Volumes** → add volume, mount path `/data`.

**Environment variables:**

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | yes | Supabase **direct** URI (port **5432**, not pooler) |
| `OPENAI_API_KEY` | yes | Embeddings on ingest |
| `X_COOKIES` | yes | `auth_token=...; ct0=...` from browser session |
| `X_ACCOUNT_NAME` | yes | twscrape account label |
| `ACCOUNTS_DB` | yes | `/data/accounts.db` (on mounted volume) |
| `SIGNAL_FILTER` | no | Same modes as API |
| `WATCHLIST` | no | Same as API (for consistency) |
| `SIGNAL_MIN_LIKES` | no | Same as API |
| `SIGNAL_REQUIRE_LINK` | no | Same as API |

`X_COOKIES` and `ACCOUNTS_DB` must **never** appear on the API service or in git.

## Verification

```bash
# Health (public)
curl https://<api>.up.railway.app/health

# Authenticated signals (requires Supabase access token)
curl -H "Authorization: Bearer <access_token>" \
  "https://<api>.up.railway.app/signals?limit=1"

# Without token → 401
curl -s -o /dev/null -w "%{http_code}" \
  "https://<api>.up.railway.app/signals?limit=1"
```

Copy the public API URL into Vercel as `NEXT_PUBLIC_API_URL` (see `docs/deploy/vercel.md`).

## Local parity

```bash
.venv/bin/python -m backend.scripts.verify_f9
```

With `AUTH_ENABLED=true` and `SUPABASE_JWT_SECRET` set locally, verify_f9 confirms `/health` is public and `/signals` returns 401 without a token.
