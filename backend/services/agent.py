"""Agente del Research Chat: elige herramientas y arma contexto."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field

from openai.types.chat import ChatCompletionMessage

from backend.services.llm import _get_client
from backend.services.research_steps import (
    GatherResult,
    ResearchStepEvent,
    format_tool_step_label,
)
from backend.services.retrieval import retrieve
from backend.services.tools import (
    TOOL_DEFINITIONS,
    dedupe_hits,
    execute_tool,
)
from backend.services.types import SignalHit

AGENT_SYSTEM_PROMPT = """Sos el recolector de datos del Research Chat de X Scraper Terminal.

Tenés herramientas para:
- search_corpus: búsqueda semántica en el Corpus (narrativa, temas, contexto)
- get_recent_signals: Signals más recientes por fecha (como el Signal Feed)
- get_quotes: precios y variación % de cualquier Ticker (sin lista fija)
- get_watchlist_quotes: panel del carrusel Quote Strip (tickers activos en el Corpus)

Según la Query del Operator, llamá las herramientas necesarias antes de redactar la respuesta final.

Guía:
- Última noticia / noticias recientes / qué pasó hoy: get_recent_signals (con ticker y hours si aplica). Preferir sobre search_corpus para "última noticia de X".
- Preguntas sobre un Ticker o empresa (Intel, INTC, precio, qué pasó): get_quotes con el símbolo o nombre + get_recent_signals o search_corpus
- Comparar activos: get_quotes para todos los tickers mencionados + get_recent_signals o search_corpus si aporta contexto
- Solo narrativa o tema amplio (no reciente): search_corpus (usá ticker y since_hours si aplica)
- Mercado en general / watchlist: get_watchlist_quotes + get_recent_signals o search_corpus sobre el tema
- Cruce precio + noticias: siempre ambas fuentes cuando el Ticker sea relevante

Podés llamar varias herramientas en una o más rondas. Cuando tengas datos suficientes, respondé exactamente: LISTO"""


@dataclass
class AgentContext:
    """Contexto reunido por el agente para la síntesis final."""

    query: str
    hits: list[SignalHit] = field(default_factory=list)
    market_sections: list[str] = field(default_factory=list)
    corpus_sections: list[str] = field(default_factory=list)


def _append_assistant_message(
    messages: list[dict],
    message: ChatCompletionMessage,
) -> None:
    entry: dict = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        entry["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    messages.append(entry)


def _record_tool_result(
    context: AgentContext,
    tool_name: str,
    arguments: dict,
    result: str,
    hits: list[SignalHit],
) -> None:
    context.hits.extend(hits)

    if tool_name == "search_corpus":
        label = f"search_corpus(query={arguments.get('query')!r}"
        if arguments.get("ticker"):
            label += f", ticker={arguments.get('ticker')!r}"
        if arguments.get("since_hours"):
            label += f", since_hours={arguments.get('since_hours')}"
        label += ")"
        context.corpus_sections.append(f"### {label}\n{result}")

    elif tool_name == "get_recent_signals":
        parts: list[str] = []
        if arguments.get("ticker"):
            parts.append(f"ticker={arguments.get('ticker')!r}")
        if arguments.get("source_type"):
            parts.append(f"source_type={arguments.get('source_type')!r}")
        if arguments.get("hours"):
            parts.append(f"hours={arguments.get('hours')}")
        if arguments.get("limit"):
            parts.append(f"limit={arguments.get('limit')}")
        label = f"get_recent_signals({', '.join(parts)})"
        context.corpus_sections.append(f"### {label}\n{result}")

    elif tool_name in {"get_quotes", "get_watchlist_quotes"}:
        label = (
            "get_watchlist_quotes()"
            if tool_name == "get_watchlist_quotes"
            else f"get_quotes(symbols={arguments.get('symbols')})"
        )
        context.market_sections.append(f"### {label}\n{result}")


def gather_agent_context(query: str, max_turns: int = 6) -> AgentContext:
    """Ejecuta el loop de herramientas y devuelve contexto para sintetizar."""
    for item in iter_gather_agent_context(query, max_turns=max_turns):
        if isinstance(item, GatherResult):
            return AgentContext(
                query=query,
                hits=item.hits,
                market_sections=item.market_sections or [],
                corpus_sections=item.corpus_sections or [],
            )
    raise RuntimeError("iter_gather_agent_context no devolvió GatherResult")


def iter_gather_agent_context(
    query: str,
    max_turns: int = 6,
) -> Iterator[ResearchStepEvent | GatherResult]:
    """Loop legacy con emisión de pasos por tool."""
    context = AgentContext(query=query)
    messages: list[dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    client = _get_client()

    yield ResearchStepEvent(
        tool="agent",
        label="Investigando consulta…",
        status="running",
    )

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            break

        _append_assistant_message(messages, message)

        for tool_call in message.tool_calls:
            fn = tool_call.function
            try:
                arguments = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            label = format_tool_step_label(fn.name, arguments)
            yield ResearchStepEvent(
                tool=fn.name,
                label=label,
                status="running",
            )

            result, hits = execute_tool(fn.name, arguments)
            _record_tool_result(context, fn.name, arguments, result, hits)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

            yield ResearchStepEvent(
                tool=fn.name,
                label=label,
                status="done",
            )

    if not context.hits:
        yield ResearchStepEvent(
            tool="search_corpus",
            label="Búsqueda de respaldo en el Corpus",
            status="running",
        )
        fallback_hits = retrieve(query, limit=10)
        context.hits.extend(fallback_hits)
        if fallback_hits:
            from backend.services.tools import _format_hits_for_tool

            context.corpus_sections.append(
                "### search_corpus (fallback)\n"
                + _format_hits_for_tool(fallback_hits)
            )
        yield ResearchStepEvent(
            tool="search_corpus",
            label="Búsqueda de respaldo en el Corpus",
            status="done",
        )

    context.hits = dedupe_hits(context.hits)

    yield ResearchStepEvent(
        tool="agent",
        label="Investigando consulta…",
        status="done",
    )

    yield GatherResult(
        context=format_agent_context(context),
        hits=context.hits,
        market_sections=list(context.market_sections),
        corpus_sections=list(context.corpus_sections),
    )


def format_agent_context(context: AgentContext) -> str:
    """Arma el bloque de contexto para la síntesis final."""
    blocks: list[str] = []

    if context.market_sections:
        blocks.append(
            "## Market Data (delay ~15 min)\n\n" + "\n\n".join(context.market_sections)
        )

    if context.corpus_sections:
        blocks.append(
            "## Signals del Corpus\n\n" + "\n\n".join(context.corpus_sections)
        )
    elif context.hits:
        from backend.services.llm import build_context

        blocks.append("## Signals del Corpus\n\n" + build_context(context.hits))

    if not blocks:
        return "Sin datos de Market Data ni Signals en el Corpus."

    return "\n\n---\n\n".join(blocks)
