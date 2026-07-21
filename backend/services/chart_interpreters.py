"""Chart Interpreters: lecturas LLM acotadas por dimensión (ADR-0012)."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from dotenv import load_dotenv

from backend.services.llm import _get_client, _normalize_chart_image
from backend.services.research_steps import ResearchStepEvent

_VALID_STANCES = frozenset({"alcista", "bajista", "neutral"})

_INTERPRETER_SYSTEM = """Sos un Chart Interpreter del X Scraper Terminal.
Analizás UNA dimensión del Chart Plan. Respondé SOLO JSON válido con este schema:
{
  "summary": "string breve en español",
  "stance": "alcista" | "bajista" | "neutral" | null,
  "findings": ["hallazgo concreto", ...],
  "conflicts": ["tensión o contradicción", ...],
  "data_gaps": ["dato faltante o incierta", ...]
}
Reglas:
- No des recomendaciones de compra/venta ni predicciones de precio.
- Anclá afirmaciones a los datos provistos; si falta evidencia, usá data_gaps.
- Sé conciso (summary ≤ 3 oraciones; findings ≤ 6 ítems).
"""


def _parse_interpreter_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}

    return payload if isinstance(payload, dict) else {}


def _degraded_note(role: str, reason: str) -> dict[str, Any]:
    return {
        "role": role,
        "summary": "",
        "stance": None,
        "findings": [],
        "conflicts": [],
        "data_gaps": [reason],
    }


def _normalize_note(role: str, parsed: dict[str, Any]) -> dict[str, Any]:
    stance = parsed.get("stance")
    if stance not in _VALID_STANCES:
        stance = None

    def _str_list(key: str) -> list[str]:
        raw = parsed.get(key)
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    summary = parsed.get("summary")
    return {
        "role": role,
        "summary": str(summary).strip() if summary is not None else "",
        "stance": stance,
        "findings": _str_list("findings"),
        "conflicts": _str_list("conflicts"),
        "data_gaps": _str_list("data_gaps"),
    }


def _api_key_ready() -> bool:
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _vision_model() -> str:
    load_dotenv()
    return os.getenv("CHART_VISION_MODEL", "").strip() or "gpt-4o"


def _interpreter_model() -> str:
    load_dotenv()
    return os.getenv("CHART_INTERPRETER_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _complete_json(*, model: str, user_content: str | list[dict]) -> dict[str, Any]:
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _INTERPRETER_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "").strip()
    return _parse_interpreter_json(raw)


def interpret_chart_vision(
    *,
    symbol: str,
    chart_image_base64: str | None,
    chart_image_media_type: str = "image/png",
    chart_view: dict | None = None,
) -> dict:
    """Chart Interpreter de visión sobre la captura del Ticker Chart."""
    role = "vision"
    image_b64, media = _normalize_chart_image(
        chart_image_base64, chart_image_media_type
    )
    if not image_b64:
        return _degraded_note(
            role,
            "Interpreter visión omitido: sin captura del Ticker Chart.",
        )
    if not _api_key_ready():
        return _degraded_note(
            role,
            "Interpreter visión omitido: OPENAI_API_KEY no configurada.",
        )

    view_json = (
        json.dumps(chart_view, ensure_ascii=False, indent=2)
        if isinstance(chart_view, dict) and chart_view
        else "(no enviada)"
    )
    text_body = (
        f"Rol: visión del Ticker Chart.\n"
        f"Ticker: {symbol}\n\n"
        f"Vista Operator al capturar (chart_view):\n{view_json}\n\n"
        "Hay una imagen adjunta: captura real del Ticker Chart "
        "(velas + overlays + osciladores visibles). "
        "Describí estructura de precio, niveles y lecturas visuales relevantes."
    )
    user_content: list[dict] = [
        {"type": "text", "text": text_body},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media};base64,{image_b64}",
                "detail": "high",
            },
        },
    ]
    try:
        parsed = _complete_json(model=_vision_model(), user_content=user_content)
        if not parsed:
            return _degraded_note(role, "Interpreter visión: respuesta JSON vacía o inválida.")
        return _normalize_note(role, parsed)
    except Exception as exc:  # noqa: BLE001 — degradación controlada
        return _degraded_note(role, f"Interpreter visión omitido por error: {exc}")


def interpret_corpus_narrative(*, symbol: str, corpus_notes: str) -> dict:
    """Chart Interpreter de narrativa del Corpus."""
    role = "narrative"
    notes = (corpus_notes or "").strip()
    if not notes:
        return _degraded_note(role, "Interpreter narrativa omitido: sin notas de Corpus.")
    if not _api_key_ready():
        return _degraded_note(
            role,
            "Interpreter narrativa omitido: OPENAI_API_KEY no configurada.",
        )

    user_content = (
        f"Rol: narrativa del Corpus.\n"
        f"Ticker: {symbol}\n\n"
        f"Notas del Corpus (signals recientes + búsqueda):\n{notes}\n\n"
        "Resumí catalizadores, tono y temas dominantes anclados a estas notas."
    )
    try:
        parsed = _complete_json(model=_interpreter_model(), user_content=user_content)
        if not parsed:
            return _degraded_note(
                role, "Interpreter narrativa: respuesta JSON vacía o inválida."
            )
        return _normalize_note(role, parsed)
    except Exception as exc:  # noqa: BLE001
        return _degraded_note(role, f"Interpreter narrativa omitido por error: {exc}")


def interpret_sentiment_vs_price(
    *,
    symbol: str,
    sentiment_stats: dict,
    quote_summary: str,
    price_returns: dict,
) -> dict:
    """Chart Interpreter de sentimiento vs precio."""
    role = "sentiment"
    if not _api_key_ready():
        return _degraded_note(
            role,
            "Interpreter sentimiento omitido: OPENAI_API_KEY no configurada.",
        )

    payload = {
        "sentiment_stats": sentiment_stats or {},
        "quote_summary": quote_summary or "(sin cotización)",
        "price_returns": price_returns or {},
    }
    user_content = (
        f"Rol: sentimiento vs precio.\n"
        f"Ticker: {symbol}\n\n"
        f"Datos:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Contrastá tono del Corpus (sentimiento) con retornos/precio. "
        "Señalá alineación o divergencia."
    )
    try:
        parsed = _complete_json(model=_interpreter_model(), user_content=user_content)
        if not parsed:
            return _degraded_note(
                role, "Interpreter sentimiento: respuesta JSON vacía o inválida."
            )
        return _normalize_note(role, parsed)
    except Exception as exc:  # noqa: BLE001
        return _degraded_note(role, f"Interpreter sentimiento omitido por error: {exc}")


def interpret_multi_tf_ta(*, symbol: str, multi_tf_stats: dict) -> dict:
    """Chart Interpreter de TA multi-ventana (5d·15m, 3mo·1d, 1y·1d)."""
    role = "multi_tf"
    if not multi_tf_stats:
        return _degraded_note(
            role, "Interpreter multi-TF omitido: sin stats técnicas multi-ventana."
        )
    if not _api_key_ready():
        return _degraded_note(
            role,
            "Interpreter multi-TF omitido: OPENAI_API_KEY no configurada.",
        )

    user_content = (
        f"Rol: TA multi-ventana.\n"
        f"Ticker: {symbol}\n\n"
        "Stats técnicas por ventana (claves tipicas: 5d_15m, 3mo_1d, 1y_1d):\n"
        f"{json.dumps(multi_tf_stats, ensure_ascii=False, indent=2)}\n\n"
        "Compará estructura y momentum entre ventanas; no inventes números ausentes."
    )
    try:
        parsed = _complete_json(model=_interpreter_model(), user_content=user_content)
        if not parsed:
            return _degraded_note(
                role, "Interpreter multi-TF: respuesta JSON vacía o inválida."
            )
        return _normalize_note(role, parsed)
    except Exception as exc:  # noqa: BLE001
        return _degraded_note(role, f"Interpreter multi-TF omitido por error: {exc}")


def run_chart_interpreters_parallel(
    *,
    symbol: str,
    chart_image_base64: str | None,
    chart_image_media_type: str,
    chart_view: dict | None,
    corpus_notes: str,
    sentiment_stats: dict,
    quote_summary: str,
    price_returns: dict,
    multi_tf_stats: dict,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> list[dict]:
    """Ejecuta los 4 Chart Interpreters en paralelo con pasos visibles."""

    jobs: list[tuple[str, str, Callable[[], dict]]] = [
        (
            "chart_interpreter_vision",
            "Interpreter · visión",
            lambda: interpret_chart_vision(
                symbol=symbol,
                chart_image_base64=chart_image_base64,
                chart_image_media_type=chart_image_media_type,
                chart_view=chart_view,
            ),
        ),
        (
            "chart_interpreter_narrative",
            "Interpreter · narrativa",
            lambda: interpret_corpus_narrative(
                symbol=symbol, corpus_notes=corpus_notes
            ),
        ),
        (
            "chart_interpreter_sentiment",
            "Interpreter · sentimiento",
            lambda: interpret_sentiment_vs_price(
                symbol=symbol,
                sentiment_stats=sentiment_stats,
                quote_summary=quote_summary,
                price_returns=price_returns,
            ),
        ),
        (
            "chart_interpreter_multi_tf",
            "Interpreter · multi-TF",
            lambda: interpret_multi_tf_ta(
                symbol=symbol, multi_tf_stats=multi_tf_stats
            ),
        ),
    ]

    results: dict[str, dict] = {}

    def _run(tool: str, label: str, fn: Callable[[], dict]) -> tuple[str, dict]:
        if on_step:
            on_step(ResearchStepEvent(tool=tool, label=label, status="running"))
        note = fn()
        if on_step:
            on_step(ResearchStepEvent(tool=tool, label=label, status="done"))
        return tool, note

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_run, tool, label, fn) for tool, label, fn in jobs
        ]
        for future in as_completed(futures):
            tool, note = future.result()
            results[tool] = note

    order = [job[0] for job in jobs]
    return [results[tool] for tool in order if tool in results]
