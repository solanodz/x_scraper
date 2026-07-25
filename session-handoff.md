# Session handoff

## Verified now

- F49 en prod (smoke OK).
- Mark sanity guardrail en trader (Operator confirmó redeploy 2026-07-25).
- Historial paper limpio (trade @$28 borrado).

## Active mode: Paper Bot soak

No feature `in_progress`. No abrir F38/F50 hasta cerrar el soak con notas.

### Config sugerida (estable)

- Armed: **on**
- Symbols: BTC (o BTC+ETH si querés cobertura)
- Size USD: notional realista (ej. 50–200); **no es margen**
- Leverage: ignorar para PnL (display-only en paper)
- TP / SL: defaults o los que uses siempre (no retocar a mitad del soak)
- Donchian: dejar fijos period/interval

### Qué mirar cada día (~5 min)

En `/bot`:

1. Open positions: Price se mueve; PnL coherente con entry↔mark (~% del notional).
2. Closed: razón `tp` / `sl` / manual; exit cerca del TP/SL (no marks absurdos).
3. Events: errores de mark / venue.
4. Equity / Unreal: sin saltos imposibles.

### Log de dolores (copiá al cerrar el día)

```
Fecha:
Config (size/tp/sl/interval):
Trades del día (symbol/side/entry/exit/pnl/reason):
¿Algo raro? (mark, PnL, UI, señales, cooldown):
¿Qué cambiarías mañana?
```

### Criterio para terminar soak

Después de 2–3 días con al menos algunas entradas/salidas (o “no tradó” documentado):

→ Abrir **F50** con máximo 3 items del log (ej. leverage real, UI, strategy).

## Blockers

- Ninguno.

## Next

Operator corre soak; próxima sesión de código = F50 desde el log (o F38 si elige pivot).

## Do not touch

- Root `package-lock.json`.
- No Hyperliquid live / F38 en paralelo al soak.
