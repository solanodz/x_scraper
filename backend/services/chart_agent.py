"""Chart Agent: ReAct acotado para recolectar contexto del Chart Plan."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from backend.services.chart_plan import ChartPlanGather, chart_agent_max_turns
from backend.services.research_agent import (
    _json_schema_to_pydantic,
    _load_tools_module,
    _research_model,
)
from backend.services.research_steps import ResearchStepEvent, format_tool_step_label
from backend.services.tools import execute_tool

CHART_AGENT_TOOL_NAMES = frozenset(
    {
        "get_quotes",
        "get_price_history",
        "get_recent_signals",
        "search_corpus",
        "corpus_stats",
    }
)

CHART_AGENT_COLLECTOR_PROMPT = """Sos el recolector de datos del Chart Plan de X Scraper Terminal.

Objetivo: reunir contexto objetivo para planificar vistas de gráficos (TradingView, sentimiento, timeline de Signals) y scripts Pine opcionales.

Tenés herramientas para:
- get_latest_dossier_summary: excerpt del último Dossier persistido + stats de sentimiento
- get_quotes: precio y variación % del Ticker
- get_price_history: historial OHLC (1mo, 3mo, 6mo, 1y) vía yfinance
- get_recent_signals: Signals recientes del Corpus por fecha
- search_corpus: búsqueda semántica en el Corpus
- corpus_stats: agregación narrativa del Corpus

