"""Research Chat agent con LangGraph (ReAct) — orquestación multi-paso."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, create_model

from backend.services.agent import AgentContext, format_agent_context
from backend.services.chat_history import prepare_chat_history
from backend.services.parallel_research import run_parallel_research
from backend.services.research_gather import (
    ResearchContext,
    finalize_research_context,
    parallel_research_enabled,
    record_tool_result,
)
from backend.services.research_steps import (
    GatherResult,
    ResearchStepEvent,
    format_tool_step_label,
)

RESEARCH_SYSTEM_PROMPT = """Sos el recolector de datos del Research Chat de X Scraper Terminal.

Tenés herramientas para:
- search_corpus: búsqueda semántica en el Corpus (narrativa, temas, contexto; filtros ticker, since_hours, source_type, min_relevance)
- get_recent_signals: Signals más recientes por fecha (como el Signal Feed)
- get_signal_detail: Article Body y metadata de un Signal concreto (lectura profunda)
- corpus_stats: agregación y tendencias narrativas del Corpus (volumen, fuentes, tickers)
- get_quotes: precios y variación % de cualquier Ticker (sin lista fija)
- get_watchlist_quotes: panel del carrusel Quote Strip (tickers activos en el Corpus)
- get_price_history: historial de precios vía yfinance (tendencias, rangos, retornos)

Según la Query del Operator, llamá las herramientas necesarias antes de redactar la respuesta final.
Si hay historial de conversación, usalo para follow-ups (comparaciones, aclaraciones, referencias a turnos previos).

Guía:
- Última noticia / noticias recientes / qué pasó hoy: get_recent_signals (con ticker y hours si aplica). Preferir sobre search_corpus para "última noticia de X".
- Preguntas sobre un Ticker o empresa (Intel, INTC, precio, qué pasó): get_quotes + get_recent_signals o search_corpus; get_price_history si piden tendencia o período
- Comparar activos: get_quotes para todos los tickers + get_recent_signals o search_corpus si aporta contexto
- Solo narrativa o tema amplio (no reciente): search_corpus (usá ticker y since_hours si aplica)
- Mercado en general / watchlist: get_watchlist_quotes + get_recent_signals o search_corpus sobre el tema
- Cruce precio + noticias: siempre ambas fuentes cuando el Ticker sea relevante
- Tendencias / volumen del Corpus: corpus_stats
- Profundizar en un Signal citado: get_signal_detail con id_str

