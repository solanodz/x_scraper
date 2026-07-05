# F9 Platform Deploy + Supabase Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Operator Terminal to production (Vercel + Railway + Supabase) with Supabase Auth protecting all API routes except `/health`.

**Architecture:** Supabase hosts Postgres+pgvector and Auth. Railway runs two services from the monorepo: FastAPI (public) and Worker (cron). Vercel hosts Next.js with login gate. FastAPI validates Supabase JWT on every request; frontend attaches bearer token from session. SSE feed uses `@microsoft/fetch-event-source` because native `EventSource` cannot send `Authorization` headers.

**Tech Stack:** Supabase (Postgres, pgvector, Auth), Railway, Vercel, FastAPI, PyJWT, `@supabase/ssr`, `@microsoft/fetch-event-source`

**Spec:** `docs/superpowers/specs/2026-07-04-operator-terminal-design.md`  
**ADR:** `docs/adr/0003-supabase-railway-vercel-deploy.md`

---

## File map (F9)

| File | Responsibility |
|------|----------------|
| `infra/supabase/migrations/001_init.sql` | Schema reproducible en Supabase (vector + signals) |
| `backend/app/auth.py` | JWT validation + FastAPI dependency |
| `backend/app/main.py` | CORS desde env, auth middleware global |
| `backend/scripts/verify_f9.py` | Verificación auth + health |
| `frontend/src/lib/supabase/client.ts` | Browser Supabase client |
| `frontend/src/lib/supabase/server.ts` | Server Supabase client (middleware) |
| `frontend/src/lib/supabase/middleware.ts` | Session refresh helper |
| `frontend/src/middleware.ts` | Route protection |
| `frontend/src/app/login/page.tsx` | Login UI |
| `frontend/src/lib/api.ts` | Bearer token en fetch + SSE |
| `frontend/src/components/SignalFeed.tsx` | fetch-event-source con auth |
| `Dockerfile` | Imagen Python para Railway (API + Worker) |
| `railway.api.toml` | Start command API |
| `railway.worker.toml` | Start command Worker |
| `frontend/vercel.json` | Root directory hint (si hace falta) |
| `.env.example` | Vars nuevas documentadas |
| `feature_list.json` | Feature F9 |

---

## Task 1: Supabase schema migration

**Files:**
- Create: `infra/supabase/migrations/001_init.sql`

- [ ] **Step 1: Create migration file**

```sql
-- infra/supabase/migrations/001_init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS signals (
    id_str           TEXT PRIMARY KEY,
    published_at     TIMESTAMPTZ NOT NULL,
    username         TEXT NOT NULL,
    raw_content      TEXT NOT NULL,
    source           TEXT NOT NULL,
    cashtags         TEXT[] NOT NULL DEFAULT '{}',
    hashtags         TEXT[] NOT NULL DEFAULT '{}',
    article          JSONB,
    reply_count      INTEGER NOT NULL DEFAULT 0,
    retweet_count    INTEGER NOT NULL DEFAULT 0,
    like_count       INTEGER NOT NULL DEFAULT 0,
    quote_count      INTEGER NOT NULL DEFAULT 0,
    bookmarked_count INTEGER NOT NULL DEFAULT 0,
    payload          JSONB NOT NULL,
    embedding        vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_signals_published_at ON signals (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_cashtags ON signals USING GIN (cashtags);
```

- [ ] **Step 2: Apply in Supabase SQL Editor**

Run the file contents in Supabase Dashboard → SQL Editor.

Expected: `Success. No rows returned`

- [ ] **Step 3: Verify extension**

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Expected: one row `vector`

- [ ] **Step 4: Copy connection strings**

From Supabase → Settings → Database:
- **Pooler URI** (port 6543, mode Transaction) → `DATABASE_URL` for Railway API
- **Direct URI** (port 5432) → `DATABASE_URL` for Railway Worker

---

## Task 2: Supabase Auth setup (manual)

**Files:** none (dashboard ops)

- [ ] **Step 1: Enable Email provider**

Supabase → Authentication → Providers → Email → enabled.

- [ ] **Step 2: Create Operator user**

Authentication → Users → Add user → email + password (tu cuenta).

- [ ] **Step 3: Disable public signups**

Authentication → Settings → disable "Enable email signups" (solo tu cuenta existe).

- [ ] **Step 4: Copy secrets**

Settings → API:
- `Project URL` → `NEXT_PUBLIC_SUPABASE_URL`
- `anon public` → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Settings → API → JWT Settings → `JWT Secret` → `SUPABASE_JWT_SECRET` (Railway API only)

---

## Task 3: Backend JWT auth

**Files:**
- Create: `backend/app/auth.py`
- Modify: `backend/app/main.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add PyJWT**

Add to `requirements.txt`:

```
PyJWT>=2.8
```

Run: `.venv/bin/pip install PyJWT`

- [ ] **Step 2: Create auth module**

```python
# backend/app/auth.py
"""Supabase JWT validation."""

from __future__ import annotations

