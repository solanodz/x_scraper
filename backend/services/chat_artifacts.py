"""Artefactos determinísticos del Research Chat (Chart cards, etc.)."""

from __future__ import annotations

import re
from typing import Any

from backend.services.fx import is_fx_currency_code
from backend.services.ticker_extract import extract_tickers_from_query
from backend.services.tools import build_price_chart_artifact, execute_tool

_PRICE_CHART_INTENT_RE = re.compile(
    r"\b(?:"
    r"gr[aá]fico|grafico|chart|sparkline|"
    r"evoluci[oó]n|evolucion|hist[oó]rico|historico|tendencia|"
    r"precio|cotizaci[oó]n|cotizacion|"
    r"1\s*mo|3\s*mo|6\s*mo|1\s*y|"
    r"30\s*d[ií]as?|90\s*d[ií]as?|60\s*d[ií]as?|"
    r"(?:[uú]ltim[oa]s?\s+)?(?:\d+\s*)?(?:d[ií]as?|semanas?|meses?|a[nñ]os?)"
    r")\b",
    re.IGNORECASE,
)

_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1\s*y\b|\b(?:un|1)\s*a[nñ]o\b", re.I), "1y"),
    (re.compile(r"\b6\s*mo\b|\b6\s*meses?\b", re.I), "6mo"),
    (re.compile(r"\b3\s*mo\b|\b3\s*meses?\b|\b90\s*d", re.I), "3mo"),
    (re.compile(r"\b1\s*mo\b|\b(?:un|1)\s*mes\b|\b30\s*d", re.I), "1mo"),
)


def query_wants_price_chart(query: str) -> bool:
    """True si la Query pide precio/evolución/ventana (candidato a Chart card)."""
    text = (query or "").strip()
    if not text:
        return False
    if not extract_tickers_from_query(text):
        return False
    return bool(_PRICE_CHART_INTENT_RE.search(text))


def period_from_query(query: str) -> str:
    text = query or ""
    for pattern, period in _PERIOD_PATTERNS:
        if pattern.search(text):
            return period
    return "1mo"


def ensure_price_chart_artifacts(
    query: str,
    existing: list[dict[str, Any]] | None = None,
    *,
    max_charts: int = 2,
) -> list[dict[str, Any]]:
    """
    Garantiza Chart cards cuando la Query lo pide.

    El agente a veces solo llama get_quotes (snapshot) y nunca get_price_history,
    así que el SSE no emitía event:artifact. Acá se completa de forma determinística.
    """
    artifacts = list(existing or [])
    if not query_wants_price_chart(query):
        return artifacts

    already = {
        str(a.get("symbol", "")).upper()
        for a in artifacts
        if a.get("type") == "price_chart" and a.get("symbol")
    }
    period = period_from_query(query)
    tickers = [
        t
        for t in extract_tickers_from_query(query)
        if not is_fx_currency_code(t) and t.upper() not in already
    ][: max(0, max_charts - len(already))]

    for symbol in tickers:
        raw, _hits = execute_tool(
            "get_price_history",
            {"symbol": symbol, "period": period},
        )
        artifact = build_price_chart_artifact(raw)
        if artifact:
            artifacts.append(artifact)

    return artifacts
