"""Research Plan liviano para follow-ups conversacionales."""

from __future__ import annotations

import json
import os
import re

from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.services.chat_history import prepare_chat_history
from backend.services.ticker_catalog import resolve_ticker_input

RESEARCH_PLAN_SYSTEM_PROMPT = """Sos el planificador de contexto del Research Chat de X Scraper Terminal.

Tu única tarea es resolver follow-ups conversacionales: dado el historial del hilo y la consulta actual del Operator, identificá qué Tickers son relevantes para investigar ahora.

Reglas:
- Usá el historial para entender referencias implícitas ("¿y la otra?", "comparalo con Intel", "el mismo ticker").
- Devolvé solo Tickers con símbolo US canónico (ej. INTC, NVDA, AMD) que el Operator quiera comparar o analizar en mercado.
- NO inventes Tickers a partir de palabras sueltas del español ("mas", "esta", "que") ni de temas macro/país (Argentina, inflación).
- Si el hilo es temático (país, macro, noticias generales) sin Tickers claros, devolvé lista vacía.
- Máximo 4 Tickers, en orden de relevancia para la consulta actual.
- Si no hay Tickers claros, devolvé lista vacía.

Respondé únicamente con JSON válido, sin markdown ni texto adicional:
{"tickers": ["AMD"]}"""


@dataclass
class ResearchPlan:
    """Plan estructurado antes de Parallel Research."""

    tickers: list[str]
    raw_json: str | None = None


def _research_model() -> str:
    return os.getenv("RESEARCH_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _max_plan_tickers() -> int:
    raw = os.getenv("RESEARCH_PARALLEL_MAX_TICKERS", "4").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


def _parse_tickers_json(content: str) -> list[str]:
    text = (content or "").strip()
    if not text:
        return []

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

    raw_tickers = payload.get("tickers") if isinstance(payload, dict) else None
    if not isinstance(raw_tickers, list):
        return []

    max_tickers = _max_plan_tickers()
    ordered: list[str] = []
    seen: set[str] = set()
    for item in raw_tickers:
        symbol = resolve_ticker_input(str(item))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
        if len(ordered) >= max_tickers:
            break
    return ordered


def generate_research_plan(query: str, history: list[dict] | None) -> list[str]:
    """Resuelve Tickers relevantes en follow-ups vía LLM liviano."""
    cleaned_history = prepare_chat_history(history)
    if not cleaned_history:
        return []

    messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=RESEARCH_PLAN_SYSTEM_PROMPT)
    ]
    for entry in cleaned_history:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        else:
            messages.append(AIMessage(content=entry["content"]))
    messages.append(HumanMessage(content=query))

    model = ChatOpenAI(model=_research_model(), temperature=0)
    response = model.invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    return _parse_tickers_json(content)


def parse_research_plan_json(content: str) -> ResearchPlan:
    """Parsea JSON del Research Plan (para tests y fallback)."""
    return ResearchPlan(tickers=_parse_tickers_json(content), raw_json=content)


def build_research_plan(query: str, history: list[dict] | None) -> ResearchPlan:
    """Research Plan: tickers inline confiables o LLM con historial."""
    from backend.services.ticker_extract import (
        extract_tickers_from_query,
        should_use_parallel_research,
    )

    if should_use_parallel_research(query):
        return ResearchPlan(tickers=extract_tickers_from_query(query))

    if not prepare_chat_history(history):
        return ResearchPlan(tickers=[])

    tickers = generate_research_plan(query, history)
    return ResearchPlan(tickers=tickers)
