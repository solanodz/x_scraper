---
status: approved
approved_by: user
date: 2026-07-04
---

# Operator Terminal — Product & Platform Design

## 1. Visión

**X Scraper Terminal** es una **herramienta personal de research financiero** (Operator único). Convierte el ruido de X en **Signals** accionables, los cruza con **Market Data** y permite analizarlos con un **Research Chat** agente que **cita fuentes**.

**One-liner:** Terminal privada donde X es la fuente primaria de narrativa, filtrada y enriquecida con precios, analizable con un agente grounded.

**Usuario:** Un solo Operator (vos). No es SaaS en esta fase, pero el deploy es cloud y la Terminal queda protegida con login.

**Job diario:**

```
Login → Feed filtrado (SSE) → Signal Detail → Quote/gráfico → Research Chat → Citations
```

**Éxito (6 meses):** La abrís casi todos los días y reemplaza abrir X + múltiples tabs de noticias y gráficos sueltos.

---

## 2. Objetivos y anti-objetivos

### Objetivos

| # | Objetivo |
|---|----------|
| O1 | Corpus de X curado y filtrado (relevancia financiera US + LatAm) |
| O2 | Loop diario confiable en cloud (sin depender de la Mac local) |
| O3 | Research Chat que cruza narrativa (Corpus) + precios (Market Data) con Citations |
| O4 | Terminal accesible desde cualquier dispositivo, protegida con auth |
| O5 | Costo operativo bajo (~$0–25/mes en tiers iniciales) |

### Anti-objetivos (explícitos)

- Multi-tenant / billing / onboarding de usuarios externos
- Bloomberg completo, ejecución de órdenes, datos RT institucionales
- MCP público o API abierta (fase 2 opcional, no prioridad)
- Migrar a Qdrant u otro vector DB (pgvector alcanza para uso personal)
- Reemplazar FastAPI/Next.js por stack Supabase full (usamos Supabase como Store + Auth, no como backend)

---

## 3. Estado actual (baseline F1–F8)

| Feature | Qué hace |
|---------|----------|
| F1 | Docker Compose Postgres + pgvector (local) |
| F2 | Tabla `signals`, UPSERT por `id_str` |
| F3 | Worker Ingestion + embeddings OpenAI |
| F4 | Core Services: search, summarize, ask |
| F5 | API REST + SSE feed + Chat stream |
| F6 | Terminal 3 paneles (Next.js) |
| F7 | Quote Strip + Market Data (AV + yfinance) + TradingView |
| F8 | Research Chat agente (tools: corpus + quotes) |
| + | Signal Filter (keywords, cashtags, blocklist, trusted sources) |
| + | Chat markdown rendering |

**Deuda conocida:** ~43 Signals legacy sin embedding; junk histórico en DB; config de filtros solo en `.env`; deploy 100% local.

---

## 4. Arquitectura objetivo

```mermaid
flowchart TB
    subgraph vercel [Vercel]
        Web[Next.js Terminal]
        AuthUI[Supabase Auth UI]
    end

    subgraph railway [Railway]
        API[FastAPI API]
        Worker[Ingestion Worker]
    end

    subgraph supabase [Supabase]
        PG[(Postgres + pgvector)]
        Auth[Supabase Auth]
    end

    subgraph external [Externos]
        X[X / twscrape]
        OpenAI[OpenAI]
        Market[yfinance / Alpha Vantage]
        TV[TradingView embed]
    end

    Operator((Operator)) --> AuthUI
    AuthUI --> Auth
    Web -->|JWT| API
    Web -->|SSE / REST| API
    API --> PG
    API --> OpenAI
    API --> Market
    Worker --> X
    Worker --> PG
    Worker --> OpenAI
    Web --> TV
    Auth -.->|JWT verify| API
```

### Responsabilidades por servicio

| Servicio | Rol | Qué NO hace |
|----------|-----|-------------|
| **Vercel** | Host del Web (Terminal UI) | No corre Worker ni toca X directamente |
| **Railway — API** | FastAPI: Signals, Chat, Quotes, Ingest trigger | No sirve estáticos del frontend |
| **Railway — Worker** | Cron Ingestion (twscrape → Store + embeddings) | No expone HTTP público (opcional: solo health) |
| **Supabase — Postgres** | Store + Vector Index (`signals`, futuras tablas) | No ejecuta lógica de negocio |
| **Supabase — Auth** | Login del Operator, emisión de JWT | No reemplaza autorización fina en API (se valida JWT en FastAPI) |

### Secretos por ubicación

