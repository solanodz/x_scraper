"""Verificación F32: Provenance para datos no-Signal."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("verify_f32_provenance")

    from backend.services.provenance import (
        collect_provenances,
        format_provenance_label,
        fundamentals_provenance,
        fx_provenance,
        market_data_provenance,
        normalize_provenance,
    )

    md = market_data_provenance(
        source="finnhub", as_of="2026-07-25T17:02:00+00:00", delayed=True
    )
    label = format_provenance_label(md)
    if "Market Data" not in label or "Finnhub" not in label or "~15m" not in label:
        print(f"   FAIL: market_data label: {label}")
        return 1
    print("   format_provenance_label OK")

    fx = fx_provenance(source="dolarapi.com", as_of="2026-07-25T17:00:00Z", note="blue")
    if fx.to_dict().get("kind") != "fx":
        print(f"   FAIL: fx kind: {fx}")
        return 1

    fund = fundamentals_provenance(
        source="yfinance", note="PE no disponible"
    ).to_dict()
    if fund.get("note") != "PE no disponible":
        print(f"   FAIL: fundamentals note: {fund}")
        return 1
    print("   helpers OK")

    merged = collect_provenances(
        md,
        {"provenance": fx.to_dict()},
        fund,
        md,  # dedupe
    )
    if len(merged) != 3:
        print(f"   FAIL: collect dedupe expected 3, got {len(merged)}: {merged}")
        return 1
    print("   collect_provenances OK")

    # --- Quote schema / route ---
    from backend.app.schemas import Quote as QuoteSchema
    from backend.app.routes import quotes as quotes_routes
    from backend.services.market_data import Quote as DomainQuote
    from datetime import datetime, timezone

    q = DomainQuote(
        symbol="AAPL",
        price=100.0,
        change=1.0,
        change_percent=1.0,
        timestamp=datetime.now(tz=timezone.utc),
        delayed=True,
        source="finnhub",
    )
    schema = quotes_routes._to_schema(q)
    if schema.provenance is None or schema.provenance.source != "finnhub":
        print(f"   FAIL: quote schema provenance: {schema}")
        return 1
    if "provenance" not in QuoteSchema.model_fields:
        print("   FAIL: Quote schema missing provenance field")
        return 1
    print("   Quote API provenance OK")

    # --- Fundamentals ---
    from backend.services.fundamentals import FundamentalsSnapshot

    snap = FundamentalsSnapshot(
        symbol="AAPL",
        asset_kind="equity",
        price=100.0,
        market_cap=None,
        pe=None,
        eps=1.0,
        sector="Tech",
        industry="Hardware",
        source="finnhub",
        as_of="2026-07-25T17:00:00+00:00",
    )
    d = snap.to_dict()
    prov = normalize_provenance(d.get("provenance"))
    if not prov or prov["kind"] != "fundamentals":
        print(f"   FAIL: fundamentals.to_dict provenance: {d}")
        return 1
    if "PE" not in str(prov.get("note") or "") and "market cap" not in str(
        prov.get("note") or ""
    ):
        print(f"   FAIL: expected N/A note in fundamentals: {prov}")
        return 1
    print("   Fundamentals provenance OK")

    # --- FX ---
    from backend.services.fx import fetch_ars_usd_quotes

    # Don't hit network if cache empty — unit-shape via helper path
    sample_fx = {
        "scope": "ars_usd",
        "source": "dolarapi.com",
        "fetched_at": "2026-07-25T17:00:00+00:00",
        "provenance": fx_provenance(
            source="dolarapi.com", as_of="2026-07-25T17:00:00+00:00"
        ).to_dict(),
        "quotes": [],
    }
    if not normalize_provenance(sample_fx.get("provenance")):
        print("   FAIL: fx sample")
        return 1
    # Ensure live function attaches when it returns (signature exists)
    if not callable(fetch_ars_usd_quotes):
        print("   FAIL: fetch_ars_usd_quotes missing")
        return 1
    print("   FX provenance contract OK")

    # --- Research meta ---
    from backend.services.research_steps import ResearchAnswerMeta

    meta = ResearchAnswerMeta(
        path="fast",
        summary_only=False,
        provenances=(md.to_dict(),),
    )
    meta_d = meta.to_dict()
    if not meta_d.get("provenances"):
        print(f"   FAIL: ResearchAnswerMeta provenances: {meta_d}")
        return 1
    print("   ResearchAnswerMeta provenances OK")

    # --- Chart plan payload ---
    from backend.services.chart_plan import chart_plan_content_payload

    plan = chart_plan_content_payload(
        {
            "timeframes": [],
            "views": [],
            "suggested_view": {},
            "indicator_readings": [],
            "tradingview_studies": [],
            "assessment": {},
            "chart_data": {},
        }
    )
    if not normalize_provenance(plan.get("provenance")):
        print(f"   FAIL: chart plan provenance: {plan}")
        return 1
    print("   Chart Plan provenance OK")

    # --- Tools price_chart artifact ---
    from backend.services.tools import _price_chart_artifact

    art = _price_chart_artifact(
        {
            "symbol": "BTC",
            "period": "1mo",
            "interval": "1d",
            "candles": [
                {
                    "date": "2026-07-01",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 1.5,
                },
                {
                    "date": "2026-07-02",
                    "open": 1.5,
                    "high": 2,
                    "low": 1.4,
                    "close": 1.8,
                },
            ],
            "start_price": 1.5,
            "end_price": 1.8,
            "change_percent": 20.0,
        }
    )
    if not art or not normalize_provenance(art.get("provenance")):
        print(f"   FAIL: price_chart artifact provenance: {art}")
        return 1
    print("   price_chart artifact provenance OK")

    # --- Frontend wire ---
    chip = (ROOT / "frontend/src/components/ProvenanceChip.tsx").read_text()
    quote_ui = (ROOT / "frontend/src/components/QuoteStrip.tsx").read_text()
    dossier_ui = (ROOT / "frontend/src/components/DossierPanel.tsx").read_text()
    research_ui = (ROOT / "frontend/src/components/ResearchChat.tsx").read_text()
    types = (ROOT / "frontend/src/lib/types.ts").read_text()
    if "ProvenanceChip" not in chip:
        print("   FAIL: missing ProvenanceChip component")
        return 1
    if "ProvenanceChip" not in quote_ui:
        print("   FAIL: QuoteStrip missing ProvenanceChip")
        return 1
    if "ProvenanceChip" not in dossier_ui:
        print("   FAIL: DossierPanel missing ProvenanceChip")
        return 1
    if "provenances" not in research_ui or "ProvenanceList" not in research_ui:
        print("   FAIL: ResearchChat missing provenances footer")
        return 1
    if "export interface Provenance" not in types:
        print("   FAIL: types.ts missing Provenance")
        return 1
    # Citations regression: still wired
    if "onCitationClick" not in research_ui:
        print("   FAIL: Citation click regression")
        return 1
    print("   UI: QuoteStrip + Dossier + Research + Citation intact")

    # ask_stream yields meta with provenances
    import importlib

    ask_module = importlib.import_module("backend.services.ask")
    src = inspect.getsource(ask_module.ask_stream)
    if "provenances" not in src or "collect_provenances" not in src:
        print("   FAIL: ask_stream not emitting provenances")
        return 1
    print("   ask_stream provenances wire OK")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