Podés llamar varias herramientas en una o más rondas. Cuando tengas datos suficientes, respondé al Operator con un breve resumen de lo recolectado."""


def _research_model() -> str:
    return os.getenv("RESEARCH_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _research_max_turns() -> int:
    raw = os.getenv("RESEARCH_MAX_TURNS", "8").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 8


_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
}


def _python_type_from_json(prop_spec: dict[str, Any]) -> type:
    json_type = prop_spec.get("type", "string")
    if json_type == "array":
        items = prop_spec.get("items", {})
        item_type = _JSON_TYPE_MAP.get(items.get("type", "string"), Any)
        return list[item_type]
    return _JSON_TYPE_MAP.get(json_type, Any)


def _json_schema_to_pydantic(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    field_defs: dict[str, Any] = {}

    for prop_name, prop_spec in props.items():
        py_type = _python_type_from_json(prop_spec)
        desc = prop_spec.get("description", "")
        if prop_name in required:
            field_defs[prop_name] = (py_type, Field(description=desc))
        else:
            field_defs[prop_name] = (
                py_type | None,
                Field(default=None, description=desc),
            )

    model_name = "".join(part.capitalize() for part in name.split("_")) + "Args"
    if not field_defs:
        return create_model(model_name)
    return create_model(model_name, **field_defs)


def _load_tools_module():
    from backend.services import tools as tools_module

    return tools_module


def _build_langchain_tools(
    context: ResearchContext,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> list[StructuredTool]:
    tools_module = _load_tools_module()
    execute_tool = tools_module.execute_tool
    tool_definitions = tools_module.TOOL_DEFINITIONS

    langchain_tools: list[StructuredTool] = []

    for tool_def in tool_definitions:
        fn_spec = tool_def["function"]
        name = fn_spec["name"]
        description = fn_spec["description"]
        parameters = fn_spec.get("parameters", {"type": "object", "properties": {}})
        args_schema = _json_schema_to_pydantic(name, parameters)

        def _make_runner(tool_name: str):
            def _run(**kwargs: Any) -> str:
                clean_args = {k: v for k, v in kwargs.items() if v is not None}
                label = format_tool_step_label(tool_name, clean_args)
                if on_step:
                    on_step(
                        ResearchStepEvent(
                            tool=tool_name,
                            label=label,
                            status="running",
                        )
                    )
                result, hits = execute_tool(tool_name, clean_args)
                record_tool_result(context, tool_name, clean_args, result, hits)
                if on_step:
                    on_step(
                        ResearchStepEvent(
                            tool=tool_name,
                            label=label,
                            status="done",
                        )
                    )
                return result

            return _run

        langchain_tools.append(
            StructuredTool.from_function(
                func=_make_runner(name),
                name=name,
                description=description,
                args_schema=args_schema,
            )
        )

    return langchain_tools


def _history_to_messages(history: list[dict] | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for entry in prepare_chat_history(history):
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))
    return messages


def _resolve_parallel_tickers(
    query: str,
    history: list[dict] | None,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> list[str] | None:
    from backend.services.research_gather import resolve_parallel_tickers

    path, tickers, _plan = resolve_parallel_tickers(query, history)
    if path == "react" or not tickers:
        return None

    if path == "plan_then_parallel" and on_step:
        on_step(
            ResearchStepEvent(
                tool="research_plan",
                label="Resolviendo contexto del hilo…",
                status="running",
            )
        )
        on_step(
            ResearchStepEvent(
                tool="research_plan",
                label="Resolviendo contexto del hilo…",
                status="done",
            )
        )

    return tickers


def _run_parallel_gather(
    context: ResearchContext,
    query: str,
    history: list[dict] | None,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> bool:
    tickers = _resolve_parallel_tickers(query, history, on_step=on_step)
    if not tickers:
        return False

    run_parallel_research(context, query, tickers, on_step=on_step)
    finalize_research_context(context, query, on_step=on_step)
    return True


def iter_gather_research_context(
    query: str,
    history: list[dict] | None = None,
) -> Iterator[ResearchStepEvent | GatherResult]:
    """Ejecuta el agente LangGraph y emite pasos antes del contexto final."""
    context = ResearchContext(query=query)
    pending_steps: list[ResearchStepEvent] = []

    def on_step(step: ResearchStepEvent) -> None:
        pending_steps.append(step)

    if parallel_research_enabled():
        if _run_parallel_gather(context, query, history, on_step=on_step):
            while pending_steps:
                yield pending_steps.pop(0)
            yield GatherResult(
                context=format_research_context(context),
                hits=context.hits,
                market_sections=list(context.market_sections),
                corpus_sections=list(context.corpus_sections),
            )
            return

    tools = _build_langchain_tools(context, on_step=on_step)

    model = ChatOpenAI(model=_research_model(), temperature=0)
    agent = create_react_agent(model, tools)

    messages: list[BaseMessage] = [SystemMessage(content=RESEARCH_SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history))
    messages.append(HumanMessage(content=query))

    yield ResearchStepEvent(
        tool="agent",
        label="Investigando consulta…",
        status="running",
    )

    for _event in agent.stream(
        {"messages": messages},
        config={"recursion_limit": _research_max_turns() * 2 + 1},
        stream_mode="updates",
    ):
        while pending_steps:
            yield pending_steps.pop(0)

    while pending_steps:
        yield pending_steps.pop(0)

    yield ResearchStepEvent(
        tool="agent",
        label="Investigando consulta…",
        status="done",
    )

    finalize_research_context(context, query, on_step=on_step)
    while pending_steps:
        yield pending_steps.pop(0)

    yield GatherResult(
        context=format_research_context(context),
        hits=context.hits,
        market_sections=list(context.market_sections),
        corpus_sections=list(context.corpus_sections),
    )


def gather_research_context(
    query: str,
    history: list[dict] | None = None,
) -> ResearchContext:
    """Ejecuta el agente LangGraph ReAct y devuelve contexto para sintetizar."""
    context = ResearchContext(query=query)

    if parallel_research_enabled():
        if _run_parallel_gather(context, query, history):
            return context

    tools = _build_langchain_tools(context)

    model = ChatOpenAI(model=_research_model(), temperature=0)
    agent = create_react_agent(model, tools)

    messages: list[BaseMessage] = [SystemMessage(content=RESEARCH_SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history))
    messages.append(HumanMessage(content=query))

    agent.invoke(
        {"messages": messages},
        config={"recursion_limit": _research_max_turns() * 2 + 1},
    )

    finalize_research_context(context, query)
    return context


def format_research_context(context: ResearchContext) -> str:
    """Arma el bloque de contexto para la síntesis final."""
    return format_agent_context(
        AgentContext(
            query=context.query,
            hits=context.hits,
            market_sections=context.market_sections,
            corpus_sections=context.corpus_sections,
        )
    )
