# Progress

## Estado actual

**Listo para prod.** Research Chat v2 (F39–F45), Morning Briefing Email (F46), lectura Terminal (F36–F37), Chart Plan F35, landing + `/terminal` + `/research`.

## Próximo paso

1. Cron Morning Briefing ~08:00 ART en Railway (sin `--dry-run`)
2. Confirmar env prod: `RESEND_*`, `BRIEFING_EMAIL_*`, `FRONTEND_BASE_URL=https://myterm.solanodz.com`, `CHART_PARALLEL_ENABLED` si se quiere on
3. F38 Article Body enrichment (aparte)

## Notas

- 2026-07-23 — Push a prod: merge main (F35) + landing/Research/Briefing Email.
- 2026-07-23 — Fix HTML Briefing Email: parser línea-a-línea, FX tabla, CTAs a `myterm.solanodz.com`.
- 2026-07-23 — F46 passing (`verify_f46_briefing_email OK`); migración `013_briefing_email_log`.
- 2026-07-20 — F35 passing (Parallel Chart Gather, ADR-0012).

## Roadmap Briefing Email

- **F46** Morning Briefing Email (`passing`)

## Roadmap lectura Terminal

- **F36** / **F37** `passing` · **F38** `pending`

## Roadmap Chart Plan (ADR-0010 / ADR-0011 / ADR-0012)

- **F33** / **F34** / **F35** `passing`
