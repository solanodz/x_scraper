# Supabase — X Scraper Terminal

## Schema setup

1. Open your Supabase project → **SQL Editor**.
2. Paste and run the contents of `migrations/001_init.sql`.
3. Verify the `vector` extension is enabled:

   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

   You should see one row. If not, enable it under **Database → Extensions** and re-run the migration.

## Connection strings

| Service | URI | Notes |
|---------|-----|-------|
| **API** (FastAPI) | **Transaction pooler** (puerto **6543**) | Preferir siempre en local y Railway. Soporta IPv4. |
| **Worker** (Ingestion) | **Session pooler** (puerto **5432**) o direct | Conexiones largas; si direct falla, usar session pooler. |

Copiá las URIs en **Project Settings → Database → Connect**.

### ⚠️ No uses `db.<ref>.supabase.co` en local (IPv6)

El host directo `db.<project-ref>.supabase.co` en muchos proyectos **solo resuelve por IPv6**. Si tu red/Mac no tiene IPv6 funcional, verás:

```
psycopg.OperationalError: failed to resolve host 'db.<ref>.supabase.co'
```

**Solución:** usá el **Connection pooler** del dashboard (no el host `db.`):

```env
# API — Transaction mode, puerto 6543
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres

# Worker — Session mode, puerto 5432 (mismo host pooler, distinto modo)
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Reemplazá `<ref>`, `<password>` y `<region>` con los valores del dashboard (Connect → ORMs / URI).

### Verificar conectividad

```bash
# Debe listar el host pooler (IPv4), no solo IPv6
host aws-0-<region>.pooler.supabase.com

# Probar conexión (con tu DATABASE_URL real)
.venv/bin/python -c "from backend.app.db import connect; connect().__enter__(); print('OK')"
```

## Qué vive en Supabase

| Dato | Tabla / servicio | Alcance | Notas |
|------|------------------|---------|-------|
| **Login** | `auth.users` | Por usuario | Ya configurado |
| **Corpus (Signals)** | `signals` | Compartido | Noticias filtradas (`SIGNAL_FILTER=relevant`); embeddings para RAG |
| **Watchlist, filtros UI** | `operator_settings` | Por usuario | Migración `002_operator_data.sql` — reemplaza `.env` WATCHLIST a futuro |
| **Research Chat** | `chat_sessions`, `chat_messages` | Por usuario | Historial + Citations en JSONB |
| **Quotes (precios)** | — (no persistir) | Efímero | Finnhub + fallback AV; caché en memoria 15 min |

Los **Tickers en la Quote Strip** son Market Data en vivo (o ~15m delayed); se consultan on-demand. Lo que sí persistís del Operator es la **watchlist** en `operator_settings.settings` (ej. `{"watchlist": ["SPY","NVDA",...]}`).

## Data migration (local → Supabase)

Choose one path after applying `migrations/001_init.sql` on Supabase.

### Option A: pg_dump (preserve existing Corpus)

Export only `signals` data from the local Docker Store:

```bash
docker exec xscraper_store pg_dump -U xscraper -d xscraper -t signals --data-only > signals_data.sql
```

Import in Supabase → **SQL Editor** (paste `signals_data.sql`). Fix schema/name conflicts if the dump includes `COPY` headers incompatible with Supabase roles.

Use this when the local Corpus is valuable and you want to avoid re-scraping.

### Option B: Re-ingest (recommended for noisy history)

Skip the dump. After Railway Worker is deployed, run a one-off ingest:

```bash
python -m scraper.worker --once
```

On Railway: open the Worker service shell or temporarily set the start command to `python -m scraper.worker --once`, deploy, then restore `--interval 1800`.

Cleaner when local data has junk or legacy rows without embeddings.

### Verify counts

Run in Supabase SQL Editor:

```sql
SELECT count(*) FROM signals;
SELECT count(embedding) FROM signals;
```

Expect `count(embedding)` to grow after the first successful Worker run with `OPENAI_API_KEY` set. Legacy rows without embeddings backfill on subsequent ingests.

## Auth setup (dashboard)

1. **Authentication → Providers** → Email enabled.
2. **Authentication → Users** → create your Operator account.
3. (Before public deploy) **Authentication → Settings** → disable email signups.
4. **Settings → API → JWT Settings** → copy **JWT Secret** → `SUPABASE_JWT_SECRET` (fallback HS256; proyectos nuevos usan **ES256** vía JWKS automático).
5. **`SUPABASE_URL`** o `NEXT_PUBLIC_SUPABASE_URL` en `.env` raíz — el API usa JWKS en `{url}/auth/v1/.well-known/jwks.json`.

## Desarrollo local (sin Railway/Vercel)

Dos perfiles. Railway queda para cuando el loop local funcione.

### Perfil 1 — Híbrido (recomendado mientras iterás)

| Pieza | Dónde |
|-------|--------|
| Store | Docker local (`DATABASE_URL` puerto 5433) |
| Auth UI | Supabase (login en `/login`) |
| API auth | `AUTH_ENABLED=false` en `.env` raíz |

El frontend puede tener login Supabase; el API **no exige JWT** todavía. Tus Signals siguen en Postgres local.

**`.env` raíz:** `AUTH_ENABLED=false`  
**`frontend/.env.local`:** `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (o `ANON_KEY`)

