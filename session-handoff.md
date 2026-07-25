# Session handoff

## Verified now

- F52: `verify_f52` OK (crypto N/A, Finnhub equity mock, dossier attach, UI panel).

## Changed this session

- `backend/services/fundamentals.py` — Finnhub profile2+metric → yfinance
- Dossier gather/context overwrites bloque Fundamentals + `content.fundamentals`
- DossierPanel: FundamentalsSnapshotPanel
- CONTEXT + ADR-0009 actualizados

## Blockers

- Redeploy API + frontend. Operator debe Refresh Dossier para persistir snapshot nuevo.

## Next

F53 — Landing honest copy + empty/disabled states + Research chips Rápido/Research.

## Do not touch

- Root `package-lock.json`.
