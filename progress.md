# Progress

## Estado actual

**F46 `passing`.** Morning Briefing Email (Resend + FX solo USD/ARS + CLI + idempotencia).

**Research Chat v2 F39–F45 `passing`.**

## Próximo paso

1. Configurar `.env`: `RESEND_API_KEY`, `RESEND_FROM`, `BRIEFING_EMAIL_TO`, `BRIEFING_EMAIL_ENABLED=true`
2. Probar: `.venv/bin/python -m backend.scripts.send_morning_briefing --dry-run`
3. Cron ~08:00 ART sin `--dry-run`
4. F38 enrichment (aparte)

## Notas

- 2026-07-23 — Fix HTML Briefing Email: parser línea-a-línea (##/###/listas), FX como tabla, CTAs a `myterm.solanodz.com`. Reenviado con `--force`.
- 2026-07-23 — F46: alineé orchestrator a API Task1 (`fx_payload` / tuple); `verify_f46_briefing_email OK`; migración `013_briefing_email_log` aplicada.
- 2026-07-23 — Subagents: [Resend+render](ba6b979d-7ce0-419b-a392-eaf84b38be50) + [Orchestrator](69bf3c60-61b5-42aa-9eb2-e5a043c85070)

## Roadmap Briefing Email

- **F46** Morning Briefing Email (`passing`)

## Roadmap lectura Terminal

- **F36** / **F37** `passing` · **F38** `pending`
