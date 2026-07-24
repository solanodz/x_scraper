"""Fast paths determinísticos para Research Chat."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.services.agent import AgentContext, format_agent_context
from backend.services.research_gather import ResearchContext, record_tool_result
from backend.services.research_steps import GatherResult, ResearchStepEvent
from backend.services.ticker_extract import (
    extract_tickers_from_query,
    query_looks_fx,
    query_looks_thematic,
)
from backend.services.tools import execute_tool

_QUOTE_SNAPSHOT_RE = re.compile(
    r"\b(?:precios?|cotizaci[oó]n(?:es)?|cotizacion(?:es)?|cotiza|"
    r"quote|cu[aá]nto\s+vale|c[oó]mo\s+est[aá]\s+de\s+precios?)\b",
    re.IGNORECASE,
)
_HISTORICAL_PRICE_RE = re.compile(
    r"\b(?:gr[aá]fico|grafico|chart|evoluci[oó]n|hist[oó]rico|"
    r"tendencia|30\s*d[ií]as?|90\s*d[ií]as?|1\s*mo|3\s*mo|"
    r"(?:[uú]ltim[oa]s?\s+)?(?:\d+\s*)?(?:d[ií]as?|semanas?|meses?|a[nñ]os?))\b",
    re.IGNORECASE,
)
_RECENT_SIGNALS_RE = re.compile(
    r"\b(?:[uú]ltima\s+noticia|noticias\s+recientes|se[nñ]ales\s+recientes|"
    r"qu[eé]\s+pas[oó]\s+hoy|qu[eé]\s+pas[oó]\s+con|novedades)\b",
    re.IGNORECASE,
)

_ANALYTICAL_RE = re.compile(
    r"\b(?:"
    r"analiz[aá]|an[aá]lisis|compar[aá]|compare|vs\.?|versus|"
    r"drivers?|implica|por\s+qu[eé]|qu[eé]\s+pas[oó]|tendencia|"
    r"rese[nñ]a|resumen\s+amplio|deep\s+dive|memo|"
    r"corpus|narrativa|sentimiento|riesgos?|"
    r"conviene|comprar|vender|hold|entrada|salir|"
    r"qu[eé]\s+hago|posicionarme|entrar[ií]as|comprar[ií]as|"
    r"m[aá]ximo|m[ií]nimo|respecto\s+a\s+su"
    r")\b",
    re.IGNORECASE,
)

# Narrativa / noticias sobre el dólar → Corpus, no cotización snapshot.
_FX_NARRATIVE_RE = re.compile(
    r"\b(?:"
    r"noticias?|noticia|"
    r"se\s+dijo|dijeron|comentaron|hablaron|dijeron|"
    r"qu[eé]\s+se\s+dijo|qu[eé]\s+hubo|hubo|"
    r"cobertura|medios|prensa|"
    r"esta\s+semana|estos\s+d[ií]as|"
    r"[uú]ltim[oa]s?\s+(?:\d+\s*)?(?:d[ií]as?|semanas?)|"
    r"resumen|analiz[aá]|an[aá]lisis|"
    r"qu[eé]\s+pas[oó]|pas[oó]\s+con|dijeron\s+sobre|"
    r"sobre\s+el\s+d[oó]lar|del\s+d[oó]lar\s+en"
    r")\b",
    re.IGNORECASE,
)

_FX_SNAPSHOT_HINT_RE = re.compile(
    r"\b(?:"
    r"precio|cotizaci[oó]n|cotizacion|cotiza|quote|"
    r"cu[aá]nto\s+(?:est[aá]|vale|sale)|a\s+cu[aá]nto|"
    r"bid|ask|compra|venta|"
    r"hoy|ahora|actual"
    r")\b",
    re.IGNORECASE,
)

# Orden: más específico primero (contado con liqui antes que "dólar").
_FX_LABEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcontado\s+con\s+liqui|\bccl\b", re.I), "ccl"),
    (re.compile(r"\bmep\b|\bbolsa\b", re.I), "mep"),
    (re.compile(r"\bblue\b", re.I), "blue"),
    (re.compile(r"\boficial\b", re.I), "oficial"),
    (re.compile(r"\btarjeta\b", re.I), "tarjeta"),
    (re.compile(r"\bcripto\b|\bcrypto\b", re.I), "cripto"),
    (re.compile(r"\bmayorista\b", re.I), "mayorista"),
)

_FX_DISPLAY: dict[str, str] = {
    "oficial": "oficial",
    "blue": "blue",
    "mep": "MEP",
    "ccl": "CCL",
    "tarjeta": "tarjeta",
    "cripto": "cripto",
    "mayorista": "mayorista",
}


def query_wants_fx_snapshot(query: str) -> bool:
    """True solo si la Query pide cotización FX, no noticias/narrativa del dólar."""
    text = (query or "").strip()
    if not text or not query_looks_fx(text):
        return False
    if _FX_NARRATIVE_RE.search(text):
        return False

    labels = detect_requested_fx_labels(text)
    if _FX_SNAPSHOT_HINT_RE.search(text) or _QUOTE_SNAPSHOT_RE.search(text):
        return True

    # Follow-ups / pedidos cortos de una casa: "y mep?", "dólar blue", "oficial".
    if labels and len(text) <= 64:
        return True

    # "dólar hoy" genérico sin palabras de noticia.
    if len(text) <= 40 and re.search(r"\bd[oó]lar", text, re.I):
        return True

    return False


def infer_response_style(query: str) -> str:
    """'concise' por defecto; 'memo' solo si la Query pide análisis."""
    text = (query or "").strip()
    if not text:
        return "concise"

    path = resolve_fast_path(text)
    if path is not None:
        return "concise"

    # Noticias / narrativa del dólar → memo grounded en Corpus.
    if query_looks_fx(text) and _FX_NARRATIVE_RE.search(text):
        return "memo"

    # Follow-ups cortos ("y el oficial?", "y MEP?") → siempre conciso.
    if len(text) <= 48 and not _ANALYTICAL_RE.search(text):
        return "concise"

    if _ANALYTICAL_RE.search(text) or _HISTORICAL_PRICE_RE.search(text):
        return "memo"

    if query_looks_thematic(text):
        return "memo"

    return "concise"


def detect_requested_fx_labels(query: str) -> list[str]:
    """Casas FX pedidas en la Query. Vacío = todas las disponibles."""
    text = (query or "").strip()
    found: list[str] = []
    for pattern, label in _FX_LABEL_PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)
    return found


def _format_fx_number(value: float | None) -> str:
    if value is None or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def format_fx_direct_answer(
    query: str,
    payload: dict[str, Any],
) -> str:
    """Respuesta corta y determinística: no deja al LLM elegir la casa equivocada."""
    if payload.get("error") and not payload.get("quotes"):
        return (
            f"No pude obtener cotizaciones USD/ARS: {payload.get('error')}. "
            "Fuente: dolarapi.com."
        )

    quotes = [
        q for q in (payload.get("quotes") or []) if isinstance(q, dict) and q.get("label")
    ]
    requested = detect_requested_fx_labels(query)
    if requested:
        wanted = set(requested)
        quotes = [q for q in quotes if str(q.get("label")).lower() in wanted]
        missing = [lab for lab in requested if lab not in {str(q.get("label")).lower() for q in quotes}]
        if missing and not quotes:
            return (
                f"No tengo cotización para {', '.join(missing)} en dolarapi ahora. "
                "Casas disponibles habituales: oficial, blue, MEP, CCL, tarjeta, cripto."
            )

    if not quotes:
        return "No hay cotizaciones USD/ARS en el contexto."

    lines: list[str] = []
    for q in quotes:
        label = str(q.get("label") or "").lower()
        title = _FX_DISPLAY.get(label, label)
        bid = _format_fx_number(q.get("bid") if isinstance(q.get("bid"), (int, float)) else None)
        ask = _format_fx_number(q.get("ask") if isinstance(q.get("ask"), (int, float)) else None)
        updated = q.get("updated_at") or payload.get("fetched_at") or "—"
        source = q.get("source") or payload.get("source") or "dolarapi.com"
        lines.append(
            f"**Dólar {title}** (USD/ARS)\n"
            f"- Bid: {bid} ARS\n"
            f"- Ask: {ask} ARS\n"
            f"Fuente: {source} · actualizado {updated}"
        )
    return "\n\n".join(lines)


def filter_fx_payload_for_query(query: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Recorta quotes a las casas pedidas (evita que el LLM mezcle blue/oficial)."""
    requested = detect_requested_fx_labels(query)
    if not requested or not isinstance(payload.get("quotes"), list):
        return payload
    filtered = {
        **payload,
        "quotes": [
            q
            for q in payload["quotes"]
            if isinstance(q, dict) and str(q.get("label", "")).lower() in set(requested)
        ],
        "requested_labels": requested,
    }
    return filtered


