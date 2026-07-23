"""FX Quotes: dólar Argentina (dolarapi) + pares comunes (Frankfurter)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

DOLARAPI_BASE = "https://dolarapi.com/v1"
FRANKFURTER_BASE = "https://api.frankfurter.app"
DEFAULT_CACHE_TTL_SECONDS = 300  # ~5 min

# Códigos ISO de moneda: nunca son Tickers de equity en este producto.
# Evita que "USD" / "dólar" abra Quote Strip, Dossier o Chart Plan (~$92 de un ETF).
FX_CURRENCY_CODES: frozenset[str] = frozenset(
    {
        "USD",
        "ARS",
        "EUR",
        "GBP",
        "JPY",
        "BRL",
        "CNY",
        "MXN",
        "CLP",
        "UYU",
        "CAD",
        "AUD",
        "CHF",
        "NZD",
    }
)


def is_fx_currency_code(raw: str | None) -> bool:
    """True si el texto es un código de moneda (no Ticker de acciones/cripto)."""
    if not raw or not str(raw).strip():
        return False
    sym = str(raw).strip().lstrip("$").upper()
    return sym in FX_CURRENCY_CODES


# casa dolarapi → etiqueta canónica para el Operator
ARS_USD_CASAS: tuple[tuple[str, str], ...] = (
    ("oficial", "oficial"),
    ("blue", "blue"),
    ("bolsa", "mep"),
    ("contadoconliqui", "ccl"),
    ("tarjeta", "tarjeta"),
)

_cache: dict[str, tuple[Any, float]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any, ttl: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
    _cache[key] = (value, time.monotonic() + max(30, ttl))


def clear_fx_cache() -> None:
    """Limpia cache en proceso (tests)."""
    _cache.clear()


def _http_get_json(url: str, *, timeout: float = 8.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "x-scraper-terminal/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _parse_dolarapi_item(item: dict[str, Any], label: str) -> dict[str, Any]:
    compra = item.get("compra")
    venta = item.get("venta")
    return {
        "label": label,
        "casa": item.get("casa") or label,
        "nombre": item.get("nombre") or label,
        "bid": float(compra) if compra is not None else None,
        "ask": float(venta) if venta is not None else None,
        "currency_pair": "USD/ARS",
        "updated_at": item.get("fechaActualizacion"),
        "source": "dolarapi.com",
    }


def fetch_ars_usd_quotes(*, use_cache: bool = True) -> dict[str, Any]:
    """Cotizaciones USD en Argentina (oficial, blue, MEP, CCL, tarjeta si hay)."""
    cache_key = "ars_usd"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    quotes: list[dict[str, Any]] = []
    errors: list[str] = []

    # Preferir listado completo; fallback por casa.
    try:
        payload = _http_get_json(f"{DOLARAPI_BASE}/dolares")
        if isinstance(payload, list):
            by_casa = {
                str(item.get("casa", "")).strip().lower(): item
                for item in payload
                if isinstance(item, dict)
            }
            for casa, label in ARS_USD_CASAS:
                item = by_casa.get(casa)
                if item:
                    quotes.append(_parse_dolarapi_item(item, label))
        else:
            errors.append("respuesta inesperada de dolarapi /dolares")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"dolarapi list: {exc}")
        for casa, label in ARS_USD_CASAS:
            try:
                item = _http_get_json(f"{DOLARAPI_BASE}/dolares/{casa}")
                if isinstance(item, dict):
                    quotes.append(_parse_dolarapi_item(item, label))
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                ValueError,
            ) as casa_exc:
                errors.append(f"dolarapi {casa}: {casa_exc}")

    result: dict[str, Any] = {
        "scope": "ars_usd",
        "quotes": quotes,
        "fetched_at": _now_iso(),
        "source": "dolarapi.com",
    }
    if not quotes:
        result["error"] = "No se obtuvieron cotizaciones USD/ARS"
        if errors:
            result["details"] = errors
    elif errors:
        result["warnings"] = errors

    if quotes:
        _cache_set(cache_key, result)
    return result


def fetch_frankfurter_pair(
    base: str,
    quote: str,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Par FX vía Frankfurter (ECB). No inventa números si falla la fuente."""
    base_c = base.strip().upper()
    quote_c = quote.strip().upper()
    if not base_c or not quote_c:
        return {"error": "base y quote requeridos", "source": "frankfurter.app"}
    if base_c == quote_c:
        return {
            "scope": "pair",
            "base": base_c,
            "quote": quote_c,
            "rate": 1.0,
            "date": None,
            "fetched_at": _now_iso(),
            "source": "frankfurter.app",
        }

    cache_key = f"pair:{base_c}:{quote_c}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    params = urllib.parse.urlencode({"from": base_c, "to": quote_c})
    url = f"{FRANKFURTER_BASE}/latest?{params}"
    try:
        payload = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {
            "error": f"No se pudo obtener {base_c}/{quote_c}: {exc}",
            "base": base_c,
            "quote": quote_c,
            "source": "frankfurter.app",
            "fetched_at": _now_iso(),
        }

    rates = payload.get("rates") if isinstance(payload, dict) else None
    if not isinstance(rates, dict) or quote_c not in rates:
        return {
            "error": f"Sin tasa para {base_c}/{quote_c}",
            "base": base_c,
            "quote": quote_c,
            "source": "frankfurter.app",
            "fetched_at": _now_iso(),
            "raw_keys": list(rates.keys()) if isinstance(rates, dict) else [],
        }

    result = {
        "scope": "pair",
        "base": base_c,
        "quote": quote_c,
        "rate": float(rates[quote_c]),
        "date": payload.get("date"),
        "fetched_at": _now_iso(),
        "source": "frankfurter.app",
    }
    _cache_set(cache_key, result)
    return result


def get_fx_quotes(
    *,
    scope: str = "ars_usd",
    base: str | None = None,
    quote: str | None = None,
    pairs: list[str] | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """API unificada para la tool get_fx_quotes."""
    effective_scope = (scope or "ars_usd").strip().lower()

    if effective_scope == "ars_usd":
        return fetch_ars_usd_quotes(use_cache=use_cache)

    if effective_scope == "pair":
        results: list[dict[str, Any]] = []
        if pairs:
            for raw in pairs:
                text = str(raw).strip().upper().replace(" ", "")
                if "/" in text:
                    b, q = text.split("/", 1)
                elif len(text) == 6 and text.isalpha():
                    b, q = text[:3], text[3:]
                else:
                    results.append({"error": f"par inválido: {raw}", "pair": raw})
                    continue
                results.append(fetch_frankfurter_pair(b, q, use_cache=use_cache))
            return {
                "scope": "pair",
                "results": results,
                "fetched_at": _now_iso(),
            }

        if base and quote:
            return fetch_frankfurter_pair(base, quote, use_cache=use_cache)

        return {
            "error": "Para scope=pair indicá base+quote o pairs (ej. EUR/USD)",
            "scope": "pair",
            "fetched_at": _now_iso(),
        }

    return {
        "error": f"scope desconocido: {scope}",
        "hint": "Usá ars_usd o pair",
        "fetched_at": _now_iso(),
    }
