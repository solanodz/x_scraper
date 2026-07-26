# Progress

## Estado actual

Feed perf: SQL slice + keyset `before`, sin `body`, count diferido, page 20. Encima de SSE/scroll fix + F32/latency/skeletons (sin commit conjunto).

## Próximo paso

1. Commit + push + redeploy API/web.
2. Smoke: primer paint del Feed en <~1s (red local/prod).

## Notas

- 2026-07-25 — `list_signals` overfetch sobre idx `published_at` (no window full-table); FE no espera `/count`; scroll con `before`.
- Skeletons / Research history + latency + F32 + feed SSE fix en working tree.

## Roadmap

- Commit/redeploy
- Soak Paper Bot