@dataclass(frozen=True)
class FastPath:
    kind: str
    tool: str
    arguments: dict
    label: str


def resolve_fast_path(query: str) -> FastPath | None:
    """Resuelve queries simples sin pasar por el agente ReAct completo."""
    text = (query or "").strip()
    if not text:
        return None

    if query_wants_fx_snapshot(text):
        requested = detect_requested_fx_labels(text)
        step_label = (
            f"Cotizaciones FX ({', '.join(requested)})"
            if requested
            else "Cotizaciones FX"
        )
        return FastPath(
            kind="fx",
            tool="get_fx_quotes",
            arguments={"scope": "ars_usd"},
            label=step_label,
        )

    if query_looks_thematic(text):
        return None

    tickers = extract_tickers_from_query(text)
    if not tickers:
        return None

    if len(tickers) == 1 and _RECENT_SIGNALS_RE.search(text):
        # Mixed intents (noticia + precio / "conviene comprar") must not take the
        # news-only shortcut — that starves Market Data and the LLM inventa "N/A".
        if (
            _QUOTE_SNAPSHOT_RE.search(text)
            or _ANALYTICAL_RE.search(text)
            or _HISTORICAL_PRICE_RE.search(text)
        ):
            return None
        ticker = tickers[0]
        return FastPath(
            kind="recent_signals",
            tool="get_recent_signals",
            arguments={"ticker": ticker, "hours": 168, "limit": 5},
            label=f"{ticker} · señales recientes",
        )

    if _QUOTE_SNAPSHOT_RE.search(text) and not _HISTORICAL_PRICE_RE.search(text):
        return FastPath(
            kind="quote",
            tool="get_quotes",
            arguments={"symbols": tickers},
            label=f"Cotizaciones ({', '.join(tickers)})",
        )

    return None


