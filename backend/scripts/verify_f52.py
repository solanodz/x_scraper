"""Verificación F52: Dossier Fundamentals snapshot (Finnhub→yfinance)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("verify_f52_dossier_fundamentals")

    import backend.app.main  # noqa: F401 — resolve import cycles

    from backend.services.fundamentals import (
        FundamentalsSnapshot,
        fetch_fundamentals_snapshot,
        format_fundamentals_markdown,
    )
    from backend.services.dossier import (
        _attach_deterministic_layers,
        _mock_dossier_content,
        build_dossier_context,
        dossier_content_payload,
    )
    from backend.services.dossier import DossierGather
    from backend.services.market_data import Quote
    from datetime import datetime, timezone

    # 1) Crypto: honest N/A ratios
    crypto = fetch_fundamentals_snapshot("BTC")
    if crypto.asset_kind != "crypto":
        print(f"   FAIL: BTC asset_kind={crypto.asset_kind}")
        return 1
    if crypto.pe is not None or crypto.eps is not None or crypto.market_cap is not None:
        print("   FAIL: crypto should not invent PE/EPS/mkt cap")
        return 1
    md = format_fundamentals_markdown(crypto)
    if "no disponible" not in md:
        print("   FAIL: crypto markdown missing 'no disponible'")
        return 1
    print("   crypto → honest N/A")

    # 2) Equity mock Finnhub path
    fake_profile = {
        "name": "Apple Inc",
        "marketCapitalization": 3000.0,  # millions
        "finnhubIndustry": "Technology",
    }
    fake_metric = {"metric": {"peTTM": 28.5, "epsTTM": 6.4}}

    with (
        patch(
            "backend.services.fundamentals._fetch_finnhub_profile",
            return_value=fake_profile,
        ),
        patch(
            "backend.services.fundamentals._fetch_finnhub_metric",
            return_value=fake_metric,
        ),
    ):
        equity = fetch_fundamentals_snapshot(
            "AAPL",
            quote=Quote(
                symbol="AAPL",
                price=190.0,
                change=1.0,
                change_percent=0.5,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        )
    if equity.source != "finnhub":
        print(f"   FAIL: expected finnhub source, got {equity.source}")
        return 1
    if equity.market_cap != 3000.0 * 1_000_000:
        print(f"   FAIL: mcap scale wrong: {equity.market_cap}")
        return 1
    if equity.pe != 28.5 or equity.eps != 6.4:
        print(f"   FAIL: pe/eps {equity.pe}/{equity.eps}")
        return 1
    print("   equity Finnhub snapshot OK")

    # 3) Missing fields stay None → markdown says no disponible
    empty = FundamentalsSnapshot(
        symbol="ZZZZ",
        asset_kind="unknown",
        price=None,
        market_cap=None,
        pe=None,
        eps=None,
        sector=None,
        industry=None,
        source="none",
        as_of="2026-07-25T00:00:00+00:00",
    )
    empty_md = format_fundamentals_markdown(empty)
    if empty_md.count("no disponible") < 4:
        print(f"   FAIL: expected multiple N/A, got:\n{empty_md}")
        return 1
    print("   missing fields → no disponible (no inventar)")

    # 4) Dossier attach overwrites block + payload
    gather = DossierGather(
        symbol="AAPL",
        thesis=None,
        quote=None,
        fundamentals=equity,
        hits_7d=[],
        hits_7_30d=[],
        sentiment_stats={"total_signals": 0},
        corpus_stats_30d={"total_signals": 0, "hours": 720},
    )
    content = _attach_deterministic_layers(_mock_dossier_content("AAPL"), gather)
    fund_block = content["blocks"]["fundamentals"]
    if "28.50" not in fund_block:
        print(f"   FAIL: block missing PE:\n{fund_block}")
        return 1
    if "F31 pendiente" in fund_block:
        print("   FAIL: old placeholder still present")
        return 1
    payload = dossier_content_payload(content)
    if not isinstance(payload.get("fundamentals"), dict):
        print("   FAIL: payload missing fundamentals dict")
        return 1
    ctx = build_dossier_context(gather, macro_hits=[])
    if "F31 pendiente" in ctx:
        print("   FAIL: context still has F31 placeholder")
        return 1
    if "no disponible" not in ctx:
        print("   FAIL: context missing honesty cue")
        return 1
    print("   dossier attach + context OK")

    # 5) UI surfaces snapshot
    panel = (ROOT / "frontend/src/components/DossierPanel.tsx").read_text()
    if "FundamentalsSnapshotPanel" not in panel or "no disponible" not in panel:
        print("   FAIL: DossierPanel missing FundamentalsSnapshotPanel")
        return 1
    print("   UI panel present")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