| Secreto | Dónde vive | Nunca en |
|---------|------------|----------|
| `X_COOKIES`, `ACCOUNTS_DB` | Railway Worker | Frontend, git |
| `OPENAI_API_KEY` | Railway API + Worker | Frontend |
| `DATABASE_URL` (service role) | Railway API + Worker | Frontend |
| `SUPABASE_ANON_KEY` | Vercel (público) | — |
| `SUPABASE_SERVICE_ROLE_KEY` | Railway API (si necesita bypass RLS) | Frontend |
| `SUPABASE_JWT_SECRET` | Railway API (validar tokens) | Frontend |
| `ALPHA_VANTAGE_API_KEY` | Railway API | Frontend |

---

## 5. Supabase (Store + Auth)

### 5.1 Postgres + pgvector

- Crear proyecto Supabase.
- Habilitar extensión `vector` en SQL Editor:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- Aplicar schema existente (`infra/store/init/001_extensions.sql`, `002_signals.sql`).
- Agregar índice HNSW cuando el corpus supere ~1k embeddings (opcional en F9, recomendado en F10):
  ```sql
  CREATE INDEX ON signals USING hnsw (embedding vector_cosine_ops);
  ```
- `DATABASE_URL`: usar **connection pooler** (Supabase → Settings → Database → URI mode `Transaction`) para API serverless-friendly si aplica; Worker puede usar conexión directa.

### 5.2 Migración local → Supabase

1. `pg_dump` del Docker local (solo datos `signals` si el volumen tiene historia útil).
2. O re-ingestar desde cero con Worker en Railway (más limpio si hay mucho junk).
3. Verificar `SELECT count(*) FROM signals WHERE embedding IS NOT NULL`.
4. Correr backfill de embeddings para legacy rows.

### 5.3 Supabase Auth

**Modo:** Email + password (o magic link) para un solo Operator. Registro deshabilitado en dashboard después de crear tu cuenta.

**Flujo:**

1. Operator abre Terminal en Vercel → pantalla `/login`.
2. Login vía `@supabase/supabase-js` → sesión con `access_token` (JWT).
3. Frontend adjunta `Authorization: Bearer <token>` a todas las llamadas al API en Railway.
4. FastAPI middleware valida JWT con `SUPABASE_JWT_SECRET` (o librería `PyJWT` + JWKS de Supabase).
5. Sin token válido → `401` en `/signals`, `/chat`, `/quotes`, `/ingest/refresh`.

**Worker:** No usa Auth de usuario. Conecta al Store con `DATABASE_URL` (service role / connection string con permisos de escritura). El Worker no es invocable desde el browser sin token admin (el endpoint `/ingest/refresh` en API sí requiere JWT).

**RLS (Row Level Security):** Fase opcional. Para Operator único, basta con JWT en API sin RLS en `signals` (tabla solo accesible vía service role desde API/Worker). Si se activa RLS más adelante: política `authenticated` read-only en `signals`; writes solo service role.

---

## 6. Railway (API + Worker)

### 6.1 Servicios

| Servicio Railway | Comando | Puerto |
|------------------|---------|--------|
| `xscraper-api` | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` | dinámico |
| `xscraper-worker` | `python -m scraper.worker --interval 1800` | — |

### 6.2 API

- CORS: permitir origen de Vercel (`https://<app>.vercel.app` + preview URLs).
- Health: `GET /health` sin auth (para Railway healthcheck).
- Resto de rutas: auth middleware.
- Variables: ver sección 8.

### 6.3 Worker

- Cron interno (`--interval 1800`) o Railway Cron Job que invoque `--once` cada 30 min.
- `X_COOKIES` rotadas manualmente cuando expiren (operación del Operator).
- `accounts.db` de twscrape: volumen persistente en Railway o rebuild en cada deploy (aceptable si solo hay una cuenta).

### 6.4 Networking

- API URL pública → `NEXT_PUBLIC_API_URL` en Vercel.
- Worker sin endpoint público.

---

## 7. Vercel (Web)

- Deploy desde `frontend/` (Next.js 16 App Router).
- Env:
  - `NEXT_PUBLIC_API_URL` → Railway API URL
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Rutas:
  - `/login` — auth gate
  - `/` — Terminal (protegida; redirect a `/login` si no hay sesión)
- Middleware Next.js: verificar sesión Supabase en rutas protegidas.

---

## 8. Variables de entorno (matriz)

### Vercel (`frontend/.env`)

