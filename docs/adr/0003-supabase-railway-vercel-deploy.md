---
status: accepted
---

# Supabase (Store + Auth) + Railway (API/Worker) + Vercel (Web)

El producto se define como **Operator Terminal personal** (un solo usuario), pero el deploy es cloud para uso diario sin depender de la máquina local. Se adopta Supabase para Postgres/pgvector y autenticación, Railway para procesos de larga duración (API FastAPI + Worker de Ingestion), y Vercel para el frontend Next.js.

## Considered Options

- **Todo local (Docker Compose)** — rechazado como estado objetivo: el Worker no corre 24/7 si la Mac está apagada; no hay acceso remoto.
- **Neon + Railway + Vercel (sin Auth)** — viable para DB; se descarta porque el usuario quiere Supabase Auth para proteger la Terminal en URL pública.
- **Supabase como backend completo (Edge Functions + Realtime)** — rechazado: duplica FastAPI y Core Services ya implementados; Supabase se usa solo como Store + Auth.
- **Supabase + Railway + Vercel** — elegido.

## Consequences

- `DATABASE_URL` apunta a Supabase en producción; Docker Compose local sigue para desarrollo.
- FastAPI valida JWT de Supabase Auth; el Worker usa connection string con permisos de escritura (service role / direct).
- `X_COOKIES` y `accounts.db` viven solo en Railway Worker (secretos de plataforma).
- Frontend en Vercel usa `NEXT_PUBLIC_SUPABASE_*` + `NEXT_PUBLIC_API_URL`.
- Nuevas tablas de auth (`operator_settings`, `chat_sessions`) referencian `auth.users` de Supabase en fases posteriores (F11).
- CORS en API restringido a dominios Vercel.

## Spec

Detalle completo en [`docs/superpowers/specs/2026-07-04-operator-terminal-design.md`](../superpowers/specs/2026-07-04-operator-terminal-design.md).
