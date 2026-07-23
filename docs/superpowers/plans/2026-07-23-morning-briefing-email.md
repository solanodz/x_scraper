# Morning Briefing Email (F46) Implementation Plan

> **For agentic workers:** Implement task-by-task. Do NOT commit unless the user asks. Use CONTEXT.md language (Briefing, Operator, Ticker Watch, FX Quote, Terminal, Research Chat).

**Goal:** Daily email (CLI + cron) with Briefing + FX USD/ARS only + CTAs, via Resend, single `.env` recipient.

**Architecture:** `send_morning_briefing` CLI → `briefing_email.run(...)` gathers FX (`scope=ars_usd` only), generates Briefing text (reuse `briefing.py` / `stream_briefing_answer` collected to string), persists Chat Session like on-demand Briefing, renders HTML+text, sends via Resend, logs idempotency by Operator+date (ART timezone).

**Tech Stack:** FastAPI backend services, Resend HTTP API, existing Briefing + `get_fx_quotes`, Postgres Store.

**Spec:** `docs/superpowers/specs/2026-07-23-morning-briefing-email-design.md`

## Global Constraints

- FX in email: **only USD/ARS** via `get_fx_quotes(scope="ars_usd")` — never Frankfurter/other pairs
- No buy/sell advice in copy
- Single recipient: `BRIEFING_EMAIL_TO`
- Idempotent per calendar day in `BRIEFING_EMAIL_TZ` (default `America/Argentina/Buenos_Aires`) unless `--force`
- Do not invent Resend SDK if urllib/httpx already used elsewhere; prefer stdlib urllib or existing HTTP style in `fx.py`

---

## File map

| File | Role |
|------|------|
| `backend/services/email_resend.py` | Resend send helper |
| `backend/services/briefing_email_render.py` | markdown Briefing + FX block → subject, text, HTML |
| `backend/services/briefing_email.py` | Orchestrator: idempotency, FX, briefing body, persist, send |
| `backend/scripts/send_morning_briefing.py` | CLI `--dry-run` `--force` |
| `backend/scripts/verify_f46_briefing_email.py` | Mocks Resend + FX + briefing |
| `infra/store/init/013_briefing_email_log.sql` + supabase twin | Idempotency log |
| `.env.example` | New vars |
| `CONTEXT.md` | Morning Briefing Email term |
| `feature_list.json` / `progress.md` | F46 evidence |

---

## Task 1 — Resend client + render

- [ ] `email_resend.py`: `send_email(to, subject, html, text) -> message_id`; reads `RESEND_API_KEY`, `RESEND_FROM`; raises clear errors
- [ ] `briefing_email_render.py`: build FX section (ARS quotes only), append Briefing markdown, CTAs from `FRONTEND_BASE_URL`, footer disclaimer; subject `Briefing · DD/MM`
- [ ] Unit-friendly pure functions (no network)

## Task 2 — Orchestrator + CLI + idempotency

- [ ] Migration `briefing_email_log (operator_id, sent_on date, resend_id, created_at)` unique (operator_id, sent_on)
- [ ] `briefing_email.py`: `run_morning_briefing(*, dry_run, force) -> result dict`
  - operator from `BRIEFING_OPERATOR_ID` or `operator_id_from_user(None)`
  - skip if log row exists today unless force
  - FX ars_usd only
  - Collect briefing answer from existing briefing stream/synthesis for that operator
  - Persist session via chat_repo (mirror `/chat/briefing` title pattern)
  - Render + send (skip send if dry_run)
  - Insert log on success
- [ ] CLI `send_morning_briefing.py`
- [ ] `verify_f46_briefing_email.py` with mocks — assert no EUR in body; dry-run; idempotent skip

## Task 3 — Docs + env

- [ ] `.env.example` vars from spec
- [ ] CONTEXT.md short term **Morning Briefing Email**
- [ ] Mark F46 evidence; leave passing only if verify OK

## Verification

```bash
.venv/bin/python -m backend.scripts.verify_f46_briefing_email
.venv/bin/python -m backend.scripts.send_morning_briefing --dry-run
```
