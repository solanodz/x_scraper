"""Provenance: origen de hechos no-Signal (Market Data, FX, fundamentals, etc.).

Distinto de Citation (que siempre apunta a un Signal del Corpus). Ver F32 / CONTEXT.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

ProvenanceKind = Literal[
    "market_data",
    "fundamentals",
    "fx",
    "corpus_stats",
    "chart_plan",
]

KIND_LABELS: dict[str, str] = {
    "market_data": "Market Data",
    "fundamentals": "Fundamentals",
    "fx": "FX",
    "corpus_stats": "Corpus stats",
    "chart_plan": "Chart Plan",
}

SOURCE_LABELS: dict[str, str] = {
    "finnhub": "Finnhub",
    "yfinance": "yfinance",
    "alpha_vantage": "Alpha Vantage",
    "dolarapi.com": "dolarapi",
    "dolarapi": "dolarapi",
    "frankfurter.app": "Frankfurter",
    "frankfurter": "Frankfurter",
    "none": "N/A",
    "unknown": "desconocido",
}


@dataclass(frozen=True)
class Provenance:
    kind: str
    source: str
    as_of: str | None = None
    delay_label: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None}


def normalize_provenance(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    source = str(raw.get("source") or "").strip()
    if not kind or not source:
        return None
    out: dict[str, Any] = {"kind": kind, "source": source}
    as_of = raw.get("as_of")
    if isinstance(as_of, str) and as_of.strip():
        out["as_of"] = as_of.strip()
    delay = raw.get("delay_label")
    if isinstance(delay, str) and delay.strip():
        out["delay_label"] = delay.strip()
    note = raw.get("note")
    if isinstance(note, str) and note.strip():
        out["note"] = note.strip()
    return out


def format_as_of_clock(as_of: str | None) -> str | None:
    if not as_of:
        return None
    try:
        text = as_of.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt.strftime("%H:%M")
    except (TypeError, ValueError):
        return None


def format_provenance_label(prov: Provenance | dict[str, Any]) -> str:
    """Etiqueta corta legible para chips UI."""
    data = prov.to_dict() if isinstance(prov, Provenance) else normalize_provenance(prov)
    if not data:
        return ""
    kind = KIND_LABELS.get(data["kind"], data["kind"])
    source = SOURCE_LABELS.get(data["source"], data["source"])
    parts = [kind, source]
    if data.get("delay_label"):
        parts.append(f"delay {data['delay_label']}")
    clock = format_as_of_clock(data.get("as_of"))
    if clock:
        parts.append(clock)
    if data.get("note"):
        parts.append(str(data["note"]))
    return " · ".join(parts)


def market_data_provenance(
    *,
    source: str,
    as_of: str | None = None,
    delayed: bool = True,
    note: str | None = None,
) -> Provenance:
    return Provenance(
        kind="market_data",
        source=source or "unknown",
        as_of=as_of,
        delay_label="~15m" if delayed else None,
        note=note,
    )


def fundamentals_provenance(
    *,
    source: str,
    as_of: str | None = None,
    note: str | None = None,
) -> Provenance:
    return Provenance(
        kind="fundamentals",
        source=source or "none",
        as_of=as_of,
        note=note,
    )


def fx_provenance(
    *,
    source: str,
    as_of: str | None = None,
    note: str | None = None,
) -> Provenance:
    return Provenance(
        kind="fx",
        source=source or "unknown",
        as_of=as_of,
        note=note,
    )


def chart_plan_provenance(
    *,
    source: str = "yfinance",
    as_of: str | None = None,
    delayed: bool = True,
) -> Provenance:
    return Provenance(
        kind="chart_plan",
        source=source,
        as_of=as_of,
        delay_label="~15m" if delayed else None,
        note="lecturas ancladas a Market Data",
    )


def attach_provenance(payload: dict[str, Any], prov: Provenance) -> dict[str, Any]:
    out = dict(payload)
    out["provenance"] = prov.to_dict()
    return out


def collect_provenances(*items: Any) -> list[dict[str, Any]]:
    """Dedup por (kind, source, note) preservando orden."""
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, list):
            for nested in item:
                out.extend(collect_provenances(nested))
            continue
        if isinstance(item, Provenance):
            data = item.to_dict()
        elif isinstance(item, dict):
            if "provenance" in item:
                data = normalize_provenance(item.get("provenance"))
            else:
                data = normalize_provenance(item)
        else:
            continue
        if not data:
            continue
        key = (data["kind"], data["source"], str(data.get("note") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(data)
    return out