```bash
docker compose up -d
uvicorn backend.app.main:app --reload --port 8000
cd frontend && npm run dev
```

Abrí http://localhost:3000 → login con tu usuario Supabase → Terminal contra DB local.

### Perfil 2 — Store en Supabase (pre-producción local)

| Pieza | Dónde |
|-------|--------|
| Store | Supabase Postgres vía **pooler** (ver sección IPv6 arriba) |
| Auth | Supabase + `AUTH_ENABLED=true` |
| API | Valida JWT con `SUPABASE_JWT_SECRET` |

**`.env` raíz (además de lo habitual):**

```env
# Transaction pooler — NO db.<ref>.supabase.co
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
AUTH_ENABLED=true
SUPABASE_JWT_SECRET=<JWT Secret del dashboard>
```

**Migraciones en orden:**

1. `migrations/001_init.sql` — `signals` + pgvector
2. `migrations/002_operator_data.sql` — settings, chat (RLS por usuario)
3. `migrations/003_signals_multisource.sql` — columnas multi-fuente en `signals` (ADR-0004; additive, sin pérdida de datos)

Corré ingesta para poblar Supabase:

```bash
# Worker: usar session pooler (5432) en DATABASE_URL si transaction pooler da problemas en ingesta larga
python -m scraper.worker --once
```

Verificá en SQL Editor: `SELECT count(*) FROM signals;`

## Roadmap local → Supabase completo

Orden recomendado (sin deploy todavía):

1. **Estabilizar Perfil 1** — login OK + `DATABASE_URL` local + Terminal carga (estado actual).
2. **Conectar Store a Supabase** — pooler URI + `pg_dump` de signals locales (411 filas) o re-ingesta.
3. **Activar auth en API** — `AUTH_ENABLED=true`, reiniciar uvicorn.
4. **Correr `002_operator_data.sql`** — tablas de preferencias y chat.
5. **F10** — purgar ruido del Corpus, backfill embeddings, article enrichment.
6. **F11** — persistir watchlist/filtros en `operator_settings`; guardar chats en `chat_messages`.
7. **Deploy** (Railway + Vercel) cuando el loop local con Supabase Store funcione.

### Variables frontend

Next.js **solo lee** `frontend/.env.local` (no el `.env` de la raíz). Copiá:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` **o** `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Tras cambiar `.env.local`, reiniciá `npm run dev`.

### HTTP 431 en el browser

Si ves **HTTP ERROR 431** (sobre todo en Brave tras varios intentos de login):

1. **Borrá cookies** de `localhost:3000`: DevTools → Application → Cookies → eliminar todas las `sb-*`.
2. O abrí una **ventana de incógnito**.
3. Reiniciá `npm run dev` (el script ya sube el límite de headers para cookies de Supabase).