import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def auth_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("AUTH_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_jwt_secret() -> str | None:
    load_dotenv()
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    return secret or None


def verify_token(token: str) -> dict:
    secret = get_jwt_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET not configured",
        )
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    if not auth_enabled():
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return verify_token(credentials.credentials)
```

- [ ] **Step 3: Wire auth middleware in main.py**

```python
# backend/app/main.py (additions)
import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.auth import PUBLIC_PATHS, auth_enabled, get_current_user

load_dotenv()

def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]

app = FastAPI(...)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def require_auth(request: Request, call_next):
    if not auth_enabled():
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})
    token = auth_header.removeprefix("Bearer ").strip()
    from backend.app.auth import verify_token
    try:
        verify_token(token)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
    return await call_next(request)
```

- [ ] **Step 4: Local dev bypass**

Add to local `.env`:

```
AUTH_ENABLED=false
```

Run: `.venv/bin/uvicorn backend.app.main:app --reload --port 8000`

Expected: `GET /signals` works without token locally.

- [ ] **Step 5: Test auth locally**

Set `AUTH_ENABLED=true` and `SUPABASE_JWT_SECRET=<from supabase>` temporarily.

```bash
# sin token → 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/signals

# con token (obtener desde login en frontend o supabase CLI)
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/signals?limit=1
```

Expected: `401` sin token, `200` con token válido.

---

## Task 4: verify_f9 script

**Files:**
- Create: `backend/scripts/verify_f9.py`
- Modify: `init.sh` (add to py_compile list)

- [ ] **Step 1: Write verification script**

```python
"""Verificación F9: Auth + health."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.main import app

def main() -> int:
    load_dotenv()
    print("== F9 verification: Platform Auth ==\n")
    client = TestClient(app)

    print("1. GET /health (public)")
    r = client.get("/health")
    if r.status_code != 200:
        print(f"   FAIL: {r.status_code}")
        return 1
    print("   PASS\n")

    auth_on = os.getenv("AUTH_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()

    print("2. GET /signals without token")
    r = client.get("/signals?limit=1")
    if auth_on and secret:
        if r.status_code != 401:
            print(f"   FAIL: expected 401, got {r.status_code}")
            return 1
        print("   PASS (401 as expected)\n")
    else:
        print("   SKIP (AUTH_ENABLED=false or no JWT secret)\n")

    print("== F9 verification OK ==")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run**

```bash
.venv/bin/python -m backend.scripts.verify_f9
```

Expected: `F9 verification OK`

---

## Task 5: Frontend Supabase Auth

**Files:**
- Create: `frontend/src/lib/supabase/client.ts`
- Create: `frontend/src/lib/supabase/server.ts`
- Create: `frontend/src/lib/supabase/middleware.ts`
- Create: `frontend/src/middleware.ts`
- Create: `frontend/src/app/login/page.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/.env.local.example`

- [ ] **Step 1: Install packages**

```bash
cd frontend && npm install @supabase/supabase-js @supabase/ssr
```

- [ ] **Step 2: Browser client**

```typescript
// frontend/src/lib/supabase/client.ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
```

- [ ] **Step 3: Server client**

```typescript
// frontend/src/lib/supabase/server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        },
      },
    },
  );
}
```

- [ ] **Step 4: Middleware session refresh**

```typescript
// frontend/src/lib/supabase/middleware.ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );
  const { data: { user } } = await supabase.auth.getUser();
  return { supabaseResponse, user };
}
```

- [ ] **Step 5: Route middleware**

```typescript
// frontend/src/middleware.ts
import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  const { supabaseResponse, user } = await updateSession(request);
  const isLogin = request.nextUrl.pathname.startsWith("/login");

  if (!user && !isLogin) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (user && isLogin) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }
  return supabaseResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 6: Login page**

```tsx
// frontend/src/app/login/page.tsx
"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }
    window.location.href = "/";
  }

  return (
    <div className="flex h-full items-center justify-center bg-zinc-950">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded border border-zinc-800 bg-zinc-900 p-6"
      >
        <h1 className="font-sans text-sm font-semibold text-amber-500">
          X Scraper Terminal
        </h1>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
          className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
          className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200"
        />
        {error && (
          <p className="font-mono text-xs text-red-400">{error}</p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded border border-zinc-700 bg-zinc-800 py-2 font-sans text-xs text-zinc-300 hover:border-amber-600"
        >
          {loading ? "…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 7: Update `.env.local.example`**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

- [ ] **Step 8: Build check**

```bash
cd frontend && npm run build
```

Expected: build OK

---

## Task 6: API client + SSE with bearer token

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/SignalFeed.tsx`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install fetch-event-source**

```bash
cd frontend && npm install @microsoft/fetch-event-source
```

- [ ] **Step 2: Token helper in api.ts**

```typescript
import { createClient } from "@/lib/supabase/client";

async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function authHeaders(): Promise<HeadersInit> {
  const token = await getAccessToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
```

Wrap all `fetch()` calls in `api.ts` with `headers: { ...await authHeaders(), ... }`.

- [ ] **Step 3: Replace EventSource in SignalFeed**

Use `fetchEventSource` from `@microsoft/fetch-event-source`:

```typescript
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { createClient } from "@/lib/supabase/client";

// inside useEffect:
const supabase = createClient();
const { data: { session } } = await supabase.auth.getSession();
const token = session?.access_token;
if (!token) return;

const ctrl = new AbortController();
fetchEventSource(`${API_URL}/signals/stream`, {
  headers: { Authorization: `Bearer ${token}` },
  signal: ctrl.signal,
  onopen: async (res) => { if (res.ok) setConnected(true); },
  onmessage: (ev) => { /* parse event: signal */ },
  onerror: () => setConnected(false),
});
return () => ctrl.abort();
```

- [ ] **Step 4: Manual test local**

1. Set `AUTH_ENABLED=true` on API with `SUPABASE_JWT_SECRET`
2. `npm run dev` + login → feed loads + LIVE indicator

---

## Task 7: Railway deploy (API + Worker)

**Files:**
- Create: `Dockerfile`
- Create: `railway.toml` (or two service configs in Railway UI)

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY scraper ./scraper
COPY infra ./infra
ENV PYTHONPATH=/app
```

- [ ] **Step 2: Create Railway project**

1. railway.app → New Project → Deploy from GitHub repo
2. Service **xscraper-api**:
   - Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - Env vars from spec section 8 (API block)
   - `AUTH_ENABLED=true`
3. Service **xscraper-worker**:
   - Start: `python -m scraper.worker --interval 1800`
   - Env vars from spec section 8 (Worker block)
   - Attach volume at `/data` for `ACCOUNTS_DB=/data/accounts.db`

- [ ] **Step 3: Health check**

Railway API → healthcheck path `/health`

```bash
curl https://<api>.up.railway.app/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Test authenticated API**

```bash
curl -H "Authorization: Bearer <token>" https://<api>.up.railway.app/signals?limit=1
```

Expected: JSON array (possibly empty if fresh Supabase)

---

## Task 8: Vercel deploy (frontend)

**Files:**
- Modify: Vercel project settings (dashboard)

- [ ] **Step 1: Import repo**

Vercel → New Project → select repo → Root Directory: `frontend`

- [ ] **Step 2: Environment variables**

```
NEXT_PUBLIC_API_URL=https://<api>.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

- [ ] **Step 3: Update Railway CORS**

```
CORS_ORIGINS=https://<app>.vercel.app,http://localhost:3000
```

Redeploy API after CORS change.

- [ ] **Step 4: E2E smoke test**

1. Open `https://<app>.vercel.app/login`
2. Sign in → Terminal loads
3. Feed shows signals (or empty + Refresh)
4. Chat responds
5. Quote strip shows prices

Document results in `progress.md` and `feature_list.json` evidence.

---

## Task 9: Data migration (optional)

**Files:** none

- [ ] **Step 1: Export local (if corpus útil)**

```bash
docker exec xscraper_store pg_dump -U xscraper -d xscraper -t signals --data-only > signals_data.sql
```

- [ ] **Step 2: Import to Supabase** (or skip and re-ingest)

Run Worker `--once` on Railway after deploy — más limpio si hay junk histórico.

- [ ] **Step 3: Verify counts**

```sql
SELECT count(*) FROM signals;
SELECT count(embedding) FROM signals;
```

---

## Task 10: Harness updates

**Files:**
- Modify: `feature_list.json` (add F9)
- Modify: `progress.md`
- Modify: `init.sh`
- Modify: `.env.example`
- Modify: `docs/superpowers/specs/2026-07-04-operator-terminal-design.md` (`approved_by: user`)

- [ ] **Step 1: Add F9 to feature_list.json**

```json
{
  "id": "F9",
  "priority": 9,
  "title": "Platform: Supabase + Railway + Vercel + Auth",
  "user_visible_behavior": "Terminal en URL pública con login Supabase; API y Worker en Railway; Store en Supabase.",
  "status": "in_progress",
  "dependencies": ["F8"],
  "verification": [
    "Login en Vercel → acceso a Terminal",
    "GET /signals sin token → 401 en producción",
    "Feed SSE + Chat + Quotes funcionan autenticados",
    "Worker ingesta en Supabase"
  ],
  "evidence": []
}
```

- [ ] **Step 2: Mark passing only after E2E evidence**

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Supabase pgvector + schema | Task 1 |
| Supabase Auth + disable signups | Task 2 |
| JWT middleware FastAPI | Task 3 |
| CORS Vercel origins | Task 3, 8 |
| Frontend login + middleware | Task 5 |
| Bearer token API calls | Task 6 |
| SSE with auth | Task 6 |
| Railway API + Worker | Task 7 |
| Vercel deploy | Task 8 |
| verify script | Task 4 |
| Env vars documented | Task 10 |
| Data migration | Task 9 |

---

## Self-review

- No TBD placeholders in tasks.
- SSE auth gap explicitly handled (fetch-event-source).
- Local dev preserved via `AUTH_ENABLED=false`.
- Worker secrets (`X_COOKIES`) only on Railway Worker.
- F11 tables deferred (not in F9 scope).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-04-f9-platform-deploy-auth.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — implement task-by-task in this session with checkpoints

**Which approach?**