Reglas:
- **No** des recomendaciones de compra/venta ni predicciones de precio.
- No inventes números: las stats determinísticas ya están en el Dossier; usá tools para complementar.
- Priorizá cruzar precio + narrativa del Corpus + sentimiento cuando sea relevante para elegir timeframes y vistas.
- Llamá las herramientas necesarias en una o más rondas acotadas.
- Cuando tengas datos suficientes, respondé con un breve resumen de lo recolectado para el plan de gráficos."""


@dataclass
class ChartAgentContext:
    """Contexto reunido por el Chart Agent."""

    symbol: str
    user_id: str
    dossier_excerpt: str
    sentiment_stats: dict[str, Any] = field(default_factory=dict)
    market_sections: list[str] = field(default_factory=list)
    corpus_sections: list[str] = field(default_factory=list)
    dossier_sections: list[str] = field(default_factory=list)


def _record_chart_tool_result(
    context: ChartAgentContext,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
) -> None:
    if tool_name == "get_latest_dossier_summary":
        context.dossier_sections.append(f"### get_latest_dossier_summary\n{result}")
        return

    if tool_name in {"get_quotes", "get_price_history"}:
        label_parts = []
        if arguments.get("symbol"):
            label_parts.append(f"symbol={arguments.get('symbol')!r}")
        if arguments.get("symbols"):
            label_parts.append(f"symbols={arguments.get('symbols')}")
        if arguments.get("period"):
            label_parts.append(f"period={arguments.get('period')!r}")
        label = f"{tool_name}({', '.join(label_parts) or ''})"
        context.market_sections.append(f"### {label}\n{result}")
        return

    label = format_tool_step_label(tool_name, arguments)
    context.corpus_sections.append(f"### {label}\n{result}")


def _format_dossier_summary(gather: ChartPlanGather) -> str:
    blocks = gather.dossier_content.get("blocks") or {}
    excerpt_parts: list[str] = []
    if isinstance(blocks, dict):
        for key in ("panorama_mercado", "narrativa_7d", "sentimiento", "lectura_integrada"):
            text = blocks.get(key, "")
            if isinstance(text, str) and text.strip():
                excerpt_parts.append(f"## {key}\n{text.strip()[:800]}")
    payload = {
        "symbol": gather.symbol,
        "dossier_version_id": gather.dossier_version_id,
        "blocks_excerpt": "\n\n".join(excerpt_parts) or "(sin bloques)",
        "sentiment_stats": gather.sentiment_stats,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_chart_langchain_tools(
    context: ChartAgentContext,
    gather: ChartPlanGather,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> list[StructuredTool]:
    tools_module = _load_tools_module()
    tool_definitions = tools_module.TOOL_DEFINITIONS
    langchain_tools: list[StructuredTool] = []

    def _make_dossier_summary_runner():
        def _run() -> str:
            label = "Resumen del Dossier"
            if on_step:
                on_step(
                    ResearchStepEvent(
                        tool="get_latest_dossier_summary",
                        label=label,
                        status="running",
                    )
                )
            result = _format_dossier_summary(gather)
            _record_chart_tool_result(
                context,
                "get_latest_dossier_summary",
                {},
                result,
            )
            if on_step:
                on_step(
                    ResearchStepEvent(
                        tool="get_latest_dossier_summary",
                        label=label,
                        status="done",
                    )
                )
            return result

        return _run

    langchain_tools.append(
        StructuredTool.from_function(
            func=_make_dossier_summary_runner(),
            name="get_latest_dossier_summary",
            description=(
                "Devuelve excerpt de bloques del último Dossier persistido "
                "y sentiment_stats determinísticas para el Ticker."
            ),
        )
    )

    for tool_def in tool_definitions:
        fn_spec = tool_def["function"]
        name = fn_spec["name"]
        if name not in CHART_AGENT_TOOL_NAMES:
            continue
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
                result, _hits = execute_tool(tool_name, clean_args)
                _record_chart_tool_result(context, tool_name, clean_args, result)
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


def format_chart_agent_context(context: ChartAgentContext) -> str:
    """Arma notas de recolección para la síntesis del Chart Plan."""
    sections: list[str] = [
        f"# Recolección Chart Agent — {context.symbol}",
    ]
    if context.dossier_sections:
        sections.append("## Dossier")
        sections.extend(context.dossier_sections)
    if context.market_sections:
        sections.append("## Market Data")
        sections.extend(context.market_sections)
    if context.corpus_sections:
        sections.append("## Corpus")
        sections.extend(context.corpus_sections)
    return "\n\n".join(sections)


def iter_chart_plan_stream(
    user_id: str,
    symbol: str,
    *,
    gather: ChartPlanGather | None = None,
) -> Iterator[ResearchStepEvent | str]:
    """Ejecuta el Chart Agent ReAct y emite pasos; al final devuelve notas (str)."""
    from backend.services.chart_plan import gather_chart_context

    if gather is None:
        gather = gather_chart_context(user_id=user_id, symbol=symbol)

    context = ChartAgentContext(
        symbol=gather.symbol,
        user_id=user_id,
        dossier_excerpt=_format_dossier_summary(gather),
        sentiment_stats=gather.sentiment_stats,
    )
    pending_steps: list[ResearchStepEvent] = []

    def on_step(step: ResearchStepEvent) -> None:
        pending_steps.append(step)

    tools = _build_chart_langchain_tools(context, gather, on_step=on_step)
    model = ChatOpenAI(model=_research_model(), temperature=0)
    agent = create_react_agent(model, tools)

    query = (
        f"Planificá vistas de gráficos para {gather.symbol}. "
        "Recolectá precio, historial, narrativa reciente del Corpus y el Dossier. "
        "No des recomendaciones de trading."
    )
    messages: list[BaseMessage] = [SystemMessage(content=CHART_AGENT_COLLECTOR_PROMPT)]
    messages.append(HumanMessage(content=query))

    yield ResearchStepEvent(
        tool="chart_agent",
        label=f"Chart Agent analizando {gather.symbol}…",
        status="running",
    )

    max_turns = chart_agent_max_turns()
    for _event in agent.stream(
        {"messages": messages},
        config={"recursion_limit": max_turns * 2 + 1},
        stream_mode="updates",
    ):
        while pending_steps:
            yield pending_steps.pop(0)

    while pending_steps:
        yield pending_steps.pop(0)

    yield ResearchStepEvent(
        tool="chart_agent",
        label=f"Chart Agent analizando {gather.symbol}…",
        status="done",
    )

    yield format_chart_agent_context(context)
