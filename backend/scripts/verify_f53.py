"""Verificación F53: polish confianza (landing + empty states + Research chips)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("verify_f53_trust_polish")

    landing = (ROOT / "frontend/src/components/landing/FeaturesBento.tsx").read_text()
    hero = (
        ROOT / "frontend/src/components/ui/gradient-bar-hero-section.tsx"
    ).read_text()
    page = (ROOT / "frontend/src/app/page.tsx").read_text()

    for banned in (
        "Forecast Q3",
        "Track institutional flow",
        "institutional conviction",
        "raised PT to",
    ):
        if banned in landing:
            print(f"   FAIL: landing still has false-promise copy: {banned!r}")
            return 1
    if "Forecast" in landing and "sin templates de forecast" not in landing.lower():
        # allow the word only in the disclaimer sentence
        if "forecast inventado" not in landing.lower():
            print("   FAIL: landing still markets Forecast queries")
            return 1

    if "Briefing" not in hero and "Briefing" not in page:
        print("   FAIL: landing missing Briefing mention")
        return 1
    if "Paper Bot" not in hero and "Paper Bot" not in page:
        print("   FAIL: landing missing Paper Bot mention")
        return 1
    print("   landing honest + Briefing/Bot")

    quotes = (ROOT / "frontend/src/components/QuoteStrip.tsx").read_text()
    chart = (ROOT / "frontend/src/components/ChartPlanPanel.tsx").read_text()
    if "Cotizaciones no disponibles" not in quotes:
        print("   FAIL: QuoteStrip missing clear empty copy")
        return 1
    if "Deshabilitado" not in chart or "Sin velas" not in chart:
        print("   FAIL: ChartPlan missing disabled/empty states")
        return 1
    print("   empty/disabled states present")

    import backend.app.main  # noqa: F401

    from backend.services.research_steps import (
        ResearchAnswerMeta,
        context_mentions_summary_only,
    )
    from backend.services.research_fast_path import build_fast_path_context
    from unittest.mock import patch

    assert context_mentions_summary_only('{"content_depth": "summary_only"}')
    assert not context_mentions_summary_only("full_body only")
    meta = ResearchAnswerMeta(path="fast", summary_only=True)
    assert meta.to_dict() == {"path": "fast", "summary_only": True}

    with patch(
        "backend.services.research_fast_path.execute_tool",
        return_value=('{"quotes":[]}', []),
    ):
        result = build_fast_path_context("precio BTC")
    if result is None or result.path != "fast":
        print(f"   FAIL: fast path GatherResult.path expected fast, got {result}")
        return 1
    print("   ResearchAnswerMeta + fast path=fast")

    chat_route = (ROOT / "backend/app/routes/chat.py").read_text()
    if 'event: meta' not in chat_route:
        print("   FAIL: chat SSE missing event: meta")
        return 1

    research_ui = (ROOT / "frontend/src/components/ResearchChat.tsx").read_text()
    if "Rápido" not in research_ui or "Solo summary" not in research_ui:
        print("   FAIL: ResearchChat missing path chips")
        return 1
    if "onMeta" not in research_ui:
        print("   FAIL: ResearchChat not wiring onMeta")
        return 1
    print("   UI chips Rápido/Research + Solo summary")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
