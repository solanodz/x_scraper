---
status: accepted
---

# Research Chat como superficie dedicada (`/research`)

La Terminal concentraba Signal Feed, Signal Detail y Research Chat en un solo workspace. El chat lateral competía con la lectura de Signals y dejaba poco espacio para el Article Body. Se decide sacar el Research Chat a una ruta propia y dejar la Terminal como superficie de observación: Feed | Detail.

## Considered Options

- **Mantener el chat lateral en Terminal** — rechazado: el Detail queda comprimido; el Operator no puede leer y chatear bien a la vez.
- **Chat en drawer/modal sobre Terminal** — rechazado: sigue siendo overlay; no da el mismo peso que Dossier/Chart Plan.
- **Research Chat en `/research` + Terminal Feed | Detail** — elegido: tres superficies claras (observar → preguntar → profundizar por Ticker).

## Decisiones asociadas

- **`/terminal`**: split horizontal Feed (izq.) | Signal Detail (der.); sin Research Chat.
- **Sin Signal seleccionado**: empty state en Detail (no auto-select).
- **Selección siempre en URL**: `/terminal?signal=<id>` (deep-link, refresh, back/forward).
- **`/research`**: mismo chrome que Terminal/Dossier (Header + Quote Strip) + Research Chat a full height.
- **Nav**: Terminal · Research · Dossier.
- **Citation** en Research → navega a `/terminal?signal=<id>` (un solo lugar canónico para leer Signals).

## Consequences

- `frontend/src/app/research/page.tsx` nueva; `terminal/page.tsx` deja de montar `ResearchChat`.
- Citations dejan de seleccionar un panel hermano; cruzan superficies por navegación.
- Landing/mockups que muestren chat al lado del Feed quedan desactualizados hasta alinearlos.
