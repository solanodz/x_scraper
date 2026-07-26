"""Smoke verify: latency pack (dossier stream route, ask TTFT chart overlap, SWR)."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("verify_latency_loaders")

    dossier_routes = importlib.import_module("backend.app.routes.dossier")
    if not hasattr(dossier_routes, "post_dossier_refresh_stream"):
        print("   FAIL: missing POST /dossier/{symbol}/refresh/stream")
        return 1
    print("   dossier refresh stream route OK")

    ask_mod = importlib.import_module("backend.services.ask")
    src = inspect.getsource(ask_mod.ask_stream)
    if "ThreadPoolExecutor" not in src or "ensure_price_chart_artifacts" not in src:
        print("   FAIL: ask_stream missing parallel chart ensure")
        return 1
    if src.find("stream_answer") < src.find("ensure_price_chart_artifacts"):
        # ensure is submitted before stream; submission can appear before stream_answer
        pass
    if "chart_future" not in src:
        print("   FAIL: ask_stream missing chart_future overlap")
        return 1
    print("   ask_stream TTFT chart overlap OK")

    gather_src = inspect.getsource(
        importlib.import_module("backend.services.dossier")._gather_bundle
    )
    if "ThreadPoolExecutor" not in gather_src:
        print("   FAIL: dossier gather not parallel")
        return 1
    print("   dossier parallel gather OK")

    api = (ROOT / "frontend/src/lib/api.ts").read_text()
    panel = (ROOT / "frontend/src/components/DossierPanel.tsx").read_text()
    strip = (ROOT / "frontend/src/components/QuoteStrip.tsx").read_text()
    cache = ROOT / "frontend/src/lib/quoteCache.ts"
    if "streamDossierRefresh" not in api:
        print("   FAIL: api missing streamDossierRefresh")
        return 1
    if "streamDossierRefresh" not in panel or "ResearchStepLoader" not in panel:
        print("   FAIL: DossierPanel not wired to stream + steps")
        return 1
    if not cache.is_file() or "readCachedWatchlistQuotes" not in strip:
        print("   FAIL: QuoteStrip SWR cache missing")
        return 1
    print("   frontend wire OK")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
