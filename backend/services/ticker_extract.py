"""Extracción de Tickers desde la Query del Operator (estricta)."""

from __future__ import annotations

import os
import re

from backend.services.market_data import CURATED_EXTRA_SYMBOLS, CURATED_TICKER_LABELS
from backend.services.ticker_catalog import resolve_ticker_input

_CASHTAG_RE = re.compile(r"\$([A-Za-z]{1,6})\b")
_TOKEN_RE = re.compile(r"\b[A-Za-zÁÉÍÓÚáéíóúÑñ]{1,6}\b")
_SPLIT_RE = re.compile(
    r"\b(?:vs\.?|versus|compar[aá]|compare|contra|y|and|,|\||/)\b",
    re.IGNORECASE,
)
_COMPARE_HINT_RE = re.compile(
    r"\b(?:vs\.?|versus|compar[aá]|compare|contra)\b",
    re.IGNORECASE,
)
_VAGUE_FOLLOWUP_RE = re.compile(
    r"^\s*[¿¡]?\s*(?:y\s+)?(?:qu[eé]\s+)?(?:m[aá]s|más)\s*\??\s*$",
    re.IGNORECASE,
)
_THEMATIC_RE = re.compile(
    r"\b(?:"
    r"argentina|argentino|argentinos|latinoam[eé]rica|"
    r"inflaci[oó]n|econom[ií]a|macro|pol[ií]tica|pa[ií]s|"
    r"mercado\s+(?:hoy|global)|mundo|internacional|"
    r"qu[eé]\s+(?:est[aá]|pas[aá]|pasa|sucede|ocurre)|"
    r"what(?:'s|\s+is)\s+happening"
    r")\b",
    re.IGNORECASE,
)
_SKIP_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "como",
        "cómo",
        "compará",
        "compare",
        "con",
        "contra",
        "de",
        "del",
        "el",
        "en",
        "es",
        "esa",
        "ese",
        "eso",
        "esta",
        "está",
        "este",
        "esto",
        "hoy",
        "la",
        "las",
        "lo",
        "los",
        "ma",
        "mas",
        "más",
        "mi",
        "mis",
        "o",
        "or",
        "para",
        "por",
        "que",
        "qué",
        "se",
        "the",
        "un",
        "una",
        "vs",
        "versus",
        "y",
        "ya",
    }
)


def _max_parallel_tickers() -> int:
    raw = os.getenv("RESEARCH_PARALLEL_MAX_TICKERS", "4").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


def _normalize_token(token: str) -> str:
    return token.strip().lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")


def _resolve_query_token(token: str) -> str | None:
    """Resuelve un token de la Query solo con señales fuertes (no palabras sueltas)."""
    if not token:
        return None

    if _normalize_token(token) in _SKIP_TOKENS:
        return None

    return resolve_ticker_input(token)


def query_looks_vague_followup(query: str) -> bool:
    return bool(_VAGUE_FOLLOWUP_RE.match((query or "").strip()))


def query_looks_thematic(query: str) -> bool:
    """Query sobre tema/país/macro sin intención clara de Ticker."""
    text = (query or "").strip()
    if not text:
        return False
    if _CASHTAG_RE.search(text) or _COMPARE_HINT_RE.search(text):
        return False
    return bool(_THEMATIC_RE.search(text))


def should_use_parallel_research(query: str) -> bool:
    """Parallel Research solo si hay Tickers confiables y la Query no es temática."""
    if query_looks_thematic(query):
        return False
    return bool(extract_tickers_from_query(query))


def extract_tickers_from_query(query: str) -> list[str]:
    """Detecta Tickers en la Query: cashtags, nombres de empresa y símbolos explícitos."""
    text = (query or "").strip()
    if not text:
        return []

    max_tickers = _max_parallel_tickers()
    candidates: list[tuple[int, str]] = []
    lower_text = text.lower()

    for match in _CASHTAG_RE.finditer(text):
        symbol = resolve_ticker_input(match.group(1))
        if symbol:
            candidates.append((match.start(), symbol))

    for symbol, label in CURATED_TICKER_LABELS.items():
        label_lower = label.lower()
        label_match = re.search(rf"\b{re.escape(label_lower)}\b", lower_text)
        if label_match:
            candidates.append((label_match.start(), symbol))
            continue
        if len(symbol) >= 3:
            sym_match = re.search(rf"\b{re.escape(symbol)}\b", text)
            if sym_match:
                candidates.append((sym_match.start(), symbol))

    for extra in CURATED_EXTRA_SYMBOLS:
        if len(extra) >= 3:
            sym_match = re.search(rf"\b{re.escape(extra)}\b", text)
            if sym_match:
                candidates.append((sym_match.start(), extra))

    for part in _SPLIT_RE.split(text):
        part = part.strip()
        if not part:
            continue
        for match in _TOKEN_RE.finditer(part):
            token = match.group(0)
            symbol = _resolve_query_token(token)
            if symbol:
                candidates.append((match.start(), symbol))

    candidates.sort(key=lambda item: item[0])

    ordered: list[str] = []
    seen: set[str] = set()
    for _, symbol in candidates:
        if symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
        if len(ordered) >= max_tickers:
            break

    return ordered