```
NEXT_PUBLIC_API_URL=https://xscraper-api.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

### Railway API

```
DATABASE_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres
SUPABASE_JWT_SECRET=<jwt secret from Supabase settings>
OPENAI_API_KEY=sk-...
ALPHA_VANTAGE_API_KEY=...
WATCHLIST=SPY,QQQ,...
SIGNAL_FILTER=relevant
CORS_ORIGINS=https://<app>.vercel.app
```

### Railway Worker

```
DATABASE_URL=postgresql://postgres.[ref]:[pass]@db.[ref].supabase.co:5432/postgres
OPENAI_API_KEY=sk-...
X_COOKIES=auth_token=...; ct0=...
X_ACCOUNT_NAME=...
ACCOUNTS_DB=/data/accounts.db
SIGNAL_FILTER=relevant
WATCHLIST=...
```

---

## 9. Roadmap de implementación

### F9 — Platform: Supabase + Railway + Vercel + Auth

**Comportamiento visible:** Terminal en URL pública con login; Feed y Chat funcionan contra Store en Supabase; Worker ingesta en background.

**Tareas:**

1. Proyecto Supabase: extensión vector, schema `signals`, migración de datos (o re-ingesta).
2. Supabase Auth: crear usuario Operator; deshabilitar signups públicos.
3. Frontend: `@supabase/ssr` o `@supabase/supabase-js`, `/login`, middleware de sesión, bearer token en `api.ts`.
4. Backend: middleware JWT, CORS, health sin auth.
5. Railway: dos servicios (API + Worker) con env vars.
6. Vercel: deploy frontend con env vars.
7. Verificación: login → feed → chat → refresh ingest → nuevo signal en feed.

**Evidencia:** E2E manual documentado en `progress.md`; scripts de health check.

---

### F10 — Corpus quality

**Comportamiento visible:** Feed con menos ruido; RAG más profundo en artículos enlazados.

**Tareas:**

1. Backfill embeddings (`python -m scraper.worker --once` o script dedicado).
2. Script `purge` de Signals que no pasan `SIGNAL_FILTER`.
3. **Article Enrichment:** scrape cuerpo de artículo → ampliar `Embedding Document`.
4. Sources curadas: cuentas LatAm + ajuste `SEARCH_QUERIES` en `scraper/sources.py`.
5. Índice HNSW en Supabase si >1k embeddings.

---

### F11 — Operator UX

**Comportamiento visible:** Filtros editables desde UI; chat con memoria de sesión; resumen diario.

**Tareas:**

1. Panel de filtros (modo, ticker, keywords) — persiste en localStorage o tabla `operator_settings`.
2. Chat sessions (`chat_sessions`, `chat_messages` en Supabase).
3. Botón “Resumen del día” (watchlist + corpus 24h).
4. Indicador de última ingesta en TerminalHeader.

---

### F12 — Alertas personales (opcional)

- Badge o notificación cuando hay Signal nuevo sobre ticker de watchlist.
- Canal: Telegram bot o email (Resend). Fuera de F9–F11.

---

## 10. Modelo de datos (actual + futuro)

### Actual: `signals`

Ver `infra/store/init/002_signals.sql`. Sin cambios requeridos para F9.

### F11 (propuesto)

```sql
-- Config del Operator (filtros UI, preferencias)
CREATE TABLE operator_settings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id),
    settings   JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sesiones de Research Chat
CREATE TABLE chat_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id),
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    citations    JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 11. Seguridad

| Riesgo | Mitigación |
|--------|------------|
| API abierta sin auth | JWT middleware en F9 |
| `SERVICE_ROLE_KEY` en frontend | Solo anon key en Vercel |
| `X_COOKIES` leak | Solo Railway Worker env; rotar si se compromete |
| CORS abierto | Lista explícita de orígenes Vercel |
| Ingest abuse | `POST /ingest/refresh` requiere JWT |
| Supabase signups no deseados | Disable signups tras crear cuenta Operator |

---

## 12. Costos estimados

| Servicio | Tier | Costo |
|----------|------|-------|
| Supabase | Free → Pro si crece | $0–25/mes |
| Railway | Hobby | ~$5–10/mes |
| Vercel | Hobby | $0 |
| OpenAI | Pay-as-you-go | ~$1–5/mes (uso personal) |
| Alpha Vantage | Free | $0 |

---

## 13. Métricas de éxito (personales)

- ≥ 5 días/semana de uso real.
- < 20% de Signals en feed descartados mentalmente como irrelevantes (tras F10).
- Chat útil en primera pregunta ≥ 70% de las veces.
- Ingesta automática sin intervención manual ≥ 7 días seguidos.
- Tiempo de apertura de Terminal (login → feed visible) < 3 s.

---

## 14. Decisiones registradas

| Decisión | ADR |
|----------|-----|
| pgvector en Postgres (no Qdrant) | ADR-0002 |
| Supabase como Store + Auth | ADR-0003 |
| Railway API + Worker | ADR-0003 |
| Vercel Web | ADR-0003 |
| Producto = Operator personal (A) | Este spec |

---

## 15. Próximo paso

Tras aprobación de este spec → invocar **writing-plans** para generar el plan de implementación detallado de **F9 (Platform deploy + Auth)**.