def build_fast_path_context(
    query: str,
    *,
    operator_id: str | None = None,
) -> GatherResult | None:
    path = resolve_fast_path(query)
    if path is None:
        return None

    context = ResearchContext(query=query)
    result, hits = execute_tool(
        path.tool,
        path.arguments,
        operator_id=operator_id,
    )

    direct_answer: str | None = None
    if path.kind == "fx":
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = {"error": "respuesta FX inválida", "quotes": []}
        if isinstance(payload, dict):
            payload = filter_fx_payload_for_query(query, payload)
            result = json.dumps(payload, ensure_ascii=False)
            direct_answer = format_fx_direct_answer(query, payload)

    record_tool_result(context, path.tool, path.arguments, result, hits)

    return GatherResult(
        context=format_agent_context(
            AgentContext(
                query=query,
                hits=context.hits,
                market_sections=context.market_sections,
                corpus_sections=context.corpus_sections,
                dossier_sections=context.dossier_sections,
                artifacts=context.artifacts,
            )
        ),
        hits=context.hits,
        market_sections=list(context.market_sections),
        corpus_sections=list(context.corpus_sections),
        artifacts=list(context.artifacts),
        direct_answer=direct_answer,
    )


def iter_fast_path_context(
    query: str,
    *,
    operator_id: str | None = None,
):
    path = resolve_fast_path(query)
    if path is None:
        return

    yield ResearchStepEvent(tool=path.tool, label=path.label, status="running")
    result = build_fast_path_context(query, operator_id=operator_id)
    yield ResearchStepEvent(tool=path.tool, label=path.label, status="done")
    if result is not None:
        yield result
