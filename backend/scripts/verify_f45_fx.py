"""Verificación F45: FX Quotes (dolarapi + Frankfurter) con HTTP mockeado."""

from __future__ import annotations

import json
import sys
from unittest.mock import patch

from backend.services import fx
from backend.services.tools import TOOL_DEFINITIONS, execute_tool


class _FakeResp:
    def __init__(self, payload: object):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _url_of(req_or_url) -> str:
    if hasattr(req_or_url, "full_url"):
        return str(req_or_url.full_url)
    return str(req_or_url)


def _mock_urlopen(req_or_url, *args, **kwargs):
    url_s = _url_of(req_or_url)
    if "/v1/dolares" in url_s and url_s.rstrip("/").endswith("dolares"):
        return _FakeResp(
            [
                {
                    "moneda": "USD",
                    "casa": "oficial",
                    "nombre": "Oficial",
                    "compra": 1000,
                    "venta": 1050,
                    "fechaActualizacion": "2026-07-22T12:00:00.000Z",
                },
                {
                    "moneda": "USD",
                    "casa": "blue",
                    "nombre": "Blue",
                    "compra": 1200,
                    "venta": 1220,
                    "fechaActualizacion": "2026-07-22T12:05:00.000Z",
                },
                {
                    "moneda": "USD",
                    "casa": "bolsa",
                    "nombre": "Bolsa",
                    "compra": 1100,
                    "venta": 1110,
                    "fechaActualizacion": "2026-07-22T12:05:00.000Z",
                },
            ]
        )
    if "frankfurter.app" in url_s:
        return _FakeResp(
            {
                "amount": 1.0,
                "base": "EUR",
                "date": "2026-07-22",
                "rates": {"USD": 1.08},
            }
        )
    raise AssertionError(f"URL no mockeada: {url_s}")


def main() -> int:
    fx.clear_fx_cache()

    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "get_fx_quotes" in names, "get_fx_quotes missing from TOOL_DEFINITIONS"

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen):
        ars = fx.get_fx_quotes(scope="ars_usd", use_cache=False)
        assert ars.get("scope") == "ars_usd"
        assert ars.get("source") == "dolarapi.com"
        labels = {q["label"] for q in ars.get("quotes", [])}
        assert "oficial" in labels and "blue" in labels
        assert "mep" in labels

        pair = fx.get_fx_quotes(
            scope="pair",
            base="EUR",
            quote="USD",
            use_cache=False,
        )
        assert pair.get("rate") == 1.08
        assert pair.get("source") == "frankfurter.app"
        assert pair.get("date") == "2026-07-22"

        tool_json, hits = execute_tool("get_fx_quotes", {"scope": "ars_usd"})
        assert hits == []
        tool_payload = json.loads(tool_json)
        assert tool_payload.get("quotes")
        assert not tool_payload.get("error")

        tool_pair, _ = execute_tool(
            "get_fx_quotes",
            {"scope": "pair", "pairs": ["EUR/USD"]},
        )
        pair_payload = json.loads(tool_pair)
        assert pair_payload.get("results")
        assert pair_payload["results"][0].get("rate") == 1.08

    # Fuente caída: no inventar números
    def _fail(*_a, **_k):
        raise TimeoutError("network down")

    fx.clear_fx_cache()
    with patch("urllib.request.urlopen", side_effect=_fail):
        failed = fx.get_fx_quotes(scope="ars_usd", use_cache=False)
        assert failed.get("error")
        assert not failed.get("quotes")

        failed_pair = fx.fetch_frankfurter_pair("EUR", "USD", use_cache=False)
        assert failed_pair.get("error")
        assert "rate" not in failed_pair or failed_pair.get("error")

    # USD no es Ticker de equity (evita Chart Plan ~$92).
    from backend.services.ticker_catalog import resolve_ticker_input
    from backend.services.ticker_extract import extract_tickers_from_query

    assert resolve_ticker_input("USD") is None
    assert resolve_ticker_input("$USD") is None
    assert extract_tickers_from_query("precio del dólar blue") == []
    bad_quote, _ = execute_tool("get_quotes", {"symbols": ["USD"]})
    assert "get_fx_quotes" in bad_quote or "divisa" in bad_quote.lower()
    bad_hist, _ = execute_tool("get_price_history", {"symbol": "USD"})
    assert "get_fx_quotes" in bad_hist or "divisa" in bad_hist.lower()

    print("verify_f45_fx OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
