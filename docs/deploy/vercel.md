# Vercel — Frontend (Terminal)

Deploy the Next.js Terminal from the `frontend/` subdirectory.

## Project setup

1. [Vercel](https://vercel.com) → **New Project** → import the GitHub repo.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js** (auto-detected).
4. Build command: `npm run build` (default).
5. Output: Next.js default (no custom output directory).

## Environment variables

Set in Vercel → Project → **Settings → Environment Variables** (Production, Preview, and Development as needed):

| Variable | Required | Example |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | yes | `https://xscraper-api.up.railway.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | yes | `https://<ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | `eyJ...` (anon public key) |

Copy values from Supabase → Settings → API (`Project URL`, `anon public`).

Local template: `frontend/.env.local.example`.

## CORS on Railway API

After the first Vercel deploy, add the Vercel URL to the Railway API service:

```
CORS_ORIGINS=https://<app>.vercel.app,http://localhost:3000
```

For preview deployments, include preview origin patterns or add specific preview URLs as needed. **Redeploy the Railway API** after updating `CORS_ORIGINS`.

Without this, the browser blocks API requests from the Vercel origin.

## Routes

| Path | Access |
|------|--------|
| `/login` | Public — Supabase email/password sign-in |
| `/` | Protected — redirects to `/login` without session |

Middleware (`frontend/src/middleware.ts`) refreshes the Supabase session and enforces the login gate.

## Verification (E2E smoke test)

1. Open `https://<app>.vercel.app/login`.
2. Sign in with the Operator account (created in Supabase Auth).
3. Terminal loads: Signal Feed, Signal Detail, Research Chat.
4. Feed connects via SSE (LIVE indicator) with bearer token.
5. Research Chat streams a response with Citations.
6. Quote Strip shows watchlist prices (if `ALPHA_VANTAGE_API_KEY` is set on API).
7. **Refresh** triggers `POST /ingest/refresh` on Railway API.

Document results in `progress.md` and `feature_list.json` evidence when marking F9 `passing`.

## Local development

```bash
cd frontend
cp .env.local.example .env.local
# Edit NEXT_PUBLIC_* values
npm run dev
```

Run the API locally on port 8000 with `AUTH_ENABLED=false` for token-free dev, or `AUTH_ENABLED=true` to match production auth behavior.
