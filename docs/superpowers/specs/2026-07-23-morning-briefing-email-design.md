# Morning Briefing Email (MVP)

Date: 2026-07-23  
Status: draft (awaiting Operator review)  
Related: ADR-0007 (Briefing), ADR-0014 (FX Quotes), F20–F23 / F46

## Problem

El Briefing on-demand en Research Chat ya entrega valor, pero no es un hábito diario. Sin un push a la mañana, el producto se siente como “demo de terminal”, no como ritual que el Operator pagaría por no armarse a mano.

## Goals

- Enviar **un email diario** con el Briefing del Ticker Watch + **FX solo USD/ARS** + links a Terminal/Research.
- Destinatario único (Operator local) vía `.env`.
- Reutilizar la generación existente del Briefing (misma calidad, Citations, delta).
- Envío vía **Resend**.

## Non-goals (MVP)

- Multi-usuario / preferencias de horario en UI
- Otras monedas FX (EUR, BRL, etc.) en el email
- PDF / attachments / rich newsletter design
- Push mobile / Slack
- Consejos de compra/venta o predicción de precios

## Decisions (confirmed)

| Tema | Decisión |
|------|----------|
| Destinatarios | **A** — un email fijo (`BRIEFING_EMAIL_TO`) |
| Contenido | **C** — Briefing + FX USD/ARS + CTA a Terminal/Research |
| Transporte | **A** — Resend API |
| Orquestación | CLI + cron externo (Railway/crontab) a ~08:00 `America/Argentina/Buenos_Aires` |
| FX en el mail | **Solo USD vs ARS** (oficial, blue; MEP/CCL/tarjeta si la fuente los expone). No Frankfurter / no pares EUR-USD etc. |

## User-visible behavior

Cada mañana (o al correr el comando a mano), el Operator recibe un mail:

1. **Asunto:** `Briefing · DD/MM` (opcional: sufijo si hay tickers en prioridad alta).
2. **Bloque Dólar (USD/ARS):** tabla o lista corta oficial / blue / MEP / CCL / tarjeta (los que respondan), con fuente + timestamp.
3. **Cuerpo Briefing:** mismo memo que el producto (delta vs Briefing anterior si existe, prioridad alta, otras novedades, temas cruzados, preguntas abiertas). Citations como links clickeables.
4. **CTA:** “Abrir Terminal” → `/terminal`, “Seguir en Research” → `/research`.
5. **Pie:** delay de Market Data · no es consejo de inversión.

El Briefing también se **persiste** como Chat Session (título `Briefing DD/MM/YYYY`) para follow-up en `/research`, igual que el botón on-demand.

## Architecture

```
cron (08:00 ART)
  → python -m backend.scripts.send_morning_briefing
      → Operator = LOCAL_OPERATOR_ID (o BRIEFING_OPERATOR_ID)
      → get_fx_quotes(scope=ars_usd)     # solo USD/ARS
      → generate briefing (reuse briefing.py synthesis, non-SSE helper)
      → persist Chat Session + assistant message (opcional pero deseable)
      → render markdown → HTML + text/plain
      → Resend API send
      → idempotency: skip if already sent today for this Operator
```

### Modules (proposed)

| Piece | Responsibility |
|-------|----------------|
| `backend/services/briefing_email.py` | Orquesta FX + Briefing + render + send + idempotency |
| `backend/services/email_resend.py` | Cliente fino Resend (`RESEND_API_KEY`, `RESEND_FROM`) |
| `backend/scripts/send_morning_briefing.py` | CLI: `--dry-run`, `--force` |
| Store | Tabla o key `briefing_email_log` (operator_id, date, message_id) **o** detectar sesión Briefing del día ya marcada como emailed |

### Config (`.env`)

```
RESEND_API_KEY=
RESEND_FROM=Briefing <onboarding@resend.dev>
BRIEFING_EMAIL_TO=you@example.com
BRIEFING_EMAIL_TZ=America/Argentina/Buenos_Aires
BRIEFING_EMAIL_ENABLED=true
# optional override; default LOCAL_OPERATOR_ID
BRIEFING_OPERATOR_ID=
FRONTEND_BASE_URL=https://…   # for CTA links (local: http://localhost:3000)
```

### Idempotency

- Clave: `(operator_id, calendar_date in BRIEFING_EMAIL_TZ)`.
- Si ya hay envío exitoso ese día → exit 0 sin reenviar, salvo `--force`.
- Fallo de Resend → no marcar como enviado; cron puede reintentar.

### FX constraint

- Llamar **únicamente** `get_fx_quotes(scope="ars_usd")` (dolarapi).
- No incluir `scope=pair` ni tasas Frankfurter en el email.
- Si dolarapi falla: bloque “Dólar: no disponible” honesto; el Briefing de Tickers igual se envía.

## Verification

1. `python -m backend.scripts.send_morning_briefing --dry-run` imprime asunto + HTML/text sin llamar Resend (o mock).
2. Con API key de test: un mail real llega a `BRIEFING_EMAIL_TO` con bloque USD/ARS y CTAs.
3. Segundo run el mismo día sin `--force` no reenvía.
4. FX en el cuerpo no menciona EUR/BRL/otras monedas.
5. Verify script con HTTP Resend + dolarapi mockeados.

## Open follow-ups (post-MVP)

- Botón “Enviar Briefing por email” en UI
- Multi-Operator + settings
- Dominio verificado en Resend (mejor deliverability)

## Approval

- [x] Destinatario único + Resend + contenido C  
- [x] FX **solo USD/ARS**  
- [ ] Operator review de este spec → luego plan F46
